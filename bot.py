import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8526618009:AAHoS3k_iH5IsQh76JAKeMkzZcFyh7RYsCs"

def convert_diskwala_to_direct(diskwala_url):
    # Extract share code
    import re
    match = re.search(r'/s/([a-zA-Z0-9_-]+)', diskwala_url)
    if not match:
        return None
    
    share_code = match.group(1)
    
    # Convert to real TeraBox link
    terabox_url = f"https://www.terabox.com/s/{share_code}"
    
    # Use working TeraBox API
    api = "https://terabox-dl.qtcloud.workers.dev/api/get-info"
    response = requests.get(api, params={"url": terabox_url}, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("ok") and data.get("list"):
            file = data["list"][0]
            size = file.get("size", 0) / (1024*1024)
            return {
                "direct_link": file.get("dlink"),
                "filename": file.get("server_filename"),
                "size": f"{size:.2f} MB"
            }
    
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if "diskwala" not in url.lower():
        await update.message.reply_text("Send DiskWala link only!")
        return
    
    msg = await update.message.reply_text("Converting DiskWala → Direct Link...")
    
    result = convert_diskwala_to_direct(url)
    
    if result:
        await msg.edit_text(
            f"**SUCCESS!**\n\n"
            f"File: `{result['filename']}`\n"
            f"Size: {result['size']}\n\n"
            f"Direct Link:\n`{result['direct_link']}`",
            parse_mode="Markdown"
        )
    else:
        await msg.edit_text("Failed! Try another link.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "**DiskWala Direct Link Bot**\n\n"
        "Send me any DiskWala link!\n"
        "Example: https://diskwala.com/s/xxxxx",
        parse_mode="Markdown"
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
