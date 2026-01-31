import os
import re
import asyncio
import threading
from flask import Flask

from telethon import TelegramClient, events, Button
from telethon.errors import FloodWaitError
from dotenv import load_dotenv

# ---------------- LOAD ENV ----------------

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ---------------- CONFIG ----------------

MASTER_CHANNEL_ID = -1003324660206

CHILD_CHANNEL_IDS = [
    -1003440216101,
    -1003509258780,
    -1003610491355,
    -1003588263421
]

# ---------------- RUNTIME STATE ----------------

START_FROM_MSG_ID = None
INTERVAL_MINUTES = None
IS_RUNNING = False

# ---------------- TELETHON CLIENT ----------------

bot = TelegramClient("diskwala_bot", API_ID, API_HASH).start(
    bot_token=BOT_TOKEN
)

# ---------------- FLASK KEEP ALIVE ----------------

app = Flask(__name__)

@app.route("/")
def home():
    return "Diskwala Bot Running", 200

def run_web():
    app.run(host="0.0.0.0", port=8080)

# ---------------- UTIL ----------------

def extract_diskwala_links(text):
    return re.findall(
        r"https?://(?:www\.)?diskwala\.com/\S+",
        text
    )

PROMO_BUTTON = Button.url(
    "Click here to See more 🤫",
    "https://t.me/addlist/gu7nU3yNklJhMTc9"
)

# ---------------- COMMANDS ----------------

@bot.on(events.NewMessage(pattern=r"^/start$"))
async def start(event):
    await bot.forward_messages(
        event.chat_id,
        3,
        -1002482808575
    )

@bot.on(events.NewMessage(pattern=r"^/startfrom_(\d+)$"))
async def startfrom(event):
    global START_FROM_MSG_ID
    START_FROM_MSG_ID = int(event.pattern_match.group(1))
    await event.respond(f"✅ Start from message ID set to {START_FROM_MSG_ID}")

@bot.on(events.NewMessage(pattern=r"^/interval_(\d+)$"))
async def interval(event):
    global INTERVAL_MINUTES
    INTERVAL_MINUTES = int(event.pattern_match.group(1))
    await event.respond(f"⏱ Interval set to {INTERVAL_MINUTES} minutes")

@bot.on(events.NewMessage(pattern=r"^/run$"))
async def run_cmd(event):
    global IS_RUNNING

    if not START_FROM_MSG_ID or not INTERVAL_MINUTES:
        await event.respond("❌ Set /startfrom_<id> and /interval_<min> first")
        return

    if IS_RUNNING:
        await event.respond("⚠️ Bot already running")
        return

    IS_RUNNING = True
    asyncio.create_task(copy_loop())
    await event.respond("🚀 Copy loop started")

@bot.on(events.NewMessage(pattern=r"^/stopbot$"))
async def stop_cmd(event):
    global IS_RUNNING
    IS_RUNNING = False
    await event.respond("🛑 Bot stopped")

# ---------------- CORE LOOP ----------------

async def copy_loop():
    global IS_RUNNING, START_FROM_MSG_ID

    child_index = 0
    current_msg_id = START_FROM_MSG_ID

    while IS_RUNNING:

        try:
            msg = await bot.get_messages(
                MASTER_CHANNEL_ID,
                ids=current_msg_id
            )

            if not msg:
                current_msg_id += 1
                continue

            text = msg.text or msg.caption
            if not text:
                current_msg_id += 1
                continue

            links = extract_diskwala_links(text)
            if not links:
                current_msg_id += 1
                continue

            links_block = "\n\n➡️".join(links)

            new_text = f"""🎬 Vdo ** 🔗🔗🔗 👇यह रहा वीडियो लिंक 👇**
{links_block}

🤔 How to Open Links 👇👇 see tutorial Video 👇🏻🤗
🤔 लिंक कैसे खोलें 👇👇 ट्यूटोरियल वीडियो देखें 👇🏻🤗
https://t.me/diskhow/3

𝐉𝐨𝐢𝐧 this 𝐁𝐚𝐜𝐤𝐮𝐩 𝐂𝐡𝐚𝐧𝐧𝐞𝐥 💾 for All New trending Videos 👇🏻👇🏻
इस बैकअप चैनल से जुड़ें 💾 सभी नए ट्रेंडिंग वीडियो पाने के लिए 👇🏻👇🏻
https://t.me/+HQmvZytWmeI2YWM1
"""

            target = CHILD_CHANNEL_IDS[child_index]

            if msg.media:
                await bot.send_file(
                    target,
                    msg.media,
                    caption=new_text,
                    buttons=PROMO_BUTTON
                )
            else:
                await bot.send_message(
                    target,
                    new_text,
                    buttons=PROMO_BUTTON
                )

            print(f"Posted {current_msg_id} → {target}")

            child_index = (child_index + 1) % len(CHILD_CHANNEL_IDS)
            await asyncio.sleep(INTERVAL_MINUTES * 60)

        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)

        except Exception as e:
            print(f"Error {current_msg_id}: {e}")

        current_msg_id += 1

    print("Loop stopped")

# ---------------- START EVERYTHING ----------------

if __name__ == "__main__":

    print("Starting Flask keep-alive server...")
    threading.Thread(target=run_web).start()

    print("Starting Telegram bot...")
    bot.run_until_disconnected()
