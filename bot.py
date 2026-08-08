"""
🤖 ADVANCED BOT & HTML HOSTING BOT (Path & 404 Fix)
"""

import os
import sys
import json
import subprocess
import shutil
import secrets
import time
import threading
import zipfile
import mimetypes
import urllib.parse
from io import BytesIO
from pathlib import Path
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==================== CONFIGURATION ====================
TOKEN = "8173098705:AAHaFQDF4YA7QNBkAaWS2ku9JiuZuzj-8_Y"
OWNER_ID = 7472542379

BOTS_DIR = Path("hosted_bots")
BOTS_DIR.mkdir(exist_ok=True)

DB_FILE = Path("database.json")

# Render Domain Auto Detect
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:10000").rstrip("/")

# ==================== DATABASE MANAGEMENT ====================
def load_db() -> dict:
    if DB_FILE.exists():
        try:
            return json.loads(DB_FILE.read_text())
        except Exception:
            pass
    return {"users": {}, "bots": {}}

def save_db(db: dict):
    DB_FILE.write_text(json.dumps(db, indent=2))

# ==================== ENTRY FILE DETECTOR ====================
def find_entry_file(bot_dir: Path):
    priority_targets = ["index.html", "main.py", "bot.py", "app.py", "index.js", "bot.js", "server.js"]
    for target in priority_targets:
        found = list(bot_dir.rglob(target))
        if found:
            return found[0]

    all_files = [f for f in bot_dir.rglob("*") if f.is_file()]
    for f in all_files:
        if f.suffix in [".py", ".js", ".html", ".htm"]:
            return f
    return None

# ==================== WEB & HTML SERVER (FIXED PATH RESOLUTION) ====================
class CustomWebServer(BaseHTTPRequestHandler):
    def do_GET(self):
        # Clean query strings and URL encoding
        clean_path = urllib.parse.unquote(self.path.split('?')[0])

        if clean_path.startswith("/site/"):
            parts = clean_path.strip("/").split("/", 2)
            if len(parts) >= 2:
                bot_id = parts[1]
                rel_path = parts[2] if len(parts) > 2 else ""

                db = load_db()
                bot_info = db["bots"].get(bot_id)
                if bot_info:
                    bot_dir = Path(bot_info["path"])
                    target_file = None

                    if not rel_path or rel_path == "/":
                        target_file = find_entry_file(bot_dir)
                    else:
                        direct_file = bot_dir / rel_path
                        if direct_file.exists() and direct_file.is_file():
                            target_file = direct_file
                        else:
                            # Search subfolders automatically if path isn't flat
                            fname = Path(rel_path).name
                            found = list(bot_dir.rglob(fname))
                            if found:
                                target_file = found[0]

                    if target_file and target_file.exists() and target_file.is_file():
                        mime_type, _ = mimetypes.guess_type(str(target_file))
                        self.send_response(200)
                        self.send_header('Content-type', mime_type or 'text/html; charset=utf-8')
                        self.end_headers()
                        self.wfile.write(target_file.read_bytes())
                        return

            self.send_response(404)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b"404 Not Found - Website or File does not exist.")
            return

        # Default Keep-Alive Ping
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(b"<h1>Server is Live 24/7!</h1><p>Bot & HTML Hosting Engine Running.</p>")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    try:
        server = HTTPServer(('0.0.0.0', port), CustomWebServer)
        print(f"🌐 Server listening on port {port}")
        server.serve_forever()
    except Exception as e:
        print(f"Server warning: {e}")

threading.Thread(target=run_web_server, daemon=True).start()

# ==================== TELEGRAM BOT SETUP ====================
try:
    import telebot
    from telebot import types
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "pyTelegramBotAPI"])
    import telebot
    from telebot import types

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
RUNNING_PROCESSES = {}

def install_dependencies(bot_dir: Path):
    req_files = list(bot_dir.rglob("requirements.txt"))
    if req_files:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(req_files[0])],
                capture_output=True,
                text=True,
                timeout=60
            )
        except Exception as e:
            print(f"Req install error: {e}")

# ==================== PROCESS CONTROL ====================
def start_hosted_bot(bid: str) -> str:
    db = load_db()
    bot_info = db["bots"].get(bid)
    if not bot_info:
        return "❌ হোস্টিং খুঁজে পাওয়া যায়নি!"

    bot_dir = Path(bot_info["path"])
    if not bot_dir.exists():
        return "❌ ফোল্ডারটি মিসিং!"

    entry_path = find_entry_file(bot_dir)
    if not entry_path:
        return "❌ কোনো রান করার মতো ফাইল পাওয়া যায়নি!"

    if entry_path.suffix in [".html", ".htm"]:
        return "🌐 এটি একটি HTML ওয়েবসাইট। এটি অটোমেটিক ২৪/৭ লাইভ আছে!"

    install_dependencies(bot_dir)

    is_python = entry_path.suffix == ".py"
    cmd = [sys.executable, entry_path.name] if is_python else ["node", entry_path.name]

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(entry_path.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        RUNNING_PROCESSES[bid] = {
            "process": proc,
            "logs": [f"🚀 Starting {entry_path.name}..."],
            "started": time.time()
        }

        def capture_logs():
            for line in iter(proc.stdout.readline, ""):
                if bid in RUNNING_PROCESSES:
                    RUNNING_PROCESSES[bid]["logs"].append(line.strip())
                    if len(RUNNING_PROCESSES[bid]["logs"]) > 150:
                        RUNNING_PROCESSES[bid]["logs"].pop(0)

        threading.Thread(target=capture_logs, daemon=True).start()
        return "🟢 বট সফলভাবে চালু হয়েছে!"
    except Exception as e:
        return f"❌ চালু করতে ব্যর্থ: {str(e)}"

def stop_hosted_bot(bid: str) -> str:
    if bid in RUNNING_PROCESSES:
        try:
            proc = RUNNING_PROCESSES[bid]["process"]
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                RUNNING_PROCESSES[bid]["process"].kill()
            except Exception:
                pass
        del RUNNING_PROCESSES[bid]
        return "🔴 প্রসেস বন্ধ করা হয়েছে।"
    return "⚠️ প্রসেসটি ইতিপূর্বে বন্ধ ছিল।"

def get_hosted_logs(bid: str) -> str:
    if bid in RUNNING_PROCESSES:
        logs = RUNNING_PROCESSES[bid].get("logs", [])
        return "\n".join(logs[-25:]) if logs else "লগ লোড হচ্ছে..."
    return "⚠️ কোনো রানিং লগ নেই।"

# ==================== KEYBOARDS ====================
def main_menu_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🤖 My Uploads", callback_data="menu_my_bots"),
        types.InlineKeyboardButton("📤 Upload File", callback_data="menu_upload")
    )
    kb.add(
        types.InlineKeyboardButton("👤 Profile", callback_data="menu_profile")
    )
    return kb

def bot_control_kb(bid: str, is_html: bool, web_url: str = "") -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)

    if is_html:
        kb.add(types.InlineKeyboardButton("🌐 Open Website", url=web_url))
    else:
        is_running = bid in RUNNING_PROCESSES and RUNNING_PROCESSES[bid]["process"].poll() is None
        if is_running:
            kb.add(types.InlineKeyboardButton("⏹️ Stop Bot", callback_data=f"act_stop_{bid}"))
        else:
            kb.add(types.InlineKeyboardButton("▶️ Start Bot", callback_data=f"act_start_{bid}"))
        kb.add(types.InlineKeyboardButton("📋 View Logs", callback_data=f"act_logs_{bid}"))

    kb.add(types.InlineKeyboardButton("🗑️ Delete", callback_data=f"act_del_{bid}"))
    kb.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main"))
    return kb

# ==================== BOT HANDLERS ====================
@bot.message_handler(commands=['start'])
def cmd_start(m: types.Message):
    db = load_db()
    suid = str(m.from_user.id)
    if suid not in db["users"]:
        db["users"][suid] = {"plan": "free", "bots": [], "joined": str(datetime.now())}
        save_db(db)

    text = (
        f"👋 **Hello {m.from_user.first_name}!**\n\n"
        f"🤖 **Bot & HTML Hosting Panel**\n"
        f"• Python/Node.js বট ব্যাকগ্রাউন্ডে রান করুন\n"
        f"• HTML ফাইল আপলোড করে অটো লাইভ ওয়েবসাইট লিংক বানিয়ে নিন\n\n"
        f"📤 আপলোড করতে `.zip`, `.py`, `.js` অথবা `.html` ফাইল সেন্ড করুন।"
    )
    bot.send_message(m.chat.id, text, reply_markup=main_menu_kb())

@bot.message_handler(content_types=['document'])
def handle_file_upload(m: types.Message):
    uid = m.from_user.id
    suid = str(uid)
    db = load_db()

    if suid not in db["users"]:
        db["users"][suid] = {"plan": "free", "bots": [], "joined": str(datetime.now())}

    user = db["users"][suid]
    limit = {"free": 5, "premium": 15}.get(user.get("plan", "free"), 5)

    if len(user.get("bots", [])) >= limit:
        bot.reply_to(m, "❌ আপলোড লিমিট শেষ!")
        return

    doc = m.document
    fname = doc.file_name.lower()
    allowed_exts = ('.zip', '.py', '.js', '.html', '.htm')
    if not fname.endswith(allowed_exts):
        bot.reply_to(m, "❌ শুধুমাত্র `.zip`, `.py`, `.js` অথবা `.html` ফাইল গ্রহণযোগ্য।")
        return

    msg = bot.reply_to(m, "⏳ ফাইল প্রসেস করা হচ্ছে...")

    try:
        file_info = bot.get_file(doc.file_id)
        file_bytes = bot.download_file(file_info.file_path)

        bot_id = secrets.token_hex(4)
        bot_dir = BOTS_DIR / bot_id
        bot_dir.mkdir(parents=True, exist_ok=True)

        if fname.endswith('.zip'):
            with zipfile.ZipFile(BytesIO(file_bytes)) as zf:
                zf.extractall(bot_dir)
        else:
            (bot_dir / doc.file_name).write_bytes(file_bytes)

        entry = find_entry_file(bot_dir)
        if not entry:
            shutil.rmtree(bot_dir, ignore_errors=True)
            bot.edit_message_text("❌ ফাইলে উপযোগী কোনো কোড ফাইল পাওয়া যায়নি!", chat_id=m.chat.id, message_id=msg.message_id)
            return

        is_html = entry.suffix in [".html", ".htm"]
        rel_entry_path = entry.relative_to(bot_dir).as_posix()
        web_url = f"{BASE_URL}/site/{bot_id}/{rel_entry_path}"

        db["bots"][bot_id] = {
            "name": doc.file_name,
            "path": str(bot_dir),
            "owner": uid,
            "is_html": is_html,
            "web_url": web_url,
            "uploaded": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        db["users"][suid]["bots"].append(bot_id)
        save_db(db)

        if is_html:
            reply_text = (
                f"✅ **HTML ওয়েবসাইট হোস্টিং সফল!**\n\n"
                f"📁 **File:** `{doc.file_name}`\n"
                f"🌐 **Hosted URL:**\n`{web_url}`"
            )
        else:
            reply_text = (
                f"✅ **কোড আপলোড সফল হয়েছে!**\n\n"
                f"📁 **File:** `{doc.file_name}`\n"
                f"📄 **Entry Point:** `{entry.name}`\n\n"
                f"বট স্টার্ট করতে **My Uploads** অপশনে যান।"
            )

        bot.edit_message_text(
            reply_text,
            chat_id=m.chat.id,
            message_id=msg.message_id,
            reply_markup=main_menu_kb()
        )

    except Exception as e:
        bot.edit_message_text(f"❌ প্রসেসিং ব্যর্থ: {str(e)}", chat_id=m.chat.id, message_id=msg.message_id)

@bot.callback_query_handler(func=lambda c: True)
def handle_callbacks(c: types.CallbackQuery):
    data = c.data
    uid = c.from_user.id
    suid = str(uid)
    chat_id = c.message.chat.id

    if data == "menu_main":
        bot.edit_message_text("🤖 **Main Control Panel**", chat_id=chat_id, message_id=c.message.message_id, reply_markup=main_menu_kb())

    elif data == "menu_my_bots":
        db = load_db()
        user_bots = db["users"].get(suid, {}).get("bots", [])

        if not user_bots:
            bot.answer_callback_query(c.id, "আপনার কোনো আপলোড করা ফাইল নেই!", show_alert=True)
            return

        kb = types.InlineKeyboardMarkup(row_width=1)
        for bid in user_bots:
            if bid in db["bots"]:
                binfo = db["bots"][bid]
                bname = binfo["name"]
                if binfo.get("is_html"):
                    status = "🌐"
                else:
                    is_running = bid in RUNNING_PROCESSES and RUNNING_PROCESSES[bid]["process"].poll() is None
                    status = "🟢" if is_running else "🔴"
                kb.add(types.InlineKeyboardButton(f"{status} {bname}", callback_data=f"select_{bid}"))

        kb.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main"))
        bot.edit_message_text("🤖 **আপনার আপলোড করা প্রজেক্টসমূহ:**", chat_id=chat_id, message_id=c.message.message_id, reply_markup=kb)

    elif data == "menu_upload":
        bot.send_message(chat_id, "📤 আপনার `.py`, `.js`, `.html` অথবা ওয়েবসাইট/বটের `.zip` ফাইল সেন্ড করুন।")
        bot.answer_callback_query(c.id)

    elif data == "menu_profile":
        db = load_db()
        user = db["users"].get(suid, {})
        bot.edit_message_text(
            f"👤 **User Profile**\n\n"
            f"🆔 **ID:** `{uid}`\n"
            f"📦 **Total Hosted:** {len(user.get('bots', []))}\n"
            f"📅 **Joined:** {user.get('joined', '')[:10]}",
            chat_id=chat_id,
            message_id=c.message.message_id,
            reply_markup=main_menu_kb()
        )

    elif data.startswith("select_"):
        bid = data[7:]
        db = load_db()
        bot_info = db["bots"].get(bid)

        if not bot_info:
            bot.answer_callback_query(c.id, "তথ্য পাওয়া যায়নি!")
            return

        is_html = bot_info.get("is_html", False)
        web_url = bot_info.get("web_url", "")

        if is_html:
            status_text = f"🌐 **Live Website**\n\n🔗 **URL:** `{web_url}`"
        else:
            is_running = bid in RUNNING_PROCESSES and RUNNING_PROCESSES[bid]["process"].poll() is None
            status = "🟢 Running" if is_running else "🔴 Stopped"
            status_text = f"📊 **Status:** {status}"

        bot.edit_message_text(
            f"⚙️ **Project Details**\n\n"
            f"📛 **Name:** `{bot_info['name']}`\n"
            f"{status_text}\n"
            f"📅 **Uploaded:** {bot_info.get('uploaded', 'N/A')}",
            chat_id=chat_id,
            message_id=c.message.message_id,
            reply_markup=bot_control_kb(bid, is_html, web_url)
        )

    elif data.startswith("act_start_"):
        bid = data[10:]
        res = start_hosted_bot(bid)
        bot.answer_callback_query(c.id, res)
        db = load_db()
        bot_info = db["bots"].get(bid)
        if bot_info:
            bot.edit_message_text(f"⚙️ **Project Details**\n\n📛 **Name:** `{bot_info['name']}`\n📊 **Status:** 🟢 Running", chat_id=chat_id, message_id=c.message.message_id, reply_markup=bot_control_kb(bid, False))

    elif data.startswith("act_stop_"):
        bid = data[9:]
        res = stop_hosted_bot(bid)
        bot.answer_callback_query(c.id, res)
        db = load_db()
        bot_info = db["bots"].get(bid)
        if bot_info:
            bot.edit_message_text(f"⚙️ **Project Details**\n\n📛 **Name:** `{bot_info['name']}`\n📊 **Status:** 🔴 Stopped", chat_id=chat_id, message_id=c.message.message_id, reply_markup=bot_control_kb(bid, False))

    elif data.startswith("act_logs_"):
        bid = data[9:]
        logs = get_hosted_logs(bid)
        bot.send_message(chat_id, f"📋 **Console Logs ({bid}):**\n\n<pre>{logs[:3800]}</pre>")

    elif data.startswith("act_del_"):
        bid = data[8:]
        stop_hosted_bot(bid)
        db = load_db()
        if bid in db["bots"]:
            shutil.rmtree(db["bots"][bid]["path"], ignore_errors=True)
            del db["bots"][bid]
            if suid in db["users"] and bid in db["users"][suid]["bots"]:
                db["users"][suid]["bots"].remove(bid)
            save_db(db)
        bot.answer_callback_query(c.id, "🗑️ সফলভাবে মুছে ফেলা হয়েছে!")
        bot.edit_message_text("🤖 **Main Control Panel**", chat_id=chat_id, message_id=c.message.message_id, reply_markup=main_menu_kb())

    bot.answer_callback_query(c.id)

# ==================== START POLLING ====================
if __name__ == "__main__":
    print("🤖 Bot & HTML Hosting Engine Started!")
    try:
        bot.delete_webhook()
    except Exception:
        pass
    bot.infinity_polling(skip_pending=True)
