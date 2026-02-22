import os
import re
import json
import asyncio
import logging
import time
import hashlib
import base64
import requests

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

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
BASE_API = "https://ddudapidd.diskwala.com/api/v1"

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


def serialize_value(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return json.dumps(value)
    if isinstance(value, (int, float)):
        return json.dumps(value)
    if isinstance(value, list):
        items = [serialize_value(v) for v in value]
        return "[" + ",".join(items) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys())
        items = [
            json.dumps(k) + ":"
            + serialize_value(value[k])
            for k in keys
        ]
        return "{" + ",".join(items) + "}"
    return str(value)


def generate_headers(method, url_path, data=None):
    ts = str(int(time.time() * 1000))
    method_str = (method or "GET").upper()
    path_str = url_path or ""

    body_str = ""
    if data is not None:
        body_str = serialize_value(data)

    canonical = (
        f"{method_str} {path_str}"
        f" | params="
        f" | body={body_str}"
        f" | ts={ts}"
    )

    sha256_hash = hashlib.sha256(
        canonical.encode('utf-8')
    ).digest()

    b64_hash = base64.b64encode(sha256_hash).decode()

    return {
        'Content-Type': 'application/json',
        'Appicrypt': b64_hash,
        'Appicrypt-ts': ts,
        'Origin': 'https://www.diskwala.com',
        'Referer': 'https://www.diskwala.com/',
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
    }


def find_url(data, depth=0):
    if depth > 5:
        return None
    if isinstance(data, str):
        if data.startswith('http'):
            return data
        return None
    if isinstance(data, dict):
        url_keys = [
            'url', 'signedUrl', 'signed_url',
            'downloadUrl', 'download_url',
            'videoUrl', 'video_url',
            'link', 'fileUrl', 'file_url',
            'streamUrl', 'stream_url',
            'src', 'source', 'path',
        ]
        for key in url_keys:
            if key in data:
                val = data[key]
                if isinstance(val, str) and \
                   val.startswith('http'):
                    return val
        for val in data.values():
            found = find_url(val, depth + 1)
            if found:
                return found
    if isinstance(data, list):
        for item in data:
            found = find_url(item, depth + 1)
            if found:
                return found
    return None


async def call_api(file_id):
    result = {
        'success': False,
        'video_url': None,
        'title': 'DiskWala Video',
        'debug': [],
    }

    body_data = {"id": file_id}

    # Method 1: Python requests with headers
    for endpoint in ['/file/sign', '/file/temp_info']:
        headers = generate_headers(
            'POST', endpoint, body_data
        )

        hex_hash = hashlib.sha256(
            (headers['Appicrypt']).encode()
        ).hexdigest()

        formats = [
            headers['Appicrypt'],
            hex_hash,
            hashlib.md5(
                headers['Appicrypt'].encode()
            ).hexdigest(),
        ]

        for crypto_val in formats:
            try:
                h = {**headers, 'Appicrypt': crypto_val}
                resp = requests.post(
                    f"{BASE_API}{endpoint}",
                    json=body_data,
                    headers=h,
                    timeout=15,
                )

                result['debug'].append(
                    f"{endpoint} [{resp.status_code}]:"
                    f" {resp.text[:200]}"
                )

                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        video_url = find_url(data)
                        if video_url:
                            result['success'] = True
                            result['video_url'] = video_url
                            result['title'] = (
                                data.get('name')
                                or data.get('fileName')
                                or data.get('title')
                                or 'DiskWala Video'
                            )
                            return result
                    except json.JSONDecodeError:
                        pass

                if resp.status_code != 403:
                    break

            except Exception as e:
                result['debug'].append(
                    f"{endpoint} error: {str(e)}"
                )

    # Method 2: Node.js with WASM
    try:
        node_result = await try_nodejs(file_id)
        if node_result:
            result['success'] = True
            result['video_url'] = node_result
            return result
    except Exception as e:
        result['debug'].append(f"Node: {str(e)}")

    return result


async def try_nodejs(file_id):
    try:
        proc = await asyncio.create_subprocess_exec(
            'node', '--version',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return None

        node_script = """
const https = require('https');
const crypto = require('crypto');
const FILE_ID = '""" + file_id + """';

function serialize(val) {
    if (val === null || val === undefined) return '';
    if (typeof val === 'string') return val;
    if (typeof val !== 'object')
        return JSON.stringify(val);
    if (Array.isArray(val))
        return '[' + val.map(serialize).join(',') + ']';
    const keys = Object.keys(val).sort();
    return '{' + keys.map(
        k => JSON.stringify(k) + ':' + serialize(val[k])
    ).join(',') + '}';
}

function makeReq(endpoint, body) {
    return new Promise((resolve, reject) => {
        const ts = Date.now().toString();
        const bodyStr = serialize(body);
        const canonical =
            'POST ' + endpoint
            + ' | params='
            + ' | body=' + bodyStr
            + ' | ts=' + ts;
        const hash = crypto
            .createHash('sha256')
            .update(canonical)
            .digest('base64');
        const postData = JSON.stringify(body);
        const options = {
            hostname: 'ddudapidd.diskwala.com',
            path: '/api/v1' + endpoint,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length':
                    Buffer.byteLength(postData),
                'Appicrypt': hash,
                'Appicrypt-ts': ts,
                'Origin': 'https://www.diskwala.com',
                'Referer': 'https://www.diskwala.com/',
                'User-Agent':
                    'Mozilla/5.0 Chrome/120.0.0.0',
            },
        };
        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', (c) => { data += c; });
            res.on('end', () => {
                resolve({
                    status: res.statusCode,
                    data: data,
                });
            });
        });
        req.on('error', reject);
        req.write(postData);
        req.end();
    });
}

async function main() {
    try {
        const s = await makeReq(
            '/file/sign', { id: FILE_ID }
        );
        const i = await makeReq(
            '/file/temp_info', { id: FILE_ID }
        );
        console.log(JSON.stringify({
            sign_status: s.status,
            sign_data: s.data,
            info_status: i.status,
            info_data: i.data,
        }));
    } catch(e) {
        console.log(JSON.stringify({
            error: e.message,
        }));
    }
}
main();
"""
        script_path = '/tmp/dw_api.js'
        with open(script_path, 'w') as f:
            f.write(node_script)

        proc = await asyncio.create_subprocess_exec(
            'node', script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=15
        )

        if proc.returncode == 0 and stdout:
            output = stdout.decode().strip()
            logger.info(f"Node output: {output}")
            data = json.loads(output)

            if data.get('sign_status') == 200:
                sign = json.loads(data['sign_data'])
                url = find_url(sign)
                if url:
                    return url

            if data.get('info_status') == 200:
                info = json.loads(data['info_data'])
                url = find_url(info)
                if url:
                    return url

    except Exception as e:
        logger.error(f"Node error: {e}")

    return None


async def start(update, context):
    await update.message.reply_text(
        "🎬 **DiskWala Video Downloader**\n\n"
        "DiskWala link bhejo!\n\n"
        "**Example:**\n"
        "`https://www.diskwala.com/app/xxxxx`",
        parse_mode='Markdown',
    )


async def process_link(update, context):
    text = update.message.text.strip()
    file_id = extract_file_id(text)

    if not file_id:
        await update.message.reply_text(
            "❌ Valid link nahi!\n"
            "`https://www.diskwala.com/app/xxxxx`",
            parse_mode='Markdown',
        )
        return

    msg = await update.message.reply_text(
        "⏳ Processing... wait karo...",
    )

    try:
        result = await call_api(file_id)

        if result['success'] and result['video_url']:
            video_url = result['video_url']
            title = result.get('title', 'DiskWala Video')

            keyboard = []
            if video_url.startswith('http'):
                keyboard.append([
                    InlineKeyboardButton(
                        "⬇️ Download",
                        url=video_url,
                    )
                ])

            await msg.edit_text(
                f"✅ **Video Found!**\n\n"
                f"📹 {title}\n\n"
                f"🔗 Link:\n`{video_url}`",
                parse_mode='Markdown',
                reply_markup=(
                    InlineKeyboardMarkup(keyboard)
                    if keyboard else None
                ),
            )
        else:
            debug = "\n".join(
                result.get('debug', [])[:5]
            )[:600]

            await msg.edit_text(
                f"❌ **Video nahi mila**\n\n"
                f"Debug:\n```\n{debug}\n```\n\n"
                f"File ID: `{file_id}`",
                parse_mode='Markdown',
            )

    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")


async def handle_message(update, context):
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
        print("BOT_TOKEN not set!")
        return
    print("Starting bot...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )
    print("Bot running!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
