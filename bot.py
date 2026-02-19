# bot.py - FINAL WORKING VERSION (No Cookies Needed!)

import os
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8526618009:AAHoS3k_iH5IsQh76JAKeMkzZcFyh7RYsCs"

# Auto convert any wrapper to real TeraBox link
def convert_to_real_link(url):
    patterns = [
        r'(?:terasharefile\.com|1024terabox\.com|4funbox\.co|nephobox\.com)/s/([a-zA-Z0-9_-]+)',
        r'terabox\.app/s/([a-zA-Z0-9_-]+)',
        r'terabox\.com/s/([a-zA-Z0-9_-]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            code = match.group(1)
            real_link = f"https://www.terabox.com/s/{code}"
            return real_link, code
    return None, None

# Get direct download link (works on converted links)
def get_direct_link(terabox_url):
    try:
        # Best working API (Jan 2025)
        api = "https://terabox-dl.qtcloud.workers.dev/api/get-info"
        response = requests.get(api, params={"url": terabox_url}, timeout=30)
        data = response.json()
        
        if data.get("ok"):
            file = data["list"][0]
            return {
                "success": True,
                "direct_link": file.get("dlink"),
                "filename": file.get("server_filename"),
                "size": f"{file.get('size',0)/(1024*1024):.2f} MB"
            }
    except:
        pass
    return {"success": False}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    real_link, code = convert_to_real_link(url)
    
    if not real_link:
        await update.message.reply_text("❌ Invalid or unsupported link!")
        return
        
    msg = await update.message.reply_text(
        f"🔄 Converting...\n"
        f"🔗 Detected: Wrapper link\n"
        f"✅ Converted →\n`{real_link}`",
        parse_mode="Markdown"
    )
    
    await msg.edit_text("⏳ Extracting direct download link...")
    
    result = get_direct_link(real_link)
    
    if result.get("success"):
        await msg.edit_text(
            f"✅ **SUCCESS!**\n\n"
            f"📁 **File:** `{result['filename']}`\n"
            f"📦 **Size:** {result['size']}\n\n"
            f"🔗 **Direct Download Link:**\n`{result['direct_link']}`\n\n"
            f"💡 Ab isko VidHide pe daal do!",
            parse_mode="Markdown"
        )
    else:
        await msg.edit_text(
            f"✅ **Link Converted!**\n\n"
            f"🔗 **Real TeraBox Link:**\n`{real_link}`\n\n"
            f"⚠️ Direct link nahi mila, lekin ye link ab normal TeraBox hai\n"
            f"Ab kisi bhi bot mein daal do ya manually download karo!",
            parse_mode="Markdown"
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 **Wrapper to Real TeraBox Converter**\n\n"
        "Send any link:\n"
        "• terasharefile.com\n"
        "• 1024terabox.com\n"
        "• 4funbox.co\n"
        "• terabox.com/s/xxx\n\n"
        "I will convert it to real working link! 😈"
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Wrapper Killer Bot Started!")
    app.run_polling()

import requests
if __name__ == "__main__":
    main()
