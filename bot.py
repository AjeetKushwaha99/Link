##############################################
#  DISKWALA TELEGRAM BOT - FINAL WORKING
#  Uses Playwright to handle AppiCrypt
##############################################

import os
import re
import json
import asyncio
import logging
import time
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
    CallbackQueryHandler,
)

# ============== CONFIG ==============
BOT_TOKEN = os.environ.get(
    "BOT_TOKEN", "YOUR_BOT_TOKEN_HERE"
)
DOWNLOAD_PATH = "./downloads"
MAX_FILE_SIZE = 50 * 1024 * 1024

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s"
           " - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

DISKWALA_PATTERNS = [
    r'https?://(?:www\.)?diskwala\.com/app/([a-f0-9]+)',
    r'https?://(?:www\.)?diskwala\.me/s/(\S+)',
]


def extract_file_id(text):
    for pattern in DISKWALA_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def is_diskwala_link(text):
    return extract_file_id(text) is not None


# =============================================
#  DISKWALA EXTRACTOR using Playwright
# =============================================
class DiskWalaExtractor:
    def __init__(self):
        self.browser = None
        self.context = None

    async def init_browser(self):
        if self.browser:
            return
        try:
            from playwright.async_api import async_playwright
            self.pw = await async_playwright().start()
            self.browser = await self.pw.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--single-process',
                ],
            )
            self.context = await self.browser.new_context(
                user_agent=(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                ),
            )
            logger.info("Browser initialized!")
        except Exception as e:
            logger.error(f"Browser init error: {e}")
            self.browser = None

    async def close_browser(self):
        if self.browser:
            await self.browser.close()
            await self.pw.stop()

    async def extract_video(self, file_id):
        """
        Open DiskWala page in real browser
        Intercept API calls to capture signed URL
        """
        result = {
            'success': False,
            'title': 'Unknown',
            'video_url': None,
            'thumbnail': None,
            'file_info': None,
            'error': None,
        }

        await self.init_browser()
        if not self.browser:
            result['error'] = "Browser not available"
            return result

        page = None
        try:
            page = await self.context.new_page()

            # Capture ALL network responses
            captured_data = {
                'api_responses': [],
                'video_urls': [],
                'sign_response': None,
                'temp_info': None,
            }

            async def handle_response(response):
                url = response.url
                try:
                    ct = response.headers.get(
                        'content-type', ''
                    )

                    # Capture API responses
                    if 'ddudapidd.diskwala.com' in url:
                        try:
                            body = await response.json()
                            captured_data[
                                'api_responses'
                            ].append({
                                'url': url,
                                'status': response.status,
                                'data': body,
                            })

                            if '/file/sign' in url:
                                captured_data[
                                    'sign_response'
                                ] = body
                                logger.info(
                                    f"SIGN response: {body}"
                                )

                            if '/file/temp_info' in url:
                                captured_data[
                                    'temp_info'
                                ] = body
                                logger.info(
                                    f"TEMP_INFO: {body}"
                                )
                        except Exception:
                            try:
                                body = await response.text()
                                captured_data[
                                    'api_responses'
                                ].append({
                                    'url': url,
                                    'status': response.status,
                                    'data': body,
                                })
                            except Exception:
                                pass

                    # Capture video URLs
                    if any(
                        ext in url.lower()
                        for ext in [
                            '.mp4', '.mkv', '.webm',
                            '.m3u8', 'video', 'stream',
                            'storage.googleapis.com',
                            'r2.cloudflarestorage',
                            'cdn', 'media',
                        ]
                    ):
                        captured_data['video_urls'].append({
                            'url': url,
                            'type': ct,
                            'status': response.status,
                        })
                        logger.info(f"VIDEO URL: {url}")

                    if 'video' in ct or 'octet-stream' in ct:
                        captured_data['video_urls'].append({
                            'url': url,
                            'type': ct,
                            'status': response.status,
                        })
                        logger.info(
                            f"VIDEO CONTENT: {url}"
                        )

                except Exception as e:
                    pass

            page.on("response", handle_response)

            # Navigate to DiskWala page
            app_url = (
                f"https://www.diskwala.com/app/{file_id}"
            )
            logger.info(f"Opening: {app_url}")

            await page.goto(
                app_url,
                wait_until='networkidle',
                timeout=30000,
            )

            # Wait for page to fully load
            await page.wait_for_timeout(5000)

            # Try to find and click play/download button
            play_selectors = [
                'button:has-text("Play")',
                'button:has-text("Download")',
                'button:has-text("Watch")',
                'video',
                '[class*="play"]',
                '[class*="download"]',
                '[class*="video"]',
                'a:has-text("Download")',
                'a:has-text("Play")',
            ]

            for selector in play_selectors:
                try:
                    element = await page.query_selector(
                        selector
                    )
                    if element:
                        await element.click()
                        logger.info(
                            f"Clicked: {selector}"
                        )
                        await page.wait_for_timeout(3000)
                except Exception:
                    pass

            # Wait more for video to load
            await page.wait_for_timeout(5000)

            # Also try to extract from page JS
            try:
                page_data = await page.evaluate('''
                    () => {
                        const result = {};

                        // Check video elements
                        const videos = document.querySelectorAll(
                            'video'
                        );
                        result.videos = [];
                        videos.forEach(v => {
                            result.videos.push({
                                src: v.src,
                                currentSrc: v.currentSrc,
                                poster: v.poster,
                            });
                            v.querySelectorAll('source')
                             .forEach(s => {
                                result.videos.push({
                                    src: s.src,
                                    type: s.type,
                                });
                            });
                        });

                        // Check for any blob URLs
                        const allElements = document
                            .querySelectorAll('[src]');
                        result.srcs = [];
                        allElements.forEach(el => {
                            const src = el.getAttribute('src');
                            if (src && (
                                src.includes('blob:') ||
                                src.includes('mp4') ||
                                src.includes('video') ||
                                src.includes('storage') ||
                                src.includes('cdn') ||
                                src.includes('stream')
                            )) {
                                result.srcs.push(src);
                            }
                        });

                        // Page title
                        result.title = document.title;

                        // Meta tags
                        const ogVideo = document.querySelector(
                            'meta[property="og:video"]'
                        );
                        if (ogVideo)
                            result.ogVideo = ogVideo.content;

                        const ogImage = document.querySelector(
                            'meta[property="og:image"]'
                        );
                        if (ogImage)
                            result.ogImage = ogImage.content;

                        return result;
                    }
                ''')
                logger.info(f"Page data: {page_data}")
            except Exception as e:
                page_data = {}
                logger.error(f"Page eval error: {e}")

            # Also try calling the API directly
            # from browser context
            try:
                api_result = await page.evaluate('''
                    async (fileId) => {
                        try {
                            const resp = await fetch(
                                "https://ddudapidd.diskwala.com"
                                + "/api/v1/file/temp_info",
                                {
                                    method: "POST",
                                    headers: {
                                        "Content-Type":
                                            "application/json",
                                    },
                                    body: JSON.stringify({
                                        id: fileId,
                                    }),
                                    credentials: "include",
                                }
                            );
                            return {
                                status: resp.status,
                                data: await resp.text(),
                            };
                        } catch(e) {
                            return {error: e.message};
                        }
                    }
                ''', file_id)
                logger.info(
                    f"Direct API from browser: {api_result}"
                )
                if api_result and 'data' in api_result:
                    try:
                        captured_data['temp_info'] = json.loads(
                            api_result['data']
                        )
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Browser API call error: {e}")

            # Try /file/sign from browser
            try:
                sign_result = await page.evaluate('''
                    async (fileId) => {
                        try {
                            const resp = await fetch(
                                "https://ddudapidd.diskwala.com"
                                + "/api/v1/file/sign",
                                {
                                    method: "POST",
                                    headers: {
                                        "Content-Type":
                                            "application/json",
                                    },
                                    body: JSON.stringify({
                                        id: fileId,
                                    }),
                                    credentials: "include",
                                }
                            );
                            return {
                                status: resp.status,
                                data: await resp.text(),
                            };
                        } catch(e) {
                            return {error: e.message};
                        }
                    }
                ''', file_id)
                logger.info(
                    f"Sign API from browser: {sign_result}"
                )
                if sign_result and 'data' in sign_result:
                    try:
                        captured_data[
                            'sign_response'
                        ] = json.loads(sign_result['data'])
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Sign API error: {e}")

            # ====== PROCESS RESULTS ======

            # Check sign response
            if captured_data.get('sign_response'):
                sign_data = captured_data['sign_response']
                logger.info(
                    f"Processing sign data: {sign_data}"
                )

                video_url = None
                if isinstance(sign_data, dict):
                    for key in [
                        'url', 'signedUrl', 'signed_url',
                        'download_url', 'downloadUrl',
                        'video_url', 'videoUrl', 'link',
                        'file_url', 'fileUrl', 'data',
                        'result', 'stream_url', 'streamUrl',
                    ]:
                        if key in sign_data:
                            val = sign_data[key]
                            if isinstance(val, str) and (
                                val.startswith('http') or
                                val.startswith('//')
                            ):
                                video_url = val
                                break
                            elif isinstance(val, dict):
                                for k2 in [
                                    'url', 'link',
                                    'download', 'src',
                                ]:
                                    if k2 in val:
                                        video_url = val[k2]
                                        break

                if video_url:
                    result['success'] = True
                    result['video_url'] = video_url
                    result['file_info'] = sign_data

            # Check temp_info
            if (
                not result['success'] and
                captured_data.get('temp_info')
            ):
                info = captured_data['temp_info']
                logger.info(
                    f"Processing temp_info: {info}"
                )

                if isinstance(info, dict):
                    result['file_info'] = info
                    result['title'] = info.get(
                        'name',
                        info.get(
                            'fileName',
                            info.get('title', 'Unknown'),
                        ),
                    )

                    for key in [
                        'url', 'signedUrl', 'download_url',
                        'downloadUrl', 'video_url',
                        'videoUrl', 'link', 'file_url',
                        'src', 'stream',
                    ]:
                        if key in info:
                            val = info[key]
                            if isinstance(val, str) and (
                                val.startswith('http')
                            ):
                                result['success'] = True
                                result['video_url'] = val
                                break

            # Check captured video URLs
            if (
                not result['success'] and
                captured_data['video_urls']
            ):
                for vid in captured_data['video_urls']:
                    if vid['status'] == 200:
                        result['success'] = True
                        result['video_url'] = vid['url']
                        break

            # Check page data
            if not result['success'] and page_data:
                if page_data.get('videos'):
                    for v in page_data['videos']:
                        src = v.get('src') or v.get(
                            'currentSrc', ''
                        )
                        if src and not src.startswith(
                            'blob:'
                        ):
                            result['success'] = True
                            result['video_url'] = src
                            break

                if not result['success']:
                    for src in page_data.get('srcs', []):
                        if not src.startswith('blob:'):
                            result['success'] = True
                            result['video_url'] = src
                            break

                result['title'] = page_data.get(
                    'title', result['title']
                )
                result['thumbnail'] = page_data.get(
                    'ogImage'
                )

            # Check all API responses
            if not result['success']:
                for api_resp in captured_data[
                    'api_responses'
                ]:
                    data = api_resp.get('data', {})
                    if isinstance(data, dict):
                        for key in [
                            'url', 'signedUrl',
                            'download_url', 'link',
                            'video_url', 'src',
                        ]:
                            if key in data:
                                val = data[key]
                                if isinstance(
                                    val, str
                                ) and val.startswith(
                                    'http'
                                ):
                                    result['success'] = True
                                    result[
                                        'video_url'
                                    ] = val
                                    break

            if not result['success']:
                # Return debug info
                result['error'] = (
                    "Video URL extract nahi hua.\n"
                    f"API responses: "
                    f"{len(captured_data['api_responses'])}\n"
                    f"Video URLs: "
                    f"{len(captured_data['video_urls'])}\n"
                    f"Sign: {captured_data.get('sign_response')}\n"
                    f"Info: {captured_data.get('temp_info')}"
                )

        except Exception as e:
            logger.error(f"Extract error: {e}")
            result['error'] = str(e)
        finally:
            if page:
                await page.close()

        return result


# ============== BOT HANDLERS ==============
extractor = DiskWalaExtractor()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *DiskWala Video Downloader Bot*\n\n"
        "Mujhe DiskWala ka link bhejo\\!\n"
        "Main direct download link dunga\\! 🚀\n\n"
        "*Supported:*\n"
        "• `diskwala\\.com/app/xxxxx`\n\n"
        "Simply link paste karo\\! ⚡",
        parse_mode='MarkdownV2',
    )


async def help_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "📖 **How to Use:**\n\n"
        "1️⃣ DiskWala link copy karo\n"
        "2️⃣ Yahan paste karo\n"
        "3️⃣ Bot video link/file dega\n\n"
        "⚠️ Pehli baar mein thoda time lagega\n"
        "(browser start hota hai)",
        parse_mode='Markdown',
    )


async def process_link(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    text = update.message.text.strip()
    file_id = extract_file_id(text)

    if not file_id:
        await update.message.reply_text(
            "❌ Valid DiskWala link nahi hai!"
        )
        return

    msg = await update.message.reply_text(
        "⏳ **Processing...**\n"
        "🌐 Browser start ho raha hai...\n"
        "🔐 AppiCrypt bypass ho raha hai...\n"
        "⏱ 15-30 seconds lagenge...",
        parse_mode='Markdown',
    )

    try:
        result = await extractor.extract_video(file_id)

        if result['success'] and result['video_url']:
            video_url = result['video_url']

            response_text = (
                f"✅ **Video Mil Gaya!**\n\n"
                f"📹 **Title:** {result['title']}\n\n"
                f"🔗 **Direct Link:**\n"
                f"`{video_url}`\n\n"
                f"👆 Copy karke browser mein kholo!"
            )

            keyboard = []
            if video_url.startswith('http'):
                keyboard.append([
                    InlineKeyboardButton(
                        "⬇️ Open Download Link",
                        url=video_url,
                    )
                ])

            reply_markup = (
                InlineKeyboardMarkup(keyboard)
                if keyboard else None
            )

            await msg.edit_text(
                response_text,
                parse_mode='Markdown',
                reply_markup=reply_markup,
            )

        else:
            error = result.get('error', 'Unknown error')
            debug_info = ""
            if result.get('file_info'):
                debug_info = (
                    f"\n\n📦 Debug Info:\n"
                    f"`{json.dumps(result['file_info'])[:500]}`"
                )

            await msg.edit_text(
                f"❌ **Video extract nahi hua**\n\n"
                f"🔍 Details:\n{error}"
                f"{debug_info}\n\n"
                f"💡 File ID: `{file_id}`",
                parse_mode='Markdown',
            )

    except Exception as e:
        logger.error(f"Process error: {e}")
        await msg.edit_text(
            f"❌ Error: {str(e)}"
        )


async def handle_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if update.message and update.message.text:
        text = update.message.text.strip()
        if is_diskwala_link(text):
            await process_link(update, context)
        else:
            await update.message.reply_text(
                "🎬 DiskWala link bhejo!\n\n"
                "Example:\n"
                "`https://www.diskwala.com/app/xxxxx`",
                parse_mode='Markdown',
            )


def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ BOT_TOKEN set karo!")
        return

    print("🤖 Starting DiskWala Bot...")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
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
