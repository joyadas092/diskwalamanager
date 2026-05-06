import os
import re
import asyncio
import threading
from flask import Flask

from telethon import TelegramClient, events, Button
from telethon.errors import (
    FloodWaitError,
    PeerIdInvalidError,
    ChannelPrivateError,
    ChatWriteForbiddenError,
)
from telethon.sessions import StringSession
from dotenv import load_dotenv

# ---------------- LOAD ENV ----------------

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SESSION_STRING = os.getenv("SESSION_STRING", "").strip()

# ---------------- CONFIG ----------------

MASTER_CHANNEL_ID = -1003324660206

CHILD_CHANNEL_IDS = [
    -1003925918191,
    -1003662286694,
    -1003440216101,
    -1003509258780,
    -1003610491355,
    -1003471521632,
]

# ---------------- RUNTIME STATE ----------------

START_FROM_MSG_ID = None
INTERVAL_MINUTES = None
IS_RUNNING = False
POST_QTY = 1
LOG_USER_ID = 6796879431
# ---------------- TELETHON CLIENT ----------------

session_obj = StringSession(SESSION_STRING) if SESSION_STRING else "diskwala_bot"
bot = TelegramClient(session_obj, API_ID, API_HASH).start(bot_token=BOT_TOKEN)

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

PROMO_BUTTON = [
    [Button.url("Join & See more 🤫", "t.me/Viral_diskwala_bot?start=1")]
]


async def report_issue(issue_text):
    """Send runtime errors to owner without crashing loop."""
    try:
        await bot.send_message(LOG_USER_ID, issue_text)
    except Exception as report_error:
        print(f"Failed to send issue log: {report_error}")

# ---------------- COMMANDS ----------------

@bot.on(events.NewMessage(pattern=r"^/start$"))
async def start(event):
    # await bot.forward_messages(
    #     event.chat_id,
    #     3,
    #     -1002482808575
    # )
    txt = '''
    𝑱𝒐𝒊𝒏 𝑭𝒐𝒓 𝑫𝒊𝒔𝒌𝒘𝒂𝒍𝒂 𝑽𝒊𝒅𝒆𝒐𝒔 ⏬⏬
    
    https://t.me/viral_diskwala_bot
        '''
    await event.respond(txt)


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

@bot.on(events.NewMessage(pattern=r"^/postqty_(\d+)$"))
async def postqty(event):
    global POST_QTY
    POST_QTY = int(event.pattern_match.group(1))
    await event.respond(f"📦 Post quantity per channel set to {POST_QTY}")

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
    global IS_RUNNING, START_FROM_MSG_ID, POST_QTY

    child_index = 0
    current_msg_id = START_FROM_MSG_ID
    disabled_channels = set()

    while IS_RUNNING:

        target = CHILD_CHANNEL_IDS[child_index]
        if target in disabled_channels:
            child_index += 1
            if child_index >= len(CHILD_CHANNEL_IDS):
                child_index = 0
            await asyncio.sleep(1)
            continue

        sent_count = 0

        # 🔥 Send multiple posts in same channel
        while sent_count < POST_QTY and IS_RUNNING:

            try:
                msg = await bot.get_messages(
                    MASTER_CHANNEL_ID,
                    ids=current_msg_id
                )

                # ❌ No message
                if not msg:
                    current_msg_id += 1
                    continue

                text = msg.text or msg.caption

                # ❌ No text/caption
                if not text:
                    current_msg_id += 1
                    continue

                links = extract_diskwala_links(text)

                # ❌ No diskwala link
                if not links:
                    current_msg_id += 1
                    continue

                # ✅ Build formatted message
                links_block = "\n\n➡️".join(links)

                new_text = f"""🎬 Vdo 😍** 🔗🔗यह रहा वीडियो लिंक 👇**

{links_block}

**🤔 How to Open Links see tutorial 👇🏻🤗| लिंक कैसे खोलें 👇**
https://t.me/howdisk/2

𝑷𝒍𝒆𝒂𝒔𝒆 𝑱𝒐𝒊𝒏 𝑩𝒆𝒍𝒐𝒘 Backup 𝑪𝒉𝒂𝒏𝒏𝒆𝒍𝒔 Must 🙏
1. https://t.me/+E5TOi5ci6ZljY2Q9
2. https://t.me/+P-MVSzKF3hsxMjA1
"""

                # ✅ Send message
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

                sent_count += 1
                current_msg_id += 1

                # 🔥 Small delay to avoid flood
                await asyncio.sleep(1)

            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)

            except (PeerIdInvalidError, ChannelPrivateError, ChatWriteForbiddenError) as e:
                disabled_channels.add(target)
                await report_issue(
                    f"❌ Channel disabled/skipped: `{target}`\n"
                    f"Reason: {type(e).__name__}: {e}"
                )
                print(f"Channel skipped {target}: {e}")
                break

            except Exception as e:
                print(f"Error {current_msg_id}: {e}")
                await report_issue(
                    f"⚠️ Error on msg `{current_msg_id}` to `{target}`\n"
                    f"{type(e).__name__}: {e}"
                )
                current_msg_id += 1

        # 🔥 Move to next channel AFTER batch
        child_index += 1
        if child_index >= len(CHILD_CHANNEL_IDS):
            child_index = 0

        if len(disabled_channels) == len(CHILD_CHANNEL_IDS):
            await report_issue(
                "🛑 All child channels are disabled/private/unwritable. Stopping copy loop."
            )
            IS_RUNNING = False
            break

        print(f"⏱ Waiting {INTERVAL_MINUTES} minutes before next channel...")

        await asyncio.sleep(INTERVAL_MINUTES * 60)

    print("Loop stopped")
# ---------------- START EVERYTHING ----------------

if __name__ == "__main__":

    print("Starting Flask keep-alive server...")
    threading.Thread(target=run_web).start()

    print("Starting Telegram bot...")
    bot.run_until_disconnected()



