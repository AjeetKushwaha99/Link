import os
import re
import json
import asyncio
import logging
import time
import hashlib
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ============== CONFIG ==============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DOWNLOAD_PATH = "./downloads"
MAX_FILE_SIZE = 50 * 1024 * 1024

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
os.makedirs(DOWNLOAD_PATH, exist_ok=True)


def extract_file_id(text):
    patterns = [
        r'diskwala\.com/app/([a-f0-9]{24})',
        r'diskwala\.me/s/(\S+)',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return None


# =============================================
#  CHROME DRIVER SETUP
# =============================================
def get_chrome_driver():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--window-size=1920,1080')
    options.add_argument(
        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )

    # Enable network logging
    options.set_capability(
        'goog:loggingPrefs', {'performance': 'ALL'}
    )

    options.binary_location = '/usr/bin/google-chrome'

    driver = webdriver.Chrome(options=options)
    return driver


# =============================================
#  EXTRACT VIDEO URL FROM DISKWALA
# =============================================
def extract_video_sync(file_id):
    """
    Uses real Chrome browser to:
    1. Open DiskWala page
    2. Let AppiCrypt WASM load & run
    3. Capture API responses with video URL
    """
    result = {
        'success': False,
        'title': 'Unknown',
        'video_url': None,
        'file_info': None,
        'error': None,
    }

    driver = None
    try:
        logger.info(f"Starting Chrome for file: {file_id}")
        driver = get_chrome_driver()

        # Enable CDP Network domain to capture responses
        driver.execute_cdp_cmd('Network.enable', {})

        url = f"https://www.diskwala.com/app/{file_id}"
        logger.info(f"Opening: {url}")
        driver.get(url)

        # Wait for page to load
        time.sleep(5)

        # METHOD 1: Intercept network requests via logs
        logger.info("Checking network logs...")
        logs = driver.get_log('performance')

        api_responses = []
        video_urls = []

        for log_entry in logs:
            try:
                log_data = json.loads(log_entry['message'])
                message = log_data.get('message', {})
                method = message.get('method', '')
                params = message.get('params', {})

                # Capture request URLs
                if method == 'Network.requestWillBeSent':
                    req_url = params.get(
                        'request', {}
                    ).get('url', '')

                    if any(
                        kw in req_url.lower()
                        for kw in [
                            'sign', 'temp_info', 'video',
                            'stream', 'download', '.mp4',
                            '.mkv', 'storage.googleapis',
                            'r2.cloudflarestorage',
                            'cdn', 'media',
                        ]
                    ):
                        logger.info(
                            f"Interesting request: {req_url}"
                        )
                        video_urls.append(req_url)

                # Capture response data
                if method == 'Network.responseReceived':
                    resp = params.get('response', {})
                    resp_url = resp.get('url', '')
                    resp_type = resp.get(
                        'mimeType', ''
                    )

                    if 'ddudapidd.diskwala.com' in resp_url:
                        req_id = params.get('requestId')
                        try:
                            body = driver.execute_cdp_cmd(
                                'Network.getResponseBody',
                                {'requestId': req_id},
                            )
                            body_text = body.get('body', '')
                            logger.info(
                                f"API Response [{resp_url}]:"
                                f" {body_text[:500]}"
                            )
                            api_responses.append({
                                'url': resp_url,
                                'body': body_text,
                            })
                        except Exception:
                            pass

                    if 'video' in resp_type:
                        logger.info(
                            f"Video response: {resp_url}"
                        )
                        video_urls.append(resp_url)

            except Exception:
                pass

        # METHOD 2: Execute JS to call API
        # (browser has AppiCrypt loaded!)
        logger.info("Calling API from browser JS...")

        # Call /file/temp_info from inside browser
        try:
            temp_info_js = f"""
                return await (async () => {{
                    try {{
                        // Get the axios instance
                        // It's already configured
                        // with AppiCrypt interceptor

                        // Try using fetch with
                        // the page's context
                        const response = await fetch(
                            'https://ddudapidd.diskwala.com'
                            + '/api/v1/file/temp_info',
                            {{
                                method: 'POST',
                                headers: {{
                                    'Content-Type':
                                        'application/json',
                                }},
                                body: JSON.stringify({{
                                    id: '{file_id}'
                                }}),
                                credentials: 'include',
                            }}
                        );
                        const data = await response.text();
                        return {{
                            status: response.status,
                            data: data,
                        }};
                    }} catch(e) {{
                        return {{error: e.message}};
                    }}
                }})();
            """
            temp_result = driver.execute_script(temp_info_js)
            logger.info(f"temp_info result: {temp_result}")

            if temp_result and temp_result.get('data'):
                try:
                    info = json.loads(temp_result['data'])
                    result['file_info'] = info
                    logger.info(f"File info: {info}")

                    # Extract title
                    for key in ['name', 'fileName', 'title']:
                        if key in info:
                            result['title'] = info[key]
                            break

                except Exception as e:
                    logger.error(f"JSON parse error: {e}")
        except Exception as e:
            logger.error(f"temp_info JS error: {e}")

        # Call /file/sign from inside browser
        # (AppiCrypt will auto-generate headers!)
        try:
            sign_js = f"""
                return await (async () => {{
                    try {{
                        const response = await fetch(
                            'https://ddudapidd.diskwala.com'
                            + '/api/v1/file/sign',
                            {{
                                method: 'POST',
                                headers: {{
                                    'Content-Type':
                                        'application/json',
                                }},
                                body: JSON.stringify({{
                                    id: '{file_id}'
                                }}),
                                credentials: 'include',
                            }}
                        );
                        const data = await response.text();
                        return {{
                            status: response.status,
                            data: data,
                        }};
                    }} catch(e) {{
                        return {{error: e.message}};
                    }}
                }})();
            """
            sign_result = driver.execute_script(sign_js)
            logger.info(f"sign result: {sign_result}")

            if sign_result and sign_result.get('data'):
                try:
                    sign_data = json.loads(
                        sign_result['data']
                    )
                    logger.info(
                        f"Sign data: "
                        f"{json.dumps(sign_data)[:500]}"
                    )

                    # Extract video URL from sign response
                    url_keys = [
                        'url', 'signedUrl', 'signed_url',
                        'downloadUrl', 'download_url',
                        'videoUrl', 'video_url',
                        'link', 'fileUrl', 'file_url',
                        'streamUrl', 'stream_url',
                        'src', 'source', 'path',
                        'location',
                    ]

                    def find_url(data, depth=0):
                        if depth > 3:
                            return None
                        if isinstance(data, str):
                            if data.startswith('http'):
                                return data
                            return None
                        if isinstance(data, dict):
                            for key in url_keys:
                                if key in data:
                                    val = data[key]
                                    if isinstance(
                                        val, str
                                    ) and val.startswith(
                                        'http'
                                    ):
                                        return val
                            for key, val in data.items():
                                found = find_url(
                                    val, depth + 1
                                )
                                if found:
                                    return found
                        if isinstance(data, list):
                            for item in data:
                                found = find_url(
                                    item, depth + 1
                                )
                                if found:
                                    return found
                        return None

                    video_url = find_url(sign_data)
                    if video_url:
                        result['success'] = True
                        result['video_url'] = video_url
                        logger.info(
                            f"VIDEO URL FOUND: {video_url}"
                        )

                except Exception as e:
                    logger.error(
                        f"Sign JSON parse error: {e}"
                    )
        except Exception as e:
            logger.error(f"sign JS error: {e}")

        # METHOD 3: Use the page's OWN axios instance
        if not result['success']:
            logger.info(
                "Trying page's own axios instance..."
            )
            try:
                axios_js = f"""
                    return await (async () => {{
                        try {{
                            // Find the axios instance
                            // on the page
                            // The React app stores it

                            // Method A: Direct window check
                            if (window.__NEXT_DATA__) {{
                                return {{
                                    next: JSON.stringify(
                                        window.__NEXT_DATA__
                                    ),
                                }};
                            }}

                            // Method B: Check React fiber
                            const root = document
                                .getElementById('root');
                            if (root && root._reactRootContainer) {{
                                return {{
                                    react: 'found root',
                                }};
                            }}

                            // Method C: Look for video
                            // elements on page
                            const vids = document
                                .querySelectorAll('video');
                            const vidData = [];
                            vids.forEach(v => {{
                                vidData.push({{
                                    src: v.src,
                                    currentSrc: v.currentSrc,
                                    poster: v.poster,
                                }});
                                v.querySelectorAll('source')
                                 .forEach(s => {{
                                    vidData.push({{
                                        src: s.src,
                                        type: s.type,
                                    }});
                                }});
                            }});

                            // Method D: Check all iframes
                            const iframes = document
                                .querySelectorAll('iframe');
                            const iframeData = [];
                            iframes.forEach(f => {{
                                iframeData.push({{
                                    src: f.src,
                                }});
                            }});

                            // Method E: Get page HTML
                            const bodyHTML = document.body
                                ? document.body.innerHTML
                                    .substring(0, 5000)
                                : '';

                            return {{
                                videos: vidData,
                                iframes: iframeData,
                                title: document.title,
                                bodyPreview: bodyHTML,
                            }};
                        }} catch(e) {{
                            return {{error: e.message}};
                        }}
                    }})();
                """
                page_data = driver.execute_script(axios_js)
                logger.info(
                    f"Page data: "
                    f"{json.dumps(page_data)[:1000]}"
                )

                if page_data:
                    # Check videos
                    for v in page_data.get('videos', []):
                        src = v.get('src') or v.get(
                            'currentSrc', ''
                        )
                        if src and src.startswith('http'):
                            result['success'] = True
                            result['video_url'] = src
                            break

                    result['title'] = page_data.get(
                        'title', result['title']
                    )

            except Exception as e:
                logger.error(f"Axios JS error: {e}")

        # METHOD 4: Check captured network URLs
        if not result['success'] and video_urls:
            for vu in video_urls:
                if any(
                    ext in vu.lower()
                    for ext in [
                        '.mp4', '.mkv', '.webm',
                        'storage.googleapis',
                        'r2.cloudflarestorage',
                        'stream', 'video', 'media',
                    ]
                ):
                    if 'ddudapidd' not in vu:
                        result['success'] = True
                        result['video_url'] = vu
                        break

        # METHOD 5: Check API response bodies
        if not result['success'] and api_responses:
            for api_resp in api_responses:
                try:
                    data = json.loads(api_resp['body'])
                    video_url = None
                    if isinstance(data, dict):
                        for key in [
                            'url', 'signedUrl',
                            'download_url', 'link',
                            'videoUrl', 'src',
                        ]:
                            if key in data:
                                val = data[key]
                                if isinstance(
                                    val, str
                                ) and val.startswith(
                                    'http'
                                ):
                                    video_url = val
                                    break
                    if video_url:
                        result['success'] = True
                        result['video_url'] = video_url
                        break
                except Exception:
                    pass

        if not result['success']:
            result['error'] = (
                "Video URL nahi mila.\n"
                f"API responses: {len(api_responses)}\n"
                f"Network URLs: {len(video_urls)}\n"
            )
            if api_responses:
                result['error'] += (
                    f"\nAPI Data:\n"
                    f"{api_responses[0].get('body', '')[:500]}"
                )
            if result.get('file_info'):
                result['error'] += (
                    f"\nFile Info:\n"
                    f"{json.dumps(result['file_info'])[:500]}"
                )

    except Exception as e:
        logger.error(f"Chrome error: {e}")
        result['error'] = f"Browser error: {str(e)}"
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return result


# =============================================
#  TELEGRAM BOT HANDLERS
# =============================================
async def start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "🎬 **DiskWala Video Downloader Bot**\n\n"
        "DiskWala ka link bhejo!\n"
        "Main direct download link dunga! 🚀\n\n"
        "**Example:**\n"
        "`https://www.diskwala.com/app/xxxxx`\n\n"
        "⏱ Pehli baar 20-30 sec lagenge",
        parse_mode='Markdown',
    )


async def process_link(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    text = update.message.text.strip()
    file_id = extract_file_id(text)

    if not file_id:
        await update.message.reply_text(
            "❌ Valid DiskWala link nahi hai!\n\n"
            "Example:\n"
            "`https://www.diskwala.com/app/xxxxx`",
            parse_mode='Markdown',
        )
        return

    msg = await update.message.reply_text(
        "⏳ **Processing...**\n"
        "🌐 Chrome browser start ho raha hai...\n"
        "🔐 AppiCrypt bypass ho raha hai...\n"
        "⏱ 20-30 seconds wait karo...",
        parse_mode='Markdown',
    )

    try:
        # Run sync Chrome in executor
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, extract_video_sync, file_id
        )

        if result['success'] and result['video_url']:
            video_url = result['video_url']

            response_text = (
                f"✅ **Video Mil Gaya!**\n\n"
                f"📹 **Title:** {result['title']}\n\n"
                f"🔗 **Direct Download Link:**\n"
                f"`{video_url}`\n\n"
                f"👆 Link copy karke browser mein kholo\n"
                f"Ya niche button dabao!"
            )

            keyboard = []
            if video_url.startswith('http'):
                keyboard.append([
                    InlineKeyboardButton(
                        "⬇️ Download Video",
                        url=video_url,
                    )
                ])

            await msg.edit_text(
                response_text,
                parse_mode='Markdown',
                reply_markup=(
                    InlineKeyboardMarkup(keyboard)
                    if keyboard else None
                ),
            )

        else:
            error = result.get('error', 'Unknown')
            await msg.edit_text(
                f"❌ **Video nahi mila**\n\n"
                f"🔍 Debug Info:\n"
                f"```\n{error[:1000]}\n```\n\n"
                f"💡 File ID: `{file_id}`\n\n"
                f"Ye info developer ko bhejo!",
                parse_mode='Markdown',
            )

    except Exception as e:
        logger.error(f"Process error: {e}")
        await msg.edit_text(f"❌ Error: {str(e)}")


async def handle_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    if extract_file_id(text):
        await process_link(update, context)
    else:
        await update.message.reply_text(
            "🎬 DiskWala link bhejo!\n"
            "`https://www.diskwala.com/app/xxxxx`",
            parse_mode='Markdown',
        )


def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not set!")
        return

    print("🤖 Starting DiskWala Bot...")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    print("✅ Bot running!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
