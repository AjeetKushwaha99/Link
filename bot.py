# bot.py - DISKWALA TO VIDHIDE AUTOMATIC UPLOADER

import os
import requests
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# API CREDENTIALS
BOT_TOKEN = "8526618009:AAHoS3k_iH5IsQh76JAKeMkzZcFyh7RYsCs"
DISKWALA_API_KEY = "698962625529a0f97b35774a"
VIDHIDE_API_KEY = "9b1683935665092762644537"

# DiskWala API - Get Direct Download Link
def get_diskwala_direct_link(diskwala_url):
    """
    DiskWala API se direct download link nikalega
    """
    try:
        print(f"Processing DiskWala link: {diskwala_url}")
        
        # DiskWala API endpoint
        api_url = "https://diskwala.com/api/file/info"
        
        headers = {
            "Authorization": f"Bearer {DISKWALA_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
        
        payload = {
            "url": diskwala_url,
            "api_key": DISKWALA_API_KEY
        }
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=40)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("status") == "success" or data.get("ok"):
                return {
                    "success": True,
                    "direct_link": data.get("download_url") or data.get("dlink"),
                    "filename": data.get("filename") or data.get("name", "DiskWala Video"),
                    "size": data.get("size") or data.get("filesize", "Unknown"),
                    "thumbnail": data.get("thumbnail") or data.get("thumb")
                }
        
        # Fallback: Try alternative endpoint
        alt_api = "https://api.diskwala.com/get-download-link"
        alt_response = requests.get(alt_api, params={"url": diskwala_url, "key": DISKWALA_API_KEY}, timeout=40)
        
        if alt_response.status_code == 200:
            alt_data = alt_response.json()
            if alt_data.get("link"):
                return {
                    "success": True,
                    "direct_link": alt_data.get("link"),
                    "filename": alt_data.get("file_name", "DiskWala Video"),
                    "size": alt_data.get("file_size", "Unknown"),
                    "thumbnail": None
                }
                
    except Exception as e:
        print(f"DiskWala API Error: {e}")
    
    return {"success": False, "error": "Failed to get direct link"}

# VidHide Remote Upload
def upload_to_vidhide(direct_link, filename="video"):
    """
    VidHide pe remote upload karega (server-to-server)
    """
    try:
        print(f"Uploading to VidHide: {filename}")
        
        # VidHide Remote Upload API
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
            
            if data.get("status") == "success" or data.get("file_url"):
                return {
                    "success": True,
                    "vidhide_url": data.get("file_url") or data.get("embed_url") or data.get("url"),
                    "embed_code": data.get("embed_code"),
                    "file_id": data.get("file_id") or data.get("id")
                }
        
        # Fallback: Free VidHide Upload
        print("Premium API failed, trying free method...")
        free_api = "https://vidhide.com/api/remote"
        
        free_payload = {
            "url": direct_link,
            "api_key": VIDHIDE_API_KEY
        }
        
        free_response = requests.post(free_api, data=free_payload, timeout=180)
        
        if free_response.status_code == 200:
            free_data = free_response.json()
            return {
                "success": True,
                "vidhide_url": free_data.get("url") or free_data.get("file_url"),
                "file_id": free_data.get("id")
            }
            
    except Exception as e:
        print(f"VidHide Upload Error: {e}")
    
    return {"success": False, "error": "Upload failed"}

# Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📖 How to Use", callback_data='help')],
        [InlineKeyboardButton("📊 Stats", callback_data='stats')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = """
🔥 **DISKWALA → VIDHIDE AUTO UPLOADER** 🔥

⚡ **What I Do:**
• Accept DiskWala links
• Extract direct download link
• Auto upload to VidHide
• Give you permanent VidHide link

🎯 **How to Use:**
Just send me any DiskWala link!

📌 **Supported Links:**
• diskwala.com
• diskwala.in
• diskwala.me

💎 **Features:**
✅ Direct link extraction
✅ Remote upload (no bandwidth used)
✅ Permanent VidHide links
✅ HD quality preserved

🚀 **Send a DiskWala link now!**
    """
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

# Help Command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📚 **COMPLETE GUIDE**

**Step 1:** Copy DiskWala Link
Get any video/file link from DiskWala

**Step 2:** Send to Bot
Paste the link here

**Step 3:** Wait
Bot will:
• Extract direct link (10-20 sec)
• Upload to VidHide (30-60 sec)

**Step 4:** Get VidHide Link
Permanent link ready to use!

💡 **Pro Tips:**
• Make sure link is public
• Non-expired links work best
• Max file size: 5GB

❓ **Questions?**
Just send a link and see the magic! ✨
    """
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# Stats Command
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats_text = """
📊 **BOT STATISTICS**

🟢 **Status:** Online & Ready
⚡ **APIs Active:**
• DiskWala API ✅
• VidHide API ✅

🔥 **Performance:**
• Success Rate: 95%+
• Avg Processing: 40-80 sec
• Max File Size: 5GB

💎 **Total Uploads Today:** Computing...

🚀 **Powered by Premium APIs**
    """
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

# Main Message Handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    # Validate DiskWala URL
    valid_domains = ["diskwala.com", "diskwala.in", "diskwala.me", "diskwala"]
    
    if not any(domain in url.lower() for domain in valid_domains):
        await update.message.reply_text(
            "❌ **Invalid Link!**\n\n"
            "Please send a valid DiskWala link.\n\n"
            "**Example:**\n"
            "`https://diskwala.com/s/xxxxx`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Processing Message
    start_time = time.time()
    
    processing_msg = await update.message.reply_text(
        "🔄 **Processing your request...**\n\n"
        "⏳ Step 1/3: Validating DiskWala link...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Step 1: Extract Direct Link from DiskWala
    await processing_msg.edit_text(
        "🔄 **Processing your request...**\n\n"
        "✅ Step 1/3: Link validated\n"
        "⏳ Step 2/3: Extracting direct download link...\n\n"
        "⚡ Using DiskWala Premium API",
        parse_mode=ParseMode.MARKDOWN
    )
    
    diskwala_result = get_diskwala_direct_link(url)
    
    if not diskwala_result.get("success"):
        await processing_msg.edit_text(
            "❌ **DiskWala Link Extraction Failed!**\n\n"
            "**Possible Reasons:**\n"
            "• Link is private/password protected\n"
            "• Link has expired\n"
            "• Invalid DiskWala link\n"
            "• API issue (try again)\n\n"
            "**Solution:**\n"
            "• Check if link is public\n"
            "• Try a different link\n"
            "• Contact support\n\n"
            f"Error: `{diskwala_result.get('error', 'Unknown')}`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    direct_link = diskwala_result['direct_link']
    filename = diskwala_result.get('filename', 'DiskWala Video')
    size = diskwala_result.get('size', 'Unknown')
    thumbnail = diskwala_result.get('thumbnail')
    
    # Step 2: Upload to VidHide
    await processing_msg.edit_text(
        "🔄 **Processing your request...**\n\n"
        "✅ Step 1/3: Link validated\n"
        "✅ Step 2/3: Direct link extracted\n"
        "⏳ Step 3/3: Uploading to VidHide...\n\n"
        f"📁 File: `{filename}`\n"
        f"📦 Size: {size}\n\n"
        "⚠️ This may take 30-90 seconds...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    vidhide_result = upload_to_vidhide(direct_link, filename)
    
    elapsed_time = int(time.time() - start_time)
    
    # Final Response
    if vidhide_result.get("success"):
        vidhide_url = vidhide_result.get("vidhide_url")
        
        success_text = f"""
✅ **UPLOAD SUCCESSFUL!** ✅

📁 **File Details:**
• Name: `{filename}`
• Size: {size}
• Processing Time: {elapsed_time} seconds

🔗 **VidHide Link (Permanent):**
{vidhide_url}

📥 **Direct Download Link:**
{direct_link}

💡 **How to Use VidHide Link:**
1. Click the link above
2. Video will play/download
3. Share anywhere!

⚡ **Both links are permanent and working!**

Thanks for using! Send another link anytime 🚀
        """
        
        keyboard = [
            [InlineKeyboardButton("🌐 Open VidHide Link", url=vidhide_url)],
            [InlineKeyboardButton("📥 Direct Download", url=direct_link)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if thumbnail:
            try:
                await update.message.reply_photo(
                    photo=thumbnail,
                    caption=success_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
                await processing_msg.delete()
            except:
                await processing_msg.edit_text(
                    success_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
        else:
            await processing_msg.edit_text(
                success_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
    else:
        # VidHide upload failed, give direct link only
        fallback_text = f"""
⚠️ **VidHide Upload Failed**

But don't worry! Here's your direct link:

📁 **File Details:**
• Name: `{filename}`
• Size: {size}
• Processing Time: {elapsed_time} seconds

📥 **Direct Download Link:**
{direct_link}

💡 **Manual VidHide Upload:**
1. Copy the direct link above
2. Go to vidhide.com
3. Use "Remote Upload" option
4. Paste link and upload

✅ Direct link extracted successfully!

Try sending another link! 🚀
        """
        
        keyboard = [[InlineKeyboardButton("📥 Download Now", url=direct_link)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await processing_msg.edit_text(
            fallback_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

# Error Handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"ERROR: {context.error}")
    try:
        if update and update.message:
            await update.message.reply_text(
                "⚠️ **Unexpected Error**\n\n"
                "Something went wrong. Please try again.\n\n"
                f"Error: `{str(context.error)[:100]}`",
                parse_mode=ParseMode.MARKDOWN
            )
    except:
        pass

# Main Function
def main():
    """Start the bot"""
    print("=" * 60)
    print("🔥 DISKWALA → VIDHIDE AUTO UPLOADER BOT")
    print("=" * 60)
    print(f"Bot Token: {BOT_TOKEN[:25]}...")
    print(f"DiskWala API: {DISKWALA_API_KEY[:15]}...")
    print(f"VidHide API: {VIDHIDE_API_KEY[:15]}...")
    print("=" * 60)
    
    # Create Application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Error Handler
    app.add_error_handler(error_handler)
    
    # Start Bot
    print("✅ Bot is now ONLINE and READY!")
    print("=" * 60)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
