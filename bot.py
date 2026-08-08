"""
🤖 ADVANCED TELEGRAM BOT HOSTING BOT (Render Compatible)
সব ধরণের Python/Node.js টেলিগ্রাম বট অটোমেটিক প্যাকেজ ইনস্টলসহ হোস্ট করার বট
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

# ==================== RENDER DUMMY WEB SERVER ====================
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot Hosting Panel is Live 24/7!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    try:
        server = HTTPServer(('0.0.0.0', port), DummyHandler)
        print(f"🌐 Keep-Alive server listening on port {port}")
        server.serve_forever()
    except Exception as e:
        print(f"Server warning: {e}")

threading.Thread(target=run_dummy_server, daemon=True).start()

# ==================== DATABASE MANAGEMENT ====================
def load_db() -> dict:
    if DB_FILE.exists():
        try:
            return json.loads(DB_FILE.read_text())
        except:
            pass
    return {"users": {}, "bots": {}}

def save_db(db: dict):
    DB_FILE.write_text(json.dumps(db, indent=2))

# ==================== TELEGRAM BOT INITIALIZATION ====================
try:
    import telebot
    from telebot import types
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "pyTelegramBotAPI"])
    import telebot
    from telebot import types

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
RUNNING_PROCESSES = {}

# ==================== HELPER FUNCTIONS ====================
def get_user(uid: int) -> dict:
    db = load_db()
    suid = str(uid)
    if suid not in db["users"]:
        db["users"][suid] = {"plan": "free", "bots": [], "joined": str(datetime.now())}
        save_db(db)
    return db["users"][suid]

def can_create_bot(uid: int) -> bool:
    user = get_user(uid)
    limit = {"free": 3, "premium": 10, "pro": 25}.get(user.get("plan", "free"), 3)
    return len(user.get("bots", [])) < limit

def find_entry_file(bot_dir: Path):
    """ফোল্ডারের ভেতরে যেকোনো জায়গায় মেইন ফাইল খুঁজে বের করে"""
    targets = ["main.py", "bot.py", "app.py", "index.js", "bot.js", "server.js"]
    for target in targets:
        found = list(bot_dir.rglob(target))
        if found:
            return found[0]  # Return absolute Path object
    return None

def install_dependencies(bot_dir: Path):
    """আপলোড করা বটের requirements.txt থাকলে অটো ইনস্টল করে"""
    req_files = list(bot_dir.rglob("requirements.txt"))
    if req_files:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(req_files[0])],
                capture_output=True,
                text=True,
                timeout=60
            )
            return True
        except Exception as e:
            print(f"Req install error: {e}")
    return False

# ==================== PROCESS CONTROL ====================
def start_hosted_bot(bid: str) -> str:
    db = load_db()
    bot_info = db["bots"].get(bid)
    if not bot_info:
        return "❌ বট খুঁজে পাওয়া যায়নি!"

    bot_dir = Path(bot_info["path"])
    if not bot_dir.exists():
        return "❌ বটের ফোল্ডারটি মিসিং!"

    entry_path = find_entry_file(bot_dir)
    if not entry_path:
        return "❌ কোনো মেইন ফাইল পাওয়া যায়নি! (main.py, bot.py, index.js ইত্যাদি থাকা আবশ্যক)"

    # ইনস্টল ডিপেনডেন্সি
    install_dependencies(bot_dir)

    # ফাইলটাইপ অনুযায়ী রান কমান্ড
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

        # ব্যাকগ্রাউন্ডে লগ রিডার
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
        except:
            try:
                RUNNING_PROCESSES[bid]["process"].kill()
            except:
                pass
        del RUNNING_PROCESSES[bid]
        return "🔴 বট বন্ধ করা হয়েছে।"
    return "⚠️ বটটি ইতিপূর্বে বন্ধ ছিল।"

def get_hosted_logs(bid: str) -> str:
    if bid in RUNNING_PROCESSES:
        logs = RUNNING_PROCESSES[bid].get("logs", [])
        if not logs:
            return "লগ লোড হচ্ছে..."
        return "\n".join(logs[-25:])
    return "⚠️ বট বন্ধ রয়েছে। কোনো রানিং লগ নেই।"

# ==================== KEYBOARDS ====================
def main_menu_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🤖 My Bots", callback_data="menu_my_bots"),
        types.InlineKeyboardButton("📤 Upload Bot", callback_data="menu_upload")
    )
    kb.add(
        types.InlineKeyboardButton("👤 Profile", callback_data="menu_profile"),
        types.InlineKeyboardButton("💳 Plans", callback_data="menu_plans")
    )
    return kb

def bot_control_kb(bid: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    is_running = bid in RUNNING_PROCESSES and RUNNING_PROCESSES[bid]["process"].poll() is None

    if is_running:
        kb.add(types.InlineKeyboardButton("⏹️ Stop Bot", callback_data=f"act_stop_{bid}"))
    else:
        kb.add(types.InlineKeyboardButton("▶️ Start Bot", callback_data=f"act_start_{bid}"))

    kb.add(
        types.InlineKeyboardButton("📋 View Logs", callback_data=f"act_logs_{bid}"),
        types.InlineKeyboardButton("🗑️ Delete", callback_data=f"act_del_{bid}")
    )
    kb.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main"))
    return kb

# ==================== BOT HANDLERS ====================
@bot.message_handler(commands=['start'])
def cmd_start(m: types.Message):
    get_user(m.from_user.id)
    text = (
        f"👋 **Hello {m.from_user.first_name}!**\n\n"
        f"🤖 **Bot Hosting Server Panel**\n"
        f"আপনার Python বা Node.js বট এখানে সম্পূর্ণ বিনামূল্যে ২৪/৭ হোস্ট করুন।\n\n"
        f"📤 বট আপলোড করতে সরাসরি `.zip` বা `.py` ফাইল এই চ্যাটে পাঠান।"
    )
    bot.send_message(m.chat.id, text, reply_markup=main_menu_kb())

@bot.message_handler(content_types=['document'])
def handle_file_upload(m: types.Message):
    uid = m.from_user.id
    user = get_user(uid)

    if not can_create_bot(uid):
        bot.reply_to(m, "❌ আপনার বট লিমিট শেষ! আরও বট হোস্ট করতে প্ল্যান আপগ্রেড করুন।")
        return

    doc = m.document
    fname = doc.file_name.lower()
    if not (fname.endswith('.zip') or fname.endswith('.py') or fname.endswith('.js')):
        bot.reply_to(m, "❌ শুধুমাত্র `.zip`, `.py` অথবা `.js` ফাইল গ্রহণযোগ্য।")
        return

    msg = bot.reply_to(m, "⏳ ফাইল প্রসেস করা হচ্ছে এবং ডিপেনডেন্সি চেক করা হচ্ছে...")

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
            bot.edit_message_text("❌ আপলোড করা ফাইলে কোনো মূল ফাইল (`main.py`, `bot.py`, `index.js`) পাওয়া যায়নি!", chat_id=m.chat.id, message_id=msg.message_id)
            return

        db = load_db()
        db["bots"][bot_id] = {
            "name": doc.file_name,
            "path": str(bot_dir),
            "owner": uid,
            "uploaded": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        user["bots"].append(bot_id)
        save_db(db)

        bot.edit_message_text(
            f"✅ **বট আপলোড সফল হয়েছে!**\n\n"
            f"🆔 **Bot ID:** `+{bot_id}`\n"
            f"📁 **File:** `{doc.file_name}`\n"
            f"📄 **Entry:** `{entry.name}`\n\n"
            f"নিচের **My Bots** অপশনে গিয়ে বট চালু করুন।",
            chat_id=m.chat.id,
            message_id=msg.message_id,
            reply_markup=main_menu_kb()
        )

    except Exception as e:
        bot.edit_message_text(f"❌ আপলোড ব্যর্থ হয়েছে: {str(e)}", chat_id=m.chat.id, message_id=msg.message_id)

@bot.callback_query_handler(func=lambda c: True)
def handle_callbacks(c: types.CallbackQuery):
    data = c.data
    uid = c.from_user.id
    chat_id = c.message.chat.id

    if data == "menu_main":
        bot.edit_message_text("🤖 **Main Control Panel**", chat_id=chat_id, message_id=c.message.message_id, reply_markup=main_menu_kb())

    elif data == "menu_my_bots":
        db = load_db()
        user = get_user(uid)
        user_bots = user.get("bots", [])

        if not user_bots:
            bot.answer_callback_query(c.id, "আপনার কোনো আপলোড করা বট নেই!")
            return

        kb = types.InlineKeyboardMarkup(row_width=1)
        for bid in user_bots:
            if bid in db["bots"]:
                bname = db["bots"][bid]["name"]
                is_running = bid in RUNNING_PROCESSES and RUNNING_PROCESSES[bid]["process"].poll() is None
                status = "🟢" if is_running else "🔴"
                kb.add(types.InlineKeyboardButton(f"{status} {bname}", callback_data=f"select_{bid}"))

        kb.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main"))
        bot.edit_message_text("🤖 **আপনার হোস্ট করা বট সমূহের তালিকা:**", chat_id=chat_id, message_id=c.message.message_id, reply_markup=kb)

    elif data == "menu_upload":
        bot.send_message(chat_id, "📤 আপনার বটের `.zip` অথবা `.py` ফাইলটি চ্যাটে সেন্ড করুন।")
        bot.answer_callback_query(c.id)

    elif data == "menu_profile":
        user = get_user(uid)
        bot.edit_message_text(
            f"👤 **User Profile**\n\n"
            f"🆔 **ID:** `{uid}`\n"
            f"💎 **Plan:** `{user.get('plan', 'free').upper()}`\n"
            f"🤖 **Total Bots:** {len(user.get('bots', []))}\n"
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
            bot.answer_callback_query(c.id, "বট খুঁজে পাওয়া যায়নি!")
            return

        is_running = bid in RUNNING_PROCESSES and RUNNING_PROCESSES[bid]["process"].poll() is None
        status = "🟢 Running" if is_running else "🔴 Stopped"

        bot.edit_message_text(
            f"⚙️ **Bot Manager**\n\n"
            f"📛 **Name:** `{bot_info['name']}`\n"
            f"🆔 **ID:** `{bid}`\n"
            f"📊 **Status:** {status}\n"
            f"📅 **Uploaded:** {bot_info.get('uploaded', 'N/A')}",
            chat_id=chat_id,
            message_id=c.message.message_id,
            reply_markup=bot_control_kb(bid)
        )

    elif data.startswith("act_start_"):
        bid = data[10:]
        bot.answer_callback_query(c.id, "বট চালু হচ্ছে...")
        res = start_hosted_bot(bid)
        bot.send_message(chat_id, res)
        # Refresh state
        db = load_db()
        bot_info = db["bots"].get(bid)
        if bot_info:
            bot.edit_message_text(f"⚙️ **Bot Manager**\n\n📛 **Name:** `{bot_info['name']}`\n📊 **Status:** 🟢 Running", chat_id=chat_id, message_id=c.message.message_id, reply_markup=bot_control_kb(bid))

    elif data.startswith("act_stop_"):
        bid = data[9:]
        res = stop_hosted_bot(bid)
        bot.answer_callback_query(c.id, res)
        db = load_db()
        bot_info = db["bots"].get(bid)
        if bot_info:
            bot.edit_message_text(f"⚙️ **Bot Manager**\n\n📛 **Name:** `{bot_info['name']}`\n📊 **Status:** 🔴 Stopped", chat_id=chat_id, message_id=c.message.message_id, reply_markup=bot_control_kb(bid))

    elif data.startswith("act_logs_"):
        bid = data[9:]
        logs = get_hosted_logs(bid)
        bot.send_message(chat_id, f"📋 **Console Logs ({bid}):**\n\n<pre>{logs[:3800]}</pre>", reply_markup=bot_control_kb(bid))

    elif data.startswith("act_del_"):
        bid = data[8:]
        stop_hosted_bot(bid)
        db = load_db()
        if bid in db["bots"]:
            shutil.rmtree(db["bots"][bid]["path"], ignore_errors=True)
            del db["bots"][bid]
            if str(uid) in db["users"] and bid in db["users"][str(uid)]["bots"]:
                db["users"][str(uid)]["bots"].remove(bid)
            save_db(db)
        bot.answer_callback_query(c.id, "🗑️ বট সফলভাবে মুছে ফেলা হয়েছে!")
        bot.edit_message_text("🤖 **Main Control Panel**", chat_id=chat_id, message_id=c.message.message_id, reply_markup=main_menu_kb())

    bot.answer_callback_query(c.id)

# ==================== START POLLING ====================
if __name__ == "__main__":
    print("🤖 Main Bot Hosting Control Panel Started!")
    try:
        bot.delete_webhook()
    except:
        pass
    bot.infinity_polling(skip_pending=True)
    
