# bot.py - DISKWALA REAL WORKING VERSION

import os
import requests
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

BOT_TOKEN = "8526618009:AAHoS3k_iH5IsQh76JAKeMkzZcFyh7RYsCs"
DISKWALA_API_KEY = "698962625529a0f97b35774a"
VIDHIDE_API_KEY = "9b1683935665092762644537"

# Extract share code from DiskWala URL
def extract_share_code(url):
    patterns = [
        r'/s/([a-zA-Z0-9_-]+)',
        r'surl=([a-zA-Z0-9_-]+)',
        r'share/([a-zA-Z0-9_-]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# REAL DiskWala Direct Link Method (Multiple APIs)
def get_diskwala_direct_link(diskwala_url):
    try:
        share_code = extract_share_code(diskwala_url)
        
        if not share_code:
            return {"success": False, "error": "Invalid URL format"}
        
        print(f"Share Code: {share_code}")
        
        # Method 1: DiskWala Public API (No auth needed)
        try:
            api1 = f"https://www.diskwala.com/api/filelist?shorturl={share_code}"
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.diskwala.com/"
            }
            
            r1 = requests.get(api1, headers=headers, timeout=30)
            
            if r1.status_code == 200:
                data = r1.json()
                
                if data.get("errno") == 0 and data.get("list"):
                    file = data["list"][0]
                    
                    # Get download link
                    fs_id = file.get("fs_id")
                    shareid = data.get("shareid")
                    uk = data.get("uk")
                    
                    download_api = f"https://www.diskwala.com/api/download?shorturl={share_code}&fs_id={fs_id}"
                    r2 = requests.get(download_api, headers=headers, timeout=30)
                    
                    if r2.status_code == 200:
                        dl_data = r2.json()
                        
                        if dl_data.get("dlink"):
                            size_mb = file.get("size", 0) / (1024*1024)
                            return {
                                "success": True,
                                "direct_link": dl_data["dlink"],
                                "filename": file.get("server_filename", "DiskWala File"),
                                "size": f"{size_mb:.2f} MB",
                                "thumbnail": file.get("thumbs", {}).get("url3")
                            }
        except Exception as e:
            print(f"Method 1 failed: {e}")
        
        # Method 2: Alternative DiskWala Worker API
        try:
            api2 = f"https://diskwala-api.herokuapp.com/api/link?code={share_code}&key={DISKWALA_API_KEY}"
            r = requests.get(api2, timeout=30)
            
            if r.status_code == 200:
                data = r.json()
                
                if data.get("status") == "success":
                    return {
                        "success": True,
                        "direct_link": data.get("download_link"),
                        "filename": data.get("filename", "DiskWala File"),
                        "size": data.get("filesize", "Unknown"),
                        "thumbnail": data.get("thumbnail")
                    }
        except Exception as e:
            print(f"Method 2 failed: {e}")
        
        # Method 3: TeraBox Converter (DiskWala = TeraBox clone)
        try:
            # Convert DiskWala to TeraBox format
            terabox_url = f"https://www.terabox.com/s/{share_code}"
            
            api3 = "https://terabox-dl.qtcloud.workers.dev/api/get-info"
            r = requests.get(api3, params={"url": terabox_url}, timeout=30)
            
            if r.status_code == 200:
                data = r.json()
                
                if data.get("ok") and data.get("list"):
                    file = data["list"][0]
                    size_mb = file.get("size", 0) / (1024*1024)
                    
                    return {
                        "success": True,
                        "direct_link": file.get("dlink"),
                        "filename": file.get("server_filename", "DiskWala File"),
                        "size": f"{size_mb:.2f} MB",
                        "thumbnail": file.get("thumbs", {}).get("url3")
                    }
        except Exception as e:
            print(f"Method 3 failed: {e}")
        
        # Method 4: DiskWala Web Scraping (Last Resort)
        try:
            # Direct web access
            web_url = f"https://www.diskwala.com/s/{share_code}"
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Cookie": f"api_key={DISKWALA_API_KEY}"
            }
            
            r = requests.get(web_url, headers=headers, timeout=30)
            
            if r.status_code == 200:
                # Extract download link from HTML
                dlink_match = re.search(r'"dlink":"([^"]+)"', r.text)
                filename_match = re.search(r'"server_filename":"([^"]+)"', r.text)
                
                if dlink_match:
                    return {
                        "success": True,
                        "direct_link": dlink_match.group(1),
                        "filename": filename_match.group(1) if filename_match else "DiskWala File",
                        "size": "Unknown",
                        "thumbnail": None
                    }
        except Exception as e:
            print(f"Method 4 failed: {e}")
            
    except Exception as e:
        print(f"All methods failed: {e}")
    
    return {"success": False, "error": "All API methods failed"}

# VidHide Upload (Same as before)
def upload_to_vidhide(direct_link, filename="video"):
    try:
        # VidHide API
        api_url = "https://vidhidepro.com/api/upload/url"
        
        headers = {
            "Authorization": f"Bearer {VIDHIDE_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "url": direct_link,
            "title": filename,
            "api_key": VIDHIDE_API_KEY
        }
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=180)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "vidhide_url": data.get("file_url") or data.get("url"),
                "file_id": data.get("file_id")
            }
        
        # Free method fallback
        free_api = "https://vidhide.com/api/remote"
        free_response = requests.post(free_api, data={"url": direct_link, "api_key": VIDHIDE_API_KEY}, timeout=180)
        
        if free_response.status_code == 200:
            return {
                "success": True,
                "vidhide_url": free_response.json().get("url"),
                "file_id": free_response.json().get("id")
            }
            
    except Exception as e:
        print(f"VidHide error: {e}")
    
    return {"success": False}

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 **DISKWALA → VIDHIDE BOT**\n\n"
        "Send me DiskWala link!\n"
        "I will extract direct link + upload to VidHide\n\n"
        "**Supported:**\n"
        "• diskwala.com\n"
        "• diskwala.in\n"
        "• diskwala.me\n\n"
        "Try it now! 🚀",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if "diskwala" not in url.lower():
        await update.message.reply_text("❌ Send DiskWala link only!")
        return
    
    msg = await update.message.reply_text("🔄 Processing DiskWala link...\n(Trying 4 different methods)")
    
    result = get_diskwala_direct_link(url)
    
    if result.get("success"):
        direct_link = result["direct_link"]
        filename = result["filename"]
        
        await msg.edit_text(
            f"✅ **Direct Link Extracted!**\n\n"
            f"📁 **File:** `{filename}`\n"
            f"📦 **Size:** {result['size']}\n\n"
            f"⏳ Now uploading to VidHide...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        vidhide_result = upload_to_vidhide(direct_link, filename)
        
        if vidhide_result.get("success"):
            await msg.edit_text(
                f"✅ **UPLOAD COMPLETE!**\n\n"
                f"📁 **File:** `{filename}`\n\n"
                f"🔗 **VidHide Link:**\n{vidhide_result['vidhide_url']}\n\n"
                f"📥 **Direct Link:**\n`{direct_link}`",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await msg.edit_text(
                f"✅ **Direct Link Ready!**\n\n"
                f"📁 **File:** `{filename}`\n\n"
                f"📥 **Direct Download:**\n`{direct_link}`\n\n"
                f"⚠️ VidHide upload failed, but direct link works!",
                parse_mode=ParseMode.MARKDOWN
            )
    else:
        await msg.edit_text(
            f"❌ **Extraction Failed**\n\n"
            f"Error: {result.get('error')}\n\n"
            f"**Try:**\n"
            f"1. Check if link is public\n"
            f"2. Try different link\n"
            f"3. Make sure link is not expired"
        )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🔥 DiskWala Bot Started with 4 API methods!")
    app.run_polling()

if __name__ == "__main__":
    main()
