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
)

# ============== CONFIG ==============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


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
#  DISKWALA EXTRACTOR - PLAYWRIGHT
#  Uses page's OWN Axios with AppiCrypt
# =============================================
class DiskWalaExtractor:

    async def extract_video(self, file_id):
        result = {
            'success': False,
            'title': 'Unknown',
            'video_url': None,
            'file_info': None,
            'error': None,
            'debug': '',
        }

        browser = None
        try:
            from playwright.async_api import async_playwright

            pw = await async_playwright().start()
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                ],
            )

            context = await browser.new_context(
                user_agent=(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                ),
            )

            page = await context.new_page()

            # ===== CAPTURE ALL NETWORK TRAFFIC =====
            captured = {
                'sign_data': None,
                'temp_info': None,
                'video_urls': [],
                'all_api': [],
            }

            async def on_response(response):
                url = response.url
                try:
                    if 'ddudapidd.diskwala.com' in url:
                        try:
                            body = await response.text()
                            captured['all_api'].append({
                                'url': url,
                                'status': response.status,
                                'body': body,
                            })
                            logger.info(
                                f"API [{response.status}] "
                                f"{url}: {body[:300]}"
                            )

                            if response.status == 200:
                                data = json.loads(body)
                                if '/file/sign' in url:
                                    captured['sign_data'] = data
                                if '/file/temp_info' in url:
                                    captured['temp_info'] = data

                        except Exception:
                            pass

                    ct = response.headers.get(
                        'content-type', ''
                    )
                    if (
                        'video' in ct
                        or 'octet-stream' in ct
                    ):
                        captured['video_urls'].append(url)
                        logger.info(f"VIDEO URL: {url}")

                    if any(
                        kw in url.lower()
                        for kw in [
                            '.mp4', '.mkv', '.webm',
                            '.m3u8',
                            'storage.googleapis',
                            'r2.cloudflarestorage',
                            'cdn.diskwala',
                        ]
                    ):
                        captured['video_urls'].append(url)

                except Exception:
                    pass

            page.on('response', on_response)

            # ===== OPEN PAGE =====
            url = f"https://www.diskwala.com/app/{file_id}"
            logger.info(f"Opening: {url}")

            await page.goto(url, timeout=30000)
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(3)

            # ===== WAIT FOR REACT APP TO LOAD =====
            logger.info("Waiting for React app...")
            try:
                await page.wait_for_selector(
                    '#root > *', timeout=10000
                )
            except Exception:
                logger.warning("React root not populated")

            await asyncio.sleep(2)

            # ===== KEY STEP: USE PAGE'S AXIOS =====
            # The React app has already loaded:
            # 1. appicrypt-web WASM module
            # 2. Axios with interceptor
            # We need to find and use THAT axios instance

            logger.info(
                "Injecting script to use page's Axios..."
            )

            # First: inject a script that imports the
            # same module the page uses
            api_result = await page.evaluate("""
                async (fileId) => {
                    const results = {
                        method: null,
                        sign: null,
                        temp_info: null,
                        error: null,
                    };

                    try {
                        // METHOD 1: Find existing axios
                        // in webpack modules
                        // The page bundles everything in
                        // webpackChunk

                        let axiosInstance = null;

                        // Check if page already made
                        // the API calls and data is
                        // in React state
                        const rootEl = document
                            .getElementById('root');

                        if (rootEl) {
                            // Try to get React fiber
                            const fiberKey = Object.keys(
                                rootEl
                            ).find(
                                k => k.startsWith(
                                    '__reactFiber'
                                )
                            );

                            if (fiberKey) {
                                results.method =
                                    'react_fiber';

                                // Traverse React tree to
                                // find file data
                                let fiber = rootEl[fiberKey];
                                const visited = new Set();
                                const queue = [fiber];

                                while (queue.length > 0) {
                                    const node = queue.shift();
                                    if (!node || visited.has(node))
                                        continue;
                                    visited.add(node);

                                    if (visited.size > 500)
                                        break;

                                    // Check memoizedState
                                    // and memoizedProps
                                    const state =
                                        node.memoizedState;
                                    const props =
                                        node.memoizedProps;

                                    if (state) {
                                        const stateStr =
                                            JSON.stringify(
                                                state
                                            );
                                        if (
                                            stateStr &&
                                            stateStr.includes(
                                                'signedUrl'
                                            )
                                        ) {
                                            results.sign =
                                                stateStr
                                                    .substring(
                                                        0, 2000
                                                    );
                                        }
                                        if (
                                            stateStr &&
                                            (stateStr.includes(
                                                'fileName'
                                            ) ||
                                            stateStr.includes(
                                                'file_name'
                                            ) ||
                                            stateStr.includes(
                                                fileId
                                            ))
                                        ) {
                                            results.temp_info =
                                                stateStr
                                                    .substring(
                                                        0, 2000
                                                    );
                                        }
                                    }

                                    if (props) {
                                        const propsStr =
                                            JSON.stringify(
                                                props
                                            );
                                        if (
                                            propsStr &&
                                            (propsStr.includes(
                                                'http'
                                            ) &&
                                            (propsStr.includes(
                                                '.mp4'
                                            ) ||
                                            propsStr.includes(
                                                'storage'
                                            ) ||
                                            propsStr.includes(
                                                'signed'
                                            )))
                                        ) {
                                            results.sign =
                                                propsStr
                                                    .substring(
                                                        0, 2000
                                                    );
                                        }
                                    }

                                    // Traverse tree
                                    if (node.child)
                                        queue.push(node.child);
                                    if (node.sibling)
                                        queue.push(
                                            node.sibling
                                        );
                                    if (node.return)
                                        queue.push(
                                            node.return
                                        );
                                }
                            }
                        }

                        // METHOD 2: Access webpack modules
                        // to find the axios instance
                        if (!results.sign) {
                            results.method = 'webpack';

                            const chunkName = Object.keys(
                                window
                            ).find(
                                k => k.includes(
                                    'webpackChunk'
                                )
                            );

                            if (
                                chunkName &&
                                window[chunkName]
                            ) {
                                // Inject into webpack
                                // to get module 960
                                // (appicrypt) and the
                                // axios instance
                                let resolveAxios;
                                const axiosPromise =
                                    new Promise(r => {
                                        resolveAxios = r;
                                    });

                                window[chunkName].push([
                                    ['custom-chunk'],
                                    {},
                                    (require) => {
                                        try {
                                            // Module 960
                                            // = appicrypt
                                            const appicrypt =
                                                require(960);
                                            resolveAxios({
                                                appicrypt,
                                                require,
                                            });
                                        } catch(e) {
                                            resolveAxios({
                                                error:
                                                    e.message,
                                            });
                                        }
                                    },
                                ]);

                                const modules =
                                    await Promise.race([
                                        axiosPromise,
                                        new Promise(r =>
                                            setTimeout(
                                                () => r(null),
                                                5000,
                                            )
                                        ),
                                    ]);

                                if (
                                    modules &&
                                    modules.appicrypt
                                ) {
                                    // Use the appicrypt
                                    // module to generate
                                    // headers
                                    const genHeaders =
                                        modules
                                            .appicrypt.d;

                                    if (genHeaders) {
                                        // Generate headers
                                        // for /file/sign
                                        const headers =
                                            await genHeaders({
                                                method: 'POST',
                                                urlPath:
                                                    '/file/sign',
                                                data: {
                                                    id: fileId,
                                                },
                                            });

                                        results.method =
                                            'appicrypt_direct';

                                        // Now make the
                                        // actual API call
                                        const resp =
                                            await fetch(
                                                'https://'
                                                + 'ddudapidd'
                                                + '.diskwala'
                                                + '.com/api'
                                                + '/v1/file'
                                                + '/sign',
                                                {
                                                    method:
                                                        'POST',
                                                    headers:
                                                        headers,
                                                    body:
                                                        JSON
                                                        .stringify(
                                                            {
                                                                id:
                                                                    fileId,
                                                            }
                                                        ),
                                                    credentials:
                                                        'include',
                                                },
                                            );

                                        const data =
                                            await resp
                                                .text();
                                        results.sign =
                                            data;

                                        // Also get
                                        // temp_info
                                        const headers2 =
                                            await genHeaders({
                                                method:
                                                    'POST',
                                                urlPath:
                                                    '/file'
                                                    + '/temp'
                                                    + '_info',
                                                data: {
                                                    id:
                                                        fileId,
                                                },
                                            });

                                        const resp2 =
                                            await fetch(
                                                'https://'
                                                + 'ddudapidd'
                                                + '.diskwala'
                                                + '.com/api'
                                                + '/v1/file'
                                                + '/temp_info',
                                                {
                                                    method:
                                                        'POST',
                                                    headers:
                                                        headers2,
                                                    body:
                                                        JSON
                                                        .stringify(
                                                            {
                                                                id:
                                                                    fileId,
                                                            }
                                                        ),
                                                    credentials:
                                                        'include',
                                                },
                                            );

                                        results.temp_info =
                                            await resp2
                                                .text();
                                    }
                                }
                            }
                        }

                        // METHOD 3: Check video elements
                        const videos = document
                            .querySelectorAll('video');
                        const videoSrcs = [];
                        videos.forEach(v => {
                            if (v.src) videoSrcs.push(v.src);
                            if (v.currentSrc)
                                videoSrcs.push(v.currentSrc);
                            v.querySelectorAll('source')
                             .forEach(s => {
                                if (s.src)
                                    videoSrcs.push(s.src);
                            });
                        });
                        if (videoSrcs.length > 0) {
                            results.video_elements =
                                videoSrcs;
                        }

                        results.title = document.title;

                    } catch(e) {
                        results.error = e.message
                            + ' | ' + e.stack;
                    }

                    return results;
                }
            """, file_id)

            logger.info(
                f"Page evaluate result: "
                f"{json.dumps(api_result)[:1000]}"
            )

            # ===== PROCESS RESULTS =====
            def find_url_in_data(data):
                """Recursively find video URL"""
                if isinstance(data, str):
                    if data.startswith('http'):
                        return data
                    try:
                        return find_url_in_data(
                            json.loads(data)
                        )
                    except Exception:
                        # Search for URLs in string
                        urls = re.findall(
                            r'https?://[^\s"\'<>]+',
                            data,
                        )
                        for u in urls:
                            if any(
                                kw in u.lower()
                                for kw in [
                                    '.mp4', '.mkv',
                                    '.webm', 'storage',
                                    'signed', 'download',
                                    'stream', 'video',
                                    'cdn', 'media',
                                    'r2.cloudflare',
                                ]
                            ):
                                return u
                    return None

                if isinstance(data, dict):
                    url_keys = [
                        'url', 'signedUrl', 'signed_url',
                        'downloadUrl', 'download_url',
                        'videoUrl', 'video_url',
                        'link', 'fileUrl', 'file_url',
                        'streamUrl', 'stream_url',
                        'src', 'source', 'path',
                        'location', 'href',
                    ]
                    for key in url_keys:
                        if key in data:
                            val = data[key]
                            if isinstance(
                                val, str
                            ) and val.startswith('http'):
                                return val
                    for val in data.values():
                        found = find_url_in_data(val)
                        if found:
                            return found

                if isinstance(data, list):
                    for item in data:
                        found = find_url_in_data(item)
                        if found:
                            return found

                return None

            # Check api_result from page.evaluate
            if api_result:
                result['debug'] = json.dumps(
                    api_result
                )[:1500]

                if api_result.get('sign'):
                    video_url = find_url_in_data(
                        api_result['sign']
                    )
                    if video_url:
                        result['success'] = True
                        result['video_url'] = video_url

                if (
                    not result['success']
                    and api_result.get('temp_info')
                ):
                    video_url = find_url_in_data(
                        api_result['temp_info']
                    )
                    if video_url:
                        result['success'] = True
                        result['video_url'] = video_url

                if (
                    not result['success']
                    and api_result.get('video_elements')
                ):
                    for src in api_result['video_elements']:
                        if (
                            src
                            and src.startswith('http')
                        ):
                            result['success'] = True
                            result['video_url'] = src
                            break

                result['title'] = api_result.get(
                    'title', 'DiskWala Video'
                )

            # Check captured network responses
            if not result['success']:
                if captured.get('sign_data'):
                    video_url = find_url_in_data(
                        captured['sign_data']
                    )
                    if video_url:
                        result['success'] = True
                        result['video_url'] = video_url

                if (
                    not result['success']
                    and captured.get('temp_info')
                ):
                    video_url = find_url_in_data(
                        captured['temp_info']
                    )
                    if video_url:
                        result['success'] = True
                        result['video_url'] = video_url

                if (
                    not result['success']
                    and captured['video_urls']
                ):
                    for vu in captured['video_urls']:
                        if 'ddudapidd' not in vu:
                            result['success'] = True
                            result['video_url'] = vu
                            break

            # Check all API responses
            if (
                not result['success']
                and captured['all_api']
            ):
                for api in captured['all_api']:
                    video_url = find_url_in_data(
                        api.get('body', '')
                    )
                    if video_url:
                        result['success'] = True
                        result['video_url'] = video_url
                        break

            if not result['success']:
                result['error'] = (
                    f"Method: "
                    f"{api_result.get('method', '?')}\n"
                    f"JS Error: "
                    f"{api_result.get('error', 'None')}\n"
                    f"Network APIs: "
                    f"{len(captured['all_api'])}\n"
                    f"Video URLs: "
                    f"{len(captured['video_urls'])}\n"
                )
                if captured['all_api']:
                    for api in captured['all_api'][:3]:
                        result['error'] += (
                            f"\nAPI [{api['status']}] "
                            f"{api['url']}:\n"
                            f"{api['body'][:200]}\n"
                        )

        except Exception as e:
            logger.error(f"Extract error: {e}")
            result['error'] = str(e)
        finally:
            if browser:
                await browser.close()
                await pw.stop()

        return result


extractor = DiskWalaExtractor()


# ============== BOT HANDLERS ==============
async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🎬 *DiskWala Video Downloader Bot*\n\n"
        "DiskWala ka link bhejo\\!\n"
        "Main direct download link dunga\\! 🚀\n\n"
        "*Example:*\n"
        "`https://www.diskwala.com/app/xxxxx`\n\n"
        "⏱ 20\\-30 seconds lagenge",
        parse_mode='MarkdownV2',
    )


async def process_link(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    text = update.message.text.strip()
    file_id = extract_file_id(text)

    if not file_id:
        await update.message.reply_text(
            "❌ Valid DiskWala link nahi!\n"
            "Example: "
            "`https://www.diskwala.com/app/xxxxx`",
            parse_mode='Markdown',
        )
        return

    msg = await update.message.reply_text(
        "⏳ **Processing...**\n"
        "🌐 Browser open ho raha hai...\n"
        "🔐 Security bypass ho raha hai...\n"
        "⏱ 20-30 sec wait karo...",
        parse_mode='Markdown',
    )

    try:
        result = await extractor.extract_video(file_id)

        if result['success'] and result['video_url']:
            video_url = result['video_url']
            title = result.get('title', 'DiskWala Video')

            keyboard = []
            if video_url.startswith('http'):
                keyboard.append([
                    InlineKeyboardButton(
                        "⬇️ Download Video",
                        url=video_url,
                    )
                ])

            await msg.edit_text(
                f"✅ **Video Mil Gaya!**\n\n"
                f"📹 **Title:** {title}\n\n"
                f"🔗 **Direct Link:**\n"
                f"`{video_url}`\n\n"
                f"👆 Copy karke browser mein kholo!",
                parse_mode='Markdown',
                reply_markup=(
                    InlineKeyboardMarkup(keyboard)
                    if keyboard
                    else None
                ),
            )
        else:
            error = result.get('error', 'Unknown')
            debug = result.get('debug', '')

            error_msg = f"❌ **Video nahi mila**\n\n"
            error_msg += f"🔍 Details:\n{error}\n"

            if debug:
                short_debug = debug[:500]
                error_msg += (
                    f"\n📦 Debug:\n`{short_debug}`"
                )

            error_msg += (
                f"\n\n💡 File ID: `{file_id}`"
                f"\n\nYe info developer ko bhejo!"
            )

            await msg.edit_text(
                error_msg,
                parse_mode='Markdown',
            )

    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text(f"❌ Error: {str(e)}")


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
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
        print("❌ BOT_TOKEN set karo!")
        return
    print("🤖 Starting bot...")
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
