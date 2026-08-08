import os
import json
import subprocess
import shutil
import secrets
import time
import threading
from pathlib import Path
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests

# ==================== CONFIG ====================
# আপনার দেওয়া টোকেন এবং অ্যাডমিন আইডি সেট করা হয়েছে
TOKEN = "8173098705:AAHaFQDF4YA7QNBkAaWS2ku9JiuZuzj-8_Y"
OWNER_ID = 7472542379

BOTS_DIR = Path("bots")
BOTS_DIR.mkdir(exist_ok=True)

DB_FILE = Path("db.json")

# ==================== DUMMY WEB SERVER (FOR RENDER) ====================
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot Hosting Bot is Running on Render!")

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    print(f"🌐 Dummy web server is running on port {port}")
    threading.Thread(target=server.serve_forever, daemon=True).start()

# ==================== DATABASE ====================
def load_db() -> dict:
    if DB_FILE.exists():
        return json.loads(DB_FILE.read_text())
    return {"users": {}, "bots": {}, "pending": {}}

def save_db(db: dict):
    DB_FILE.write_text(json.dumps(db, indent=2))

# ==================== TELEGRAM BOT SETUP ====================
try:
    import telebot
    from telebot import types
except ImportError:
    os.system("pip install pyTelegramBotAPI")
    import telebot
    from telebot import types

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
RUNNING = {}

# ==================== HELPERS ====================
def is_admin(uid: int) -> bool:
    return uid == OWNER_ID

def get_user(uid: int) -> dict:
    db = load_db()
    if str(uid) not in db["users"]:
        db["users"][str(uid)] = {"plan": "free", "bots": [], "joined": str(datetime.now())}
        save_db(db)
    return db["users"][str(uid)]

def can_create_bot(uid: int) -> bool:
    user = get_user(uid)
    max_bots = {"free": 2, "premium": 5, "pro": 10}.get(user.get("plan", "free"), 2)
    return len(user.get("bots", [])) < max_bots

def bot_status(bid: str) -> str:
    if bid in RUNNING and RUNNING[bid]["process"].poll() is None:
        return "🟢 Running"
    return "🔴 Stopped"

def get_logs(bid: str, lines: int = 20) -> str:
    if bid in RUNNING:
        log = RUNNING[bid].get("logs", [])
        return "\n".join(log[-lines:])
    return "Bot is not running."

# ==================== BOT MANAGEMENT ====================
def start_bot(bid: str):
    db = load_db()
    bot_data = db["bots"].get(bid)
    if not bot_data:
        return "Bot not found"
    
    bot_dir = Path(bot_data["path"])
    if not bot_dir.exists():
        return "Bot folder missing"
    
    # Detect entry file
    entry = None
    for f in ["bot.py", "main.py", "app.py", "index.js", "bot.js"]:
        if (bot_dir / f).exists():
            entry = f
            break
    
    if not entry:
        return "No entry file found (bot.py / main.py / index.js)"
    
    # Start process
    cmd = ["python3", entry] if entry.endswith(".py") else ["node", entry]
    
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(bot_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        RUNNING[bid] = {
            "process": proc,
            "logs": [],
            "started": time.time()
        }
        
        # Log reader thread
        def read_logs():
            for line in iter(proc.stdout.readline, ""):
                if bid in RUNNING:
                    RUNNING[bid]["logs"].append(line.strip())
                    if len(RUNNING[bid]["logs"]) > 200:
                        RUNNING[bid]["logs"] = RUNNING[bid]["logs"][-200:]
        
        threading.Thread(target=read_logs, daemon=True).start()
        return "✅ Bot started successfully!"
    except Exception as e:
        return f"❌ Failed to start: {e}"

def stop_bot(bid: str):
    if bid in RUNNING:
        try:
            RUNNING[bid]["process"].terminate()
            RUNNING[bid]["process"].wait(timeout=5)
        except:
            RUNNING[bid]["process"].kill()
        del RUNNING[bid]
        return "✅ Bot stopped"
    return "Bot is not running"

def delete_bot(bid: str):
    stop_bot(bid)
    db = load_db()
    if bid in db["bots"]:
        bot_path = Path(db["bots"][bid]["path"])
        shutil.rmtree(bot_path, ignore_errors=True)
        del db["bots"][bid]
        save_db(db)
        return "✅ Bot deleted"
    return "Bot not found"

# ==================== KEYBOARDS ====================
def main_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🤖 My Bots", callback_data="my_bots"),
        types.InlineKeyboardButton("📤 Upload Bot", callback_data="upload_bot"),
    )
    kb.add(
        types.InlineKeyboardButton("👤 Profile", callback_data="profile"),
        types.InlineKeyboardButton("💳 Plans", callback_data="plans"),
    )
    kb.add(
        types.InlineKeyboardButton("🆘 Help", callback_data="help"),
    )
    return kb

def bot_actions_kb(bid: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    running = bid in RUNNING and RUNNING[bid]["process"].poll() is None
    
    if running:
        kb.add(types.InlineKeyboardButton("⏹ Stop", callback_data=f"stop_{bid}"))
    else:
        kb.add(types.InlineKeyboardButton("▶️ Start", callback_data=f"start_{bid}"))
    
    kb.add(
        types.InlineKeyboardButton("📋 Logs", callback_data=f"logs_{bid}"),
        types.InlineKeyboardButton("🗑 Delete", callback_data=f"delete_{bid}"),
    )
    kb.add(types.InlineKeyboardButton("🔙 Back", callback_data="my_bots"))
    return kb

# ==================== HANDLERS ====================
@bot.message_handler(commands=['start'])
def cmd_start(m: types.Message):
    get_user(m.from_user.id)
    bot.send_message(
        m.chat.id,
        f"👋 Welcome {m.from_user.first_name}!\n\n"
        f"<b>🤖 Bot Hosting Panel</b>\n"
        f"Upload your bot and run it 24/7!\n\n"
        f"Send a <b>.zip</b>, <b>.py</b> or <b>.js</b> file to upload.",
        reply_markup=main_kb()
    )

@bot.message_handler(commands=['help'])
def cmd_help(m: types.Message):
    help_text = """
<b>📖 How to use:</b>

1️⃣ <b>Upload Bot</b>
   Send .zip, .py or .js file

2️⃣ <b>Start Bot</b>
   My Bots → Select → Start

3️⃣ <b>View Logs</b>
   See what your bot is doing

4️⃣ <b>Stop/Delete</b>
   Manage your bots anytime

<b>📦 Supported:</b>
• Python (bot.py/main.py)
• Node.js (index.js/bot.js)
"""
    bot.send_message(m.chat.id, help_text, reply_markup=main_kb())

@bot.message_handler(content_types=['document'])
def handle_upload(m: types.Message):
    uid = m.from_user.id
    user = get_user(uid)
    
    if not can_create_bot(uid):
        bot.reply_to(m, f"❌ Bot limit reached! Upgrade to create more bots.")
        return
    
    doc = m.document
    if not doc.file_name.endswith(('.zip', '.py', '.js')):
        bot.reply_to(m, "❌ Only .zip, .py, .js files allowed")
        return
    
    file_info = bot.get_file(doc.file_id)
    file_data = bot.download_file(file_info.file_path)
    
    bot_id = secrets.token_hex(6)
    bot_path = BOTS_DIR / bot_id
    bot_path.mkdir(parents=True, exist_ok=True)
    
    if doc.file_name.endswith('.zip'):
        import zipfile
        from io import BytesIO
        with zipfile.ZipFile(BytesIO(file_data)) as zf:
            zf.extractall(bot_path)
    else:
        (bot_path / doc.file_name).write_bytes(file_data)
    
    db = load_db()
    db["bots"][bot_id] = {
        "name": doc.file_name,
        "path": str(bot_path),
        "owner": uid,
        "uploaded": str(datetime.now())
    }
    user["bots"].append(bot_id)
    save_db(db)
    
    bot.reply_to(
        m,
        f"✅ <b>Bot uploaded!</b>\n"
        f"ID: <code>{bot_id}</code>\n"
        f"File: {doc.file_name}\n\n"
        f"Go to My Bots to start it."
    )

@bot.callback_query_handler(func=lambda c: True)
def handle_callback(c: types.CallbackQuery):
    data = c.data
    
    if data == "my_bots":
        show_my_bots(c)
    
    elif data == "upload_bot":
        bot.send_message(
            c.message.chat.id,
            "📤 Send your bot file (.zip / .py / .js)",
            reply_markup=main_kb()
        )
    
    elif data == "profile":
        uid = c.from_user.id
        user = get_user(uid)
        bot_count = len(user.get("bots", []))
        plan = user.get("plan", "free")
        
        bot.send_message(
            c.message.chat.id,
            f"<b>👤 Profile</b>\n\n"
            f"ID: <code>{uid}</code>\n"
            f"Plan: <b>{plan.upper()}</b>\n"
            f"Bots: {bot_count}\n"
            f"Joined: {user.get('joined', 'Unknown')[:10]}",
            reply_markup=main_kb()
        )
    
    elif data == "plans":
        show_plans(c)
    
    elif data == "help":
        cmd_help(c.message)
    
    elif data.startswith("bot_"):
        bid = data[4:]
        show_bot_detail(c, bid)
    
    elif data.startswith("start_"):
        bid = data[6:]
        result = start_bot(bid)
        bot.answer_callback_query(c.id, result)
        show_bot_detail(c, bid)
    
    elif data.startswith("stop_"):
        bid = data[5:]
        result = stop_bot(bid)
        bot.answer_callback_query(c.id, result)
        show_bot_detail(c, bid)
    
    elif data.startswith("logs_"):
        bid = data[5:]
        logs = get_logs(bid, 30)
        bot.send_message(
            c.message.chat.id,
            f"<b>📋 Logs for {bid}</b>\n\n<pre>{logs[:3500]}</pre>",
            reply_markup=bot_actions_kb(bid)
        )
    
    elif data.startswith("delete_"):
        bid = data[7:]
        result = delete_bot(bid)
        bot.answer_callback_query(c.id, result)
        show_my_bots(c)
    
    bot.answer_callback_query(c.id)

def show_my_bots(c):
    uid = c.from_user.id
    db = load_db()
    user = db["users"].get(str(uid), {})
    bot_ids = user.get("bots", [])
    
    if not bot_ids:
        bot.send_message(
            c.message.chat.id,
            "🤖 <b>No bots yet!</b>\n\nUpload your first bot by sending a .zip file.",
            reply_markup=main_kb()
        )
        return
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    for bid in bot_ids:
        if bid in db["bots"]:
            name = db["bots"][bid].get("name", bid)[:20]
            status_icon = "🟢" if bid in RUNNING and RUNNING[bid]["process"].poll() is None else "🔴"
            kb.add(types.InlineKeyboardButton(f"{status_icon} {name}", callback_data=f"bot_{bid}"))
    
    kb.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="main"))
    
    bot.send_message(
        c.message.chat.id,
        f"🤖 <b>Your Bots</b> ({len(bot_ids)} total)",
        reply_markup=kb
    )

def show_bot_detail(c, bid: str):
    db = load_db()
    bot_data = db["bots"].get(bid)
    if not bot_data:
        bot.send_message(c.message.chat.id, "❌ Bot not found")
        return
    
    status = bot_status(bid)
    uptime = ""
    if bid in RUNNING and RUNNING[bid]["process"].poll() is None:
        elapsed = int(time.time() - RUNNING[bid].get("started", time.time()))
        uptime = f"Uptime: {elapsed//60}m {elapsed%60}s"
    
    bot.send_message(
        c.message.chat.id,
        f"<b>🤖 {bot_data.get('name', bid)}</b>\n\n"
        f"Status: {status}\n"
        f"ID: <code>{bid}</code>\n"
        f"{uptime}\n"
        f"Uploaded: {bot_data.get('uploaded', 'Unknown')[:10]}",
        reply_markup=bot_actions_kb(bid)
    )

def show_plans(c):
    kb = types.InlineKeyboardMarkup(row_width=2)
    plans = [
        ("Free", "2 bots", "0"),
        ("Premium", "5 bots", "99"),
        ("Pro", "10 bots", "199"),
    ]
    
    for name, features, price in plans:
        kb.add(types.InlineKeyboardButton(
            f"💎 {name} - {price}$", callback_data=f"plan_{name.lower()}"
        ))
    
    kb.add(types.InlineKeyboardButton("🔙 Back", callback_data="main"))
    
    bot.send_message(
        c.message.chat.id,
        "<b>💳 Plans</b>\n\n"
        "Free: 2 bots\n"
        "Premium: 5 bots (99$)\n"
        "Pro: 10 bots (199$)\n\n"
        "Contact @support to upgrade!",
        reply_markup=kb
    )

# ==================== RUN ====================
if __name__ == "__main__":
    print("🤖 Bot Hosting Bot Started!")
    
    # Render.com এর জন্য Dummy Server চালু করা হচ্ছে
    keep_alive()

    # Webhook ক্লিয়ার করে পোলিং শুরু করা
    try:
        bot.delete_webhook()
    except Exception as e:
        pass
    
    bot.infinity_polling()
