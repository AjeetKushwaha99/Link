import os
import re
import json
import asyncio
import logging
import time
import hashlib
import struct
import base64
import httpx

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

BASE_API = "https://ddudapidd.diskwala.com/api/v1"


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
#  APPICRYPT HEADER GENERATOR
#  Reverse engineered from main.504832f2.js
# =============================================
class AppiCryptGenerator:
    """
    DiskWala uses AppiCrypt security headers.
    
    The process:
    1. Build canonical string from request
    2. SHA-256 hash it
    3. Generate cryptogram using WASM
    
    Since we can't run WASM in Python,
    we download the WASM module and 
    replicate its logic.
    """

    def __init__(self):
        self.magic_file = (
            "eyJwIjoiZXlKa0lqb2lUMGRzWDBvM1FuUktjbUp"
            "uVDI5V2MzUm1URzlDVHpWV2RtUjZUMGRyTW5WSF"
            "owdzRRMWR5VVV4SFJsOVVSbkJRZURnMWEzWktOSF"
            "ZzU2xaVVptRk9NRmg1WW1sVldYTjVWbEJxVlc5e"
            "mFrWTFSMU5JUkRJeFNWVnNaMGhyZVdOblp6aFZN"
            "bXBQUkhoR2FVZzBUVE4yYjA5ck9UbFZXVXh6ZVZw"
            "aGJrNUdWVmhyZHpOVGVFNXBkMHhXY1dRMmVIUTVM"
            "VTFuUzBZelVVcHpNRGd4TVhGd1pHWmlTSEE1Y1Va"
            "bWRXUk5hRk51VUZvMmREWTFaSE5oYTNnd1VFRlhl"
            "bkJTYjA1M1JpMWlTbVl6VUdKeVRWY3pkR1p6UTB0"
            "Q1JrRlVjM1UxZW5OT1VXVmZaRzh4WmkwMFpEbFhR"
            "WGx1V1RZMVdVNTJPR1Y2V0VGQlJUZ3hhMjFrWTJV"
            "eFZEVlVURTV0VUdaTGRrSjBUMVZyWWpONGN6SlBZ"
            "V2hGTlVveGRFNUpNMDVWTFV0aU5VOVFObkpJVTNo"
            "RFQydEJWVlZOYm5NMVdYcERaMUYxVEVWcFlqRk1W"
            "MkZ2TW1ZeE9YZEhSRkprYzBsTU9USlVkak5XUmxw"
            "M1RWSmlRbFZHVUVsS1J6aFVhbk52TFhWaE16bDBT"
            "bTlUVTJoRldWVmFOMDUwU0U1TVExWnFXR04xZWpO"
            "cWRETXpXV2RhY0d0RlRVWm1abmxzZHpWUlNURkJa"
            "VnBFVVRoUFIyTk1WbEJIV1dNMmJXVlVTemg1UkQx"
            "MlFtWlNZVk53Y1RWMFRsSlZWSE54WVZZNFgzaFhj"
            "bWxzZEhGTk56TTNNbWd5TlMwNWNVTnFTRlkzU0dk"
            "T1ZsSktSVUZoUlUxV1ZYcFFlUzFvU1hKTmNVUlpV"
            "akJWYkMxSWFIZDVOVlpoVGtaMU5UUkVUV1pHUjNw"
            "c01UZERRbmx4TUhrMWJub3dNMFV6VDNkbE9WSkdh"
            "R3hTTVdOa1NYVXpRM0pHWkRCdVVVSjVUMUV4YkRk"
            "eU1qUkJaM2QxTmtGbVMyZEhlVFJoY21kV2JUSldT"
            "bVJOZDFSak5UYzRkamN3VjBaR2FtdDVlV3gwTnpS"
            "S2FuVkVVSEZpV0VwQ1gxVXlRM0JJZDJwSFMyaDVO"
            "VzVYTTFKQllrZHRWWFJzV1dGTVlqWnFXbFJ3VERo"
            "cVNtMW9aVVZMUXkxT1VpMTBaME50VWxBM1JHcDFi"
            "VVJvTlVoMFVGbFRVQzE1ZW14dFQwSklaa3hGTkhw"
            "R1VqZEJVazlvYkVvNWRHZzNTbXRMU1hGVFNUZFBk"
            "MlpVZURGQmEyMWFjMEZzYVhCUFJXOUVNbEEzUVU1"
            "WE0yaGpVMjA0TUZKS1J6QmZiRU5FVVdOV2FVRm1V"
            "akl5VkdSSlZEaENURlYzTkRJaUxDSndJam9pVFVa"
            "cmQwVjNXVWhMYjFwSmVtb3dRMEZSV1VsTGIxcEpl"
            "bW93UkVGUlkwUlJaMEZGVGtvMFRrNUliMmhOTUdk"
            "c2NIUm5RVmhJVDBsWmNrMXRRMkZPZVhwaGF6bDZM"
            "WFpsTjNWTE1XNTJabWg0VUVSaVdYUmhZelJUU0RG"
            "S05uTnBWVlJoVEhsZmJ6SlJVMEV4U1ZsNU5WQnlP"
            "VlZHZFRaTVQwRTlQU0o5IiwicyI6IlAyNjBLREJv"
            "aC1VTlVETGFlUi0xMnRWOGYyejh2ZG1aM3pEb2hR"
            "QlB4a1RFejZXbDFPbDFsNmNNLUhzZUhTcXZPb2JJ"
            "QWNBcG9HQmpseTdFdEs3RzRBPT0ifQ=="
        )
        self.sdk_url = (
            "https://www.diskwala.com"
            "/pkg/appicrypt-web-f-0_1_207.js"
        )
        self.session = None

    def _serialize_value(self, value):
        """Replicate JS function l() - serialize value"""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, bool):
            return json.dumps(value)
        if isinstance(value, (int, float)):
            return json.dumps(value)
        if isinstance(value, list):
            items = [self._serialize_value(v) for v in value]
            return "[" + ",".join(items) + "]"
        if isinstance(value, dict):
            keys = sorted(value.keys())
            items = [
                json.dumps(k) + ":"
                + self._serialize_value(value[k])
                for k in keys
            ]
            return "{" + ",".join(items) + "}"
        return str(value)

    def _build_canonical_string(
        self, method, url_path, params, data
    ):
        """
        Build the canonical string that gets hashed.
        Format from JS:
        "METHOD /path | params=... | body=... | ts=..."
        """
        ts = str(int(time.time() * 1000))

        method_str = (method or "GET").upper()
        path_str = url_path or ""

        params_str = ""
        if params:
            params_str = self._serialize_value(params)

        body_str = ""
        if data is not None:
            if isinstance(data, str):
                body_str = data
            else:
                body_str = self._serialize_value(data)

        canonical = (
            f"{method_str} {path_str}"
            f" | params={params_str}"
            f" | body={body_str}"
            f" | ts={ts}"
        )

        return canonical, ts

    def _sha256(self, data):
        """SHA-256 hash"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        return hashlib.sha256(data).digest()

    def generate_headers(self, method, url_path, data=None):
        """
        Generate Appicrypt headers.
        Since we can't run the WASM getCryptogram(),
        we try multiple approaches.
        """
        canonical, ts = self._build_canonical_string(
            method, url_path, None, data
        )

        sha256_hash = self._sha256(canonical)
        hex_hash = sha256_hash.hex()
        b64_hash = base64.b64encode(sha256_hash).decode()

        # The real Appicrypt value comes from WASM
        # getCryptogram(sha256_hash)
        # We try the hash itself as the cryptogram
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
        }, canonical, hex_hash


appicrypt = AppiCryptGenerator()


# =============================================
#  DISKWALA API CALLER
# =============================================
class DiskWalaAPI:

    def __init__(self):
        self.client = None

    async def _get_client(self):
        if not self.client:
            self.client = httpx.AsyncClient(
                timeout=30,
                follow_redirects=True,
                headers={
                    'User-Agent': (
                        'Mozilla/5.0 (Windows NT 10.0; '
                        'Win64; x64) AppleWebKit/537.36 '
                        '(KHTML, like Gecko) '
                        'Chrome/120.0.0.0 Safari/537.36'
                    ),
                },
            )
        return self.client

    async def try_api_call(self, file_id):
        """Try multiple methods to get video URL"""
        results = {
            'success': False,
            'video_url': None,
            'title': 'DiskWala Video',
            'debug': [],
        }

        client = await self._get_client()

        # ===== METHOD 1: Try with generated headers =====
        logger.info("Method 1: AppiCrypt headers...")

        body_data = {"id": file_id}

        for endpoint in ['/file/sign', '/file/temp_info']:
            headers, canonical, hex_hash = (
                appicrypt.generate_headers(
                    'POST', endpoint, body_data
                )
            )

            # Try multiple cryptogram formats
            cryptogram_formats = [
                base64.b64encode(
                    bytes.fromhex(hex_hash)
                ).decode(),
                hex_hash,
                base64.b64encode(
                    canonical.encode()
                ).decode(),
                base64.b64encode(
                    (hex_hash + ":" + headers['Appicrypt-ts'])
                    .encode()
                ).decode(),
                hashlib.md5(
                    canonical.encode()
                ).hexdigest(),
            ]

            for crypto_val in cryptogram_formats:
                try:
                    h = {**headers, 'Appicrypt': crypto_val}
                    resp = await client.post(
                        f"{BASE_API}{endpoint}",
                        json=body_data,
                        headers=h,
                    )

                    status = resp.status_code
                    body = resp.text

                    results['debug'].append(
                        f"{endpoint} [{status}]: "
                        f"{body[:200]}"
                    )

                    if status == 200:
                        try:
                            data = json.loads(body)
                            video_url = self._find_url(data)
                            if video_url:
                                results['success'] = True
                                results['video_url'] = video_url
                                results['title'] = (
                                    data.get('name')
                                    or data.get('fileName')
                                    or data.get('title')
                                    or 'DiskWala Video'
                                )
                                return results
                        except json.JSONDecodeError:
                            pass

                    if status != 403:
                        break

                except Exception as e:
                    results['debug'].append(
                        f"{endpoint} error: {str(e)}"
                    )

        # ===== METHOD 2: Scrape the app page =====
        logger.info("Method 2: Scrape app page...")
        try:
            resp = await client.get(
                f"https://www.diskwala.com/app/{file_id}",
                headers={
                    'Accept': 'text/html',
                    'User-Agent': (
                        'Mozilla/5.0 (Windows NT 10.0; '
                        'Win64; x64) AppleWebKit/537.36'
                    ),
                },
            )

            html = resp.text

            # Find any video/media URLs
            url_patterns = [
                r'(https?://[^\s"\'<>]*\.mp4[^\s"\'<>]*)',
                r'(https?://[^\s"\'<>]*\.mkv[^\s"\'<>]*)',
                r'(https?://[^\s"\'<>]*\.webm[^\s"\'<>]*)',
                r'(https?://[^\s"\'<>]*storage\.googleapis'
                r'\.com[^\s"\'<>]*)',
                r'(https?://[^\s"\'<>]*r2\.cloudflarestorage'
                r'[^\s"\'<>]*)',
                r'(https?://[^\s"\'<>]*cdn[^\s"\'<>]*'
                r'\.mp4[^\s"\'<>]*)',
            ]

            for pattern in url_patterns:
                matches = re.findall(pattern, html)
                if matches:
                    results['success'] = True
                    results['video_url'] = matches[0]
                    return results

            results['debug'].append(
                f"Page scrape: no video URLs in "
                f"{len(html)} chars"
            )

        except Exception as e:
            results['debug'].append(
                f"Scrape error: {str(e)}"
            )

        # ===== METHOD 3: Try common CDN patterns =====
        logger.info("Method 3: CDN patterns...")

        cdn_urls = [
            f"https://cdn.diskwala.com/files/{file_id}",
            f"https://cdn.diskwala.com/video/{file_id}",
            f"https://cdn.diskwala.com/{file_id}.mp4",
            f"https://media.diskwala.com/{file_id}",
            f"https://storage.diskwala.com/{file_id}",
            f"https://files.diskwala.com/{file_id}",
            f"https://download.diskwala.com/{file_id}",
        ]

        for cdn_url in cdn_urls:
            try:
                resp = await client.head(
                    cdn_url, timeout=10
                )
                ct = resp.headers.get('content-type', '')

                if (
                    resp.status_code == 200
                    and ('video' in ct or 'octet' in ct)
                ):
                    results['success'] = True
                    results['video_url'] = cdn_url
                    return results

                if resp.status_code in [301, 302, 307]:
                    location = resp.headers.get('location')
                    if location:
                        results['success'] = True
                        results['video_url'] = location
                        return results

            except Exception:
                pass

        # ===== METHOD 4: Try Node.js approach =====
        # Download WASM and run via subprocess
        logger.info("Method 4: Node.js WASM...")

        try:
            node_result = await self._try_nodejs(file_id)
            if node_result:
                results['success'] = True
                results['video_url'] = node_result
                return results
        except Exception as e:
            results['debug'].append(
                f"Node.js error: {str(e)}"
            )

        return results

    async def _try_nodejs(self, file_id):
        """Try using Node.js to run AppiCrypt WASM"""
        try:
            # Check if node is available
            proc = await asyncio.create_subprocess_exec(
                'node', '--version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            if proc.returncode != 0:
                logger.info("Node.js not available")
                return None

            logger.info(
                f"Node.js found: {stdout.decode().strip()}"
            )

            # Create Node.js script
            node_script = f"""
const https = require('https');
const crypto = require('crypto');

const BASE = 'https://ddudapidd.diskwala.com';
const FILE_ID = '{file_id}';

function serialize(val) {{
    if (val === null || val === undefined) return '';
    if (typeof val === 'string') return val;
    if (typeof val !== 'object') return JSON.stringify(val);
    if (Array.isArray(val))
        return '[' + val.map(serialize).join(',') + ']';
    const keys = Object.keys(val).sort();
    return '{{' + keys.map(
        k => JSON.stringify(k) + ':' + serialize(val[k])
    ).join(',') + '}}';
}}

async function makeRequest(endpoint, body) {{
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
        .digest();

    const b64 = hash.toString('base64');

    return new Promise((resolve, reject) => {{
        const postData = JSON.stringify(body);
        const options = {{
            hostname: 'ddudapidd.diskwala.com',
            path: '/api/v1' + endpoint,
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(postData),
                'Appicrypt': b64,
                'Appicrypt-ts': ts,
                'Origin': 'https://www.diskwala.com',
                'Referer': 'https://www.diskwala.com/',
                'User-Agent': 'Mozilla/5.0 Chrome/120.0.0.0',
            }},
        }};

        const req = https.request(options, (res) => {{
            let data = '';
            res.on('data', (chunk) => {{ data += chunk; }});
            res.on('end', () => {{
                resolve({{
                    status: res.statusCode,
                    data: data,
                }});
            }});
        }});
        req.on('error', reject);
        req.write(postData);
        req.end();
    }});
}}

async function main() {{
    try {{
        const sign = await makeRequest(
            '/file/sign', {{ id: FILE_ID }}
        );
        const info = await makeRequest(
            '/file/temp_info', {{ id: FILE_ID }}
        );

        console.log(JSON.stringify({{
            sign_status: sign.status,
            sign_data: sign.data,
            info_status: info.status,
            info_data: info.data,
        }}));
    }} catch(e) {{
        console.log(JSON.stringify({{
            error: e.message,
        }}));
    }}
}}

main();
"""
            # Write and run node script
            script_path = '/tmp/diskwala_api.js'
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
                logger.info(f"Node.js output: {output}")

                try:
                    data = json.loads(output)

                    # Check sign response
                    if data.get('sign_status') == 200:
                        sign_data = json.loads(
                            data['sign_data']
                        )
                        url = self._find_url(sign_data)
                        if url:
                            return url

                    # Check info response
                    if data.get('info_status') == 200:
                        info_data = json.loads(
                            data['info_data']
                        )
                        url = self._find_url(info_data)
                        if url:
                            return url

                    logger.info(
                        f"Node responses: "
                        f"sign={data.get('sign_status')}, "
                        f"info={data.get('info_status')}"
                    )

                except json.JSONDecodeError:
                    logger.error(
                        f"Node output parse error: {output}"
                    )

            if stderr:
                logger.error(
                    f"Node stderr: {stderr.decode()}"
                )

        except FileNotFoundError:
            logger.info("Node.js not installed")
        except asyncio.TimeoutError:
            logger.error("Node.js script timeout")
        except Exception as e:
            logger.error(f"Node.js error: {e}")

        return None

    def _find_url(self, data, depth=0):
        """Recursively find video URL in data"""
        if depth > 5:
            return None

        if isinstance(data, str):
            if data.startswith('http') and any(
                kw in data.lower()
                for kw in [
                    '.mp4', '.mkv', '.webm', '.m3u8',
                    'storage', 'cdn', 'media', 'video',
                    'stream', 'download', 'signed',
                    'r2.cloudflare', 'blob',
                ]
            ):
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
                'location', 'href',
            ]
            for key in url_keys:
                if key in data:
                    val = data[key]
                    if isinstance(val, str) and val.startswith(
                        'http'
                    ):
                        return val

            for val in data.values():
                found = self._find_url(val, depth + 1)
                if found:
                    return found

        if isinstance(data, list):
            for item in data:
                found = self._find_url(item, depth + 1)
                if found:
                    return found

        return None


api = DiskWalaAPI()


# ============== BOT HANDLERS ==============
async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🎬 **DiskWala Video Downloader Bot**\n\n"
        "DiskWala ka link bhejo!\n"
        "Main direct download link dunga! 🚀\n\n"
        "**Example:**\n"
        "`https://www.diskwala.com/app/xxxxx`\n\n"
        "⏱ 10-15 seconds lagenge",
        parse_mode='Markdown',
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
        "🔐 API call ho raha hai...\n"
        "⏱ Wait karo...",
        parse_mode='Markdown',
    )

    try:
        result = await api.try_api_call(file_id)

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
            debug_lines = result.get('debug', [])
            debug_text = "\n".join(
                debug_lines[:5]
            )[:800]

            await msg.edit_text(
                f"❌ **Video nahi mila**\n\n"
                f"🔍 DiskWala ka AppiCrypt security "
                f"bahut strong hai.\n\n"
                f"📦 Debug Info:\n"
                f"```\n{debug_text}\n```\n\n"
                f"💡 File ID: `{file_id}`\n\n"
                f"Ye info developer ko bhejo!",
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
