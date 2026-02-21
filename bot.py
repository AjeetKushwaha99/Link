import os
import re
import logging
import requests
import asyncio
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)

# ============== CONFIG ==============
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DOWNLOAD_PATH = "./downloads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

os.makedirs(DOWNLOAD_PATH, exist_ok=True)

# ============== LINK PATTERNS ==============
DISKWALA_PATTERNS = [
    r'https?://(?:www\.)?diskwala\.me/s/\S+',
    r'https?://(?:www\.)?diskwala\.com/app/\S+',
    r'https?://(?:www\.)?diskwala\.com/\S+',
    r'https?://diskwala\.me/\S+',
]


def is_diskwala_link(text):
    for pattern in DISKWALA_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def extract_link(text):
    for pattern in DISKWALA_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


# ============== VIDEO EXTRACTOR ==============
class VideoExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;'
                      'q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://diskwala.com/',
        })

    def extract(self, url):
        result = {
            'success': False,
            'title': 'Unknown Video',
            'direct_url': None,
            'thumbnail': None,
            'method': None,
            'error': None,
        }

        # Method 1: Web Scraping
        try:
            logger.info(f"Method 1: Scraping {url}")
            response = self.session.get(url, allow_redirects=True, timeout=30)
            final_url = response.url
            content_type = response.headers.get('content-type', '')

            # Check if redirected to video
            if 'video' in content_type:
                result['success'] = True
                result['direct_url'] = final_url
                result['method'] = 'Direct Redirect'
                return result

            soup = BeautifulSoup(response.text, 'html.parser')

            # Get title
            title_tag = soup.find('title')
            if title_tag:
                result['title'] = title_tag.text.strip()

            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                result['title'] = og_title['content']

            # Get thumbnail
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                result['thumbnail'] = og_image['content']

            # Find video tag
            video_tag = soup.find('video')
            if video_tag:
                source = video_tag.find('source')
                if source and source.get('src'):
                    result['success'] = True
                    result['direct_url'] = source['src']
                    result['method'] = 'Video Tag'
                    return result
                elif video_tag.get('src'):
                    result['success'] = True
                    result['direct_url'] = video_tag['src']
                    result['method'] = 'Video Tag'
                    return result

            # Search in scripts
            scripts = soup.find_all('script')
            video_patterns = [
                r'"(?:file|url|src|source|video_url|videoUrl|mp4|download_url|downloadUrl)"'
                r':\s*"(https?://[^"]+)"',
                r"'(?:file|url|src|source|video_url|mp4)'"
                r":\s*'(https?://[^']+)'",
                r'source:\s*["\']([^"\']+\.(?:mp4|mkv|webm|m3u8))',
                r'file:\s*["\']([^"\']+\.(?:mp4|mkv|webm|m3u8))',
                r'(https?://[^\s"\'<>]+\.(?:mp4|mkv|webm)(?:\?[^\s"\'<>]*)?)',
                r'atob\(["\']([^"\']+)["\']\)',
            ]

            for script in scripts:
                if script.string:
                    for pattern in video_patterns:
                        matches = re.findall(pattern, script.string)
                        for match in matches:
                            if isinstance(match, tuple):
                                match = match[0]
                            if any(ext in match.lower()
                                   for ext in ['.mp4', '.mkv', '.webm', '.m3u8',
                                               'video', 'download', 'stream']):
                                result['success'] = True
                                result['direct_url'] = match
                                result['method'] = 'Script Parse'
                                return result

            # Check meta og:video
            og_video = soup.find('meta', property='og:video')
            if og_video and og_video.get('content'):
                result['success'] = True
                result['direct_url'] = og_video['content']
                result['method'] = 'OG Video Meta'
                return result

            og_video_url = soup.find('meta', property='og:video:url')
            if og_video_url and og_video_url.get('content'):
                result['success'] = True
                result['direct_url'] = og_video_url['content']
                result['method'] = 'OG Video URL Meta'
                return result

            # Check all anchor tags for download links
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                text_content = a_tag.get_text().lower()
                if any(word in text_content
                       for word in ['download', 'direct', 'mp4']):
                    if href.startswith('http'):
                        result['success'] = True
                        result['direct_url'] = href
                        result['method'] = 'Download Button'
                        return result

            # Check iframes
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                iframe_src = iframe.get('src', '')
                if iframe_src:
                    result['success'] = True
                    result['direct_url'] = iframe_src
                    result['method'] = 'Iframe Source'
                    return result

        except Exception as e:
            logger.error(f"Method 1 error: {e}")

        # Method 2: Mobile User Agent
        try:
            logger.info(f"Method 2: Mobile UA for {url}")
            mobile_headers = {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 13; Pixel 7) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/120.0.0.0 Mobile Safari/537.36',
            }
            resp = requests.get(
                url, headers=mobile_headers,
                allow_redirects=True, timeout=30,
            )
            soup = BeautifulSoup(resp.text, 'html.parser')

            video_tag = soup.find('video')
            if video_tag:
                src = video_tag.get('src')
                source = video_tag.find('source')
                if source:
                    src = source.get('src')
                if src:
                    result['success'] = True
                    result['direct_url'] = src
                    result['method'] = 'Mobile Scrape'
                    return result

        except Exception as e:
            logger.error(f"Method 2 error: {e}")

        # Method 3: API endpoints
        try:
            logger.info(f"Method 3: API for {url}")
            api_urls = []

            if '/s/' in url:
                file_id = url.split('/s/')[-1].split('?')[0].split('/')[0]
                api_urls.extend([
                    f"https://diskwala.com/api/file/{file_id}",
                    f"https://diskwala.me/api/file/{file_id}",
                    f"https://diskwala.com/api/v1/file/{file_id}",
                    f"https://diskwala.me/download/{file_id}",
                ])
            elif '/app/' in url:
                file_id = url.split('/app/')[-1].split('?')[0].split('/')[0]
                api_urls.extend([
                    f"https://diskwala.com/api/file/{file_id}",
                    f"https://diskwala.com/api/v1/download/{file_id}",
                ])

            for api_url in api_urls:
                try:
                    resp = requests.get(
                        api_url,
                        headers=self.session.headers,
                        timeout=15,
                        allow_redirects=True,
                    )
                    ct = resp.headers.get('content-type', '')

                    if 'video' in ct or 'octet-stream' in ct:
                        result['success'] = True
                        result['direct_url'] = resp.url
                        result['method'] = 'API Direct'
                        return result

                    if 'json' in ct:
                        data = resp.json()
                        for key in ['url', 'download_url', 'file_url',
                                    'video_url', 'link', 'data']:
                            if key in data:
                                val = data[key]
                                if isinstance(val, str) and val.startswith('http'):
                                    result['success'] = True
                                    result['direct_url'] = val
                                    result['method'] = 'API JSON'
                                    return result
                                elif isinstance(val, dict):
                                    for k2 in ['url', 'download', 'link']:
                                        if k2 in val:
                                            result['success'] = True
                                            result['direct_url'] = val[k2]
                                            result['method'] = 'API JSON Nested'
                                            return result
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Method 3 error: {e}")

        result['error'] = (
            "Video URL extract nahi ho paya.\n"
            "Link expired ya protected ho sakta hai."
        )
        return result


# ============== BOT HANDLERS ==============
extractor = VideoExtractor()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = """
🎬 *DiskWala Video Downloader Bot*

Mujhe DiskWala ka link bhejo!
Main direct download link dunga! 🚀

*Supported Links:*
• `diskwala.me/s/xxxxx`
• `diskwala.com/app/xxxxx`

*Commands:*
/start \\- Bot start karo
/help \\- Help dekho

Simply link paste karo aur bhej do\\! ⚡
"""
    await update.message.reply_text(welcome, parse_mode='MarkdownV2')


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📖 **How to Use:**

1️⃣ DiskWala video link copy karo
2️⃣ Yahan paste karke send karo
3️⃣ Bot direct link dega ya video bhejega

⚠️ **Limits:**
• 50MB tak ki files direct bheji jaengi
• Badi files ka link milega

💡 **Tips:**
• Full URL paste karo
• Ek baar mein ek link
• Thoda wait karo processing ke liye
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not is_diskwala_link(text):
        await update.message.reply_text(
            "❌ Valid DiskWala link nahi hai!\n\n"
            "Example:\n"
            "`https://diskwala.me/s/xxxxx`",
            parse_mode='Markdown',
        )
        return

    url = extract_link(text)
    if not url:
        await update.message.reply_text("❌ Link extract nahi hua!")
        return

    msg = await update.message.reply_text(
        "⏳ **Processing...**\n"
        "🔍 Video dhundh raha hoon...\n"
        "Thoda wait karo...",
        parse_mode='Markdown',
    )

    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, extractor.extract, url
        )

        if result['success'] and result['direct_url']:
            direct_url = result['direct_url']

            # Make absolute URL if relative
            if not direct_url.startswith('http'):
                from urllib.parse import urljoin
                direct_url = urljoin(url, direct_url)

            response_text = (
                f"✅ **Video Mil Gaya!**\n\n"
                f"📹 **Title:** {result['title']}\n"
                f"🔧 **Method:** {result['method']}\n\n"
                f"🔗 **Direct Link:**\n"
                f"`{direct_url}`\n\n"
                f"👆 Link copy karke browser mein kholo ya\n"
                f"niche button dabao!"
            )

            keyboard = []

            # Download button
            if direct_url.startswith('http'):
                keyboard.append([
                    InlineKeyboardButton(
                        "⬇️ Open Download Link",
                        url=direct_url,
                    )
                ])

            keyboard.append([
                InlineKeyboardButton(
                    "📤 Try Send as File",
                    callback_data=f"sendfile|{direct_url[:200]}",
                )
            ])

            reply_markup = InlineKeyboardMarkup(keyboard)

            if result.get('thumbnail'):
                try:
                    await msg.delete()
                    await update.message.reply_photo(
                        photo=result['thumbnail'],
                        caption=response_text,
                        parse_mode='Markdown',
                        reply_markup=reply_markup,
                    )
                    return
                except Exception:
                    pass

            await msg.edit_text(
                response_text,
                parse_mode='Markdown',
                reply_markup=reply_markup,
            )

        else:
            error = result.get('error', 'Unknown error')
            await msg.edit_text(
                f"❌ **Video nahi mila!**\n\n"
                f"🔍 Error: {error}\n\n"
                f"💡 **Kya karo:**\n"
                f"• Check karo link sahi hai\n"
                f"• Link expired toh nahi\n"
                f"• Doosra link try karo\n\n"
                f"🔗 Original: `{url}`",
                parse_mode='Markdown',
            )

    except Exception as e:
        logger.error(f"Process error: {e}")
        await msg.edit_text(
            f"❌ **Error!**\n{str(e)}\n\nPlease try again.",
            parse_mode='Markdown',
        )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("sendfile|"):
        video_url = data.split("|", 1)[1]

        await query.edit_message_text(
            "⏳ **Downloading & Sending...**\n"
            "File download ho rahi hai...",
            parse_mode='Markdown',
        )

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36',
            }
            resp = requests.get(
                video_url, headers=headers,
                stream=True, timeout=60,
            )

            content_length = int(resp.headers.get('content-length', 0))

            if content_length > MAX_FILE_SIZE:
                await query.edit_message_text(
                    f"⚠️ **File bahut badi hai!**\n\n"
                    f"📦 Size: {content_length / (1024*1024):.1f} MB\n"
                    f"📌 Limit: 50 MB\n\n"
                    f"Direct link se download karo:\n"
                    f"`{video_url}`",
                    parse_mode='Markdown',
                )
                return

            # Download file
            filepath = os.path.join(
                DOWNLOAD_PATH,
                f"video_{query.message.message_id}.mp4",
            )

            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                file_size = os.path.getsize(filepath)
                if file_size <= MAX_FILE_SIZE:
                    await query.message.reply_video(
                        video=open(filepath, 'rb'),
                        caption="✅ DiskWala se download hua!",
                    )
                    await query.edit_message_text("✅ Video sent!")
                else:
                    await query.edit_message_text(
                        f"⚠️ File too large: "
                        f"{file_size / (1024*1024):.1f} MB",
                    )
            else:
                await query.edit_message_text("❌ Download failed!")

            # Cleanup
            try:
                os.remove(filepath)
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Send file error: {e}")
            await query.edit_message_text(
                f"❌ **Send failed!**\n{str(e)}\n\n"
                f"Direct link use karo.",
                parse_mode='Markdown',
            )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        text = update.message.text.strip()
        if is_diskwala_link(text) or 'diskwala' in text.lower():
            await process_link(update, context)
        else:
            await update.message.reply_text(
                "🎬 Mujhe DiskWala ka link bhejo!\n\n"
                "Example:\n"
                "`https://diskwala.me/s/xxxxx`",
                parse_mode='Markdown',
            )


# ============== MAIN ==============
def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not set!")
        return

    print("🤖 Starting DiskWala Bot...")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("✅ Bot is running!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
