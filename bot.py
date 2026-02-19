# bot.py - ULTIMATE WORKING VERSION 2025

import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8526618009:AAHoS3k_iH5IsQh76JAKeMkzZcFyh7RYsCs"

# BEST WORKING API 2025
def get_direct_link(url):
    api_url = "https://terabox-dl.qtcloud.workers.dev/api/get-info"
    
    try:
        response = requests.get(f"{api_url}?url={url}", timeout=40)
        data = response.json()
        
        if data.get("ok") and data.get("list"):
            file = data["list"][0]
            size_mb = file.get("size", 0) / (1024 * 1024)
            
            return {
                "success": True,
                "direct_link": file.get("dlink"),
                "filename": file.get("server_filename", "Unknown"),
                "size": f"{size_mb:.2f} MB",
                "thumb": file.get("thumbs", {}).get("url3")
            }
    except Exception as e:
        print(e)
    
    return {"success": False}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    # Supported domains
    domains = ["terabox", "1024terabox", "terasharefile", "4funbox", "nephobox", "teraboxapp"]
    
    if not any(d in url.lower() for d in domains):
        await update.message.reply_text("❌ Invalid link! Only TeraBox links allowed.")
        return
    
    msg = await update.message.reply_text("🔥 Cracking link using premium API...")
    
    result = get_direct_link(url)
    
    if result.get("success"):
        text = f"""
✅ **DIRECT LINK MIL GAYA!**

📁 **File:** `{result['filename']}`
📦 **Size:** {result['size']}

🔗 **Download Link:**
`{result['direct_link']}`

💡 Ab isko VidHide pe remote upload kar do!
        """
        await msg.edit_text(text, parse_mode="Markdown")
    else:
        await msg.edit_text(
            "❌ **Failed to extract link**\n\n"
            "Possible reasons:\n"
            "• Link expired hai\n"
            "• Password protected hai\n"
            "• File delete ho gaya\n\n"
            "Koi aur link try karo!"
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 **TERABOX DIRECT LINK BOT 2025**\n\n"
        "Bhejo koi bhi link:\n"
        "• terasharefile.com\n"
        "• 1024terabox.com\n"
        "• terabox.com/s/xxx\n\n"
        "Main direct download link dunga!\n\n"
        "Bas link bhejo, baaki main sambhal lunga 😈"
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("ULTIMATE TERABOX BOT STARTED - 2025 READY!")
    app.run_polling()

if __name__ == "__main__":
    main()
