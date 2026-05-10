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

# -------- PIPELINE 1 CHANNELS --------

CHILD_CHANNEL_IDS = [
    -1003925918191,
    -1003662286694,
    -1003440216101,
    -1003509258780,
    -1003610491355,
    -1003471521632,
]

# -------- PIPELINE 2 CHANNELS --------

CHILD_CHANNEL_IDS_2 = [
    -1003729451436,
    -1003852141524,
    -1003315790833,
    -1003900921028
]

# ---------------- RUNTIME STATE ----------------

# -------- PIPELINE 1 --------

START_FROM_MSG_ID = None
INTERVAL_MINUTES = 30
POST_QTY = 1
IS_RUNNING = False

# -------- PIPELINE 2 --------

START_FROM_MSG_ID_2 = None
INTERVAL_MINUTES_2 = 30
POST_QTY_2 = 1
IS_RUNNING_2 = False

# ---------------- OTHER ----------------

LOG_USER_ID = 6796879431

# ---------------- TELETHON CLIENT ----------------

session_obj = StringSession(SESSION_STRING) if SESSION_STRING else "diskwala_bot"

bot = TelegramClient(
    session_obj,
    API_ID,
    API_HASH
).start(bot_token=BOT_TOKEN)

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

MAIN_BUTTON = [
    [Button.url(
        "Join & See more 🤫",
        "https://t.me/Viral_diskwala_bot?start=1"
    )]
]

TERABOX_BUTTON = [
    [Button.url(
        "TeraBox Downloader ⏬",
        "https://t.me/TerawalaRoBot"
    )]
]

BUTTON_COUNTER = 0

# -------- FOOTERS --------

FOOTER_1 = """
𝑷𝒍𝒆𝒂𝒔𝒆 𝑱𝒐𝒊𝒏 Backup 𝑪𝒉𝒂𝒏𝒏𝒆𝒍𝒔 Must 🙏

1. https://t.me/+E5TOi5ci6ZljY2Q9
2. https://t.me/+P-MVSzKF3hsxMjA1
"""

FOOTER_2 = """
🔥 𝑱𝒐𝒊𝒏 𝑩𝒂𝒄𝒌𝒖𝒑 𝑪𝒉𝒂𝒏𝒏𝒆𝒍 Must👇

1. https://t.me/+A6ausbTNqyZkNGE1
2. https://t.me/+N2XrlhA6tjNjNTZl
"""

# ---------------- REPORT ----------------

async def report_issue(issue_text):
    try:
        await bot.send_message(LOG_USER_ID, issue_text)

    except Exception as report_error:
        print(f"Failed to send issue log: {report_error}")

# ---------------- START COMMAND ----------------

@bot.on(events.NewMessage(pattern=r"^/start"))
async def start(event):

    txt = '''
𝑱𝒐𝒊𝒏 𝑭𝒐𝒓 𝑫𝒊𝒔𝒌𝒘𝒂𝒍𝒂 𝑽𝒊𝒅𝒆𝒐𝒔 ⏬⏬

https://t.me/viral_diskwala_bot
'''

    await event.respond(txt)

# =========================================================
# ================= PIPELINE 1 COMMANDS ===================
# =========================================================

@bot.on(events.NewMessage(pattern=r"^/startfrom_(\d+)$"))
async def startfrom(event):

    global START_FROM_MSG_ID

    START_FROM_MSG_ID = int(event.pattern_match.group(1))

    await event.respond(
        f"✅ Pipeline1 Start ID = {START_FROM_MSG_ID}"
    )

@bot.on(events.NewMessage(pattern=r"^/interval_(\d+)$"))
async def interval(event):

    global INTERVAL_MINUTES

    INTERVAL_MINUTES = int(event.pattern_match.group(1))

    await event.respond(
        f"⏱ Pipeline1 Interval = {INTERVAL_MINUTES}"
    )

@bot.on(events.NewMessage(pattern=r"^/postqty_(\d+)$"))
async def postqty(event):

    global POST_QTY

    POST_QTY = int(event.pattern_match.group(1))

    await event.respond(
        f"📦 Pipeline1 Qty = {POST_QTY}"
    )

@bot.on(events.NewMessage(pattern=r"^/run$"))
async def run_cmd(event):

    global IS_RUNNING

    if START_FROM_MSG_ID is None:
        await event.respond("❌ Set /startfrom_ first")
        return

    if IS_RUNNING:
        await event.respond("⚠️ Pipeline1 already running")
        return

    IS_RUNNING = True

    asyncio.create_task(
        run_pipeline(
            child_channels=CHILD_CHANNEL_IDS,
            start_var_name="START_FROM_MSG_ID",
            interval_var_name="INTERVAL_MINUTES",
            post_qty_var_name="POST_QTY",
            footer_text=FOOTER_1,
            running_flag_name="IS_RUNNING"
        )
    )

    await event.respond("🚀 Pipeline1 started")

@bot.on(events.NewMessage(pattern=r"^/stopbot$"))
async def stop_cmd(event):

    global IS_RUNNING

    IS_RUNNING = False

    await event.respond("🛑 Pipeline1 stopped")

# =========================================================
# ================= PIPELINE 2 COMMANDS ===================
# =========================================================

@bot.on(events.NewMessage(pattern=r"^/startfrom2_(\d+)$"))
async def startfrom2(event):

    global START_FROM_MSG_ID_2

    START_FROM_MSG_ID_2 = int(event.pattern_match.group(1))

    await event.respond(
        f"✅ Pipeline2 Start ID = {START_FROM_MSG_ID_2}"
    )

@bot.on(events.NewMessage(pattern=r"^/interval2_(\d+)$"))
async def interval2(event):

    global INTERVAL_MINUTES_2

    INTERVAL_MINUTES_2 = int(event.pattern_match.group(1))

    await event.respond(
        f"⏱ Pipeline2 Interval = {INTERVAL_MINUTES_2}"
    )

@bot.on(events.NewMessage(pattern=r"^/postqty2_(\d+)$"))
async def postqty2(event):

    global POST_QTY_2

    POST_QTY_2 = int(event.pattern_match.group(1))

    await event.respond(
        f"📦 Pipeline2 Qty = {POST_QTY_2}"
    )

@bot.on(events.NewMessage(pattern=r"^/run2$"))
async def run2(event):

    global IS_RUNNING_2

    if START_FROM_MSG_ID_2 is None:
        await event.respond("❌ Set /startfrom2_ first")
        return

    if IS_RUNNING_2:
        await event.respond("⚠️ Pipeline2 already running")
        return

    IS_RUNNING_2 = True

    asyncio.create_task(
        run_pipeline(
            child_channels=CHILD_CHANNEL_IDS_2,
            start_var_name="START_FROM_MSG_ID_2",
            interval_var_name="INTERVAL_MINUTES_2",
            post_qty_var_name="POST_QTY_2",
            footer_text=FOOTER_2,
            running_flag_name="IS_RUNNING_2"
        )
    )

    await event.respond("🚀 Pipeline2 started")

@bot.on(events.NewMessage(pattern=r"^/stopbot_2$"))
async def stopbot2(event):

    global IS_RUNNING_2

    IS_RUNNING_2 = False

    await event.respond("🛑 Pipeline2 stopped")

# =========================================================
# ==================== MAIN PIPELINE ======================
# =========================================================

async def run_pipeline(
    child_channels,
    start_var_name,
    interval_var_name,
    post_qty_var_name,
    footer_text,
    running_flag_name
):

    global BUTTON_COUNTER

    if not child_channels:

        await report_issue(
            f"❌ No child channels configured for {running_flag_name}"
        )

        globals()[running_flag_name] = False
        return

    child_index = 0
    disabled_channels = set()

    while globals()[running_flag_name]:

        # 🔥 LIVE VALUES
        current_msg_id = globals()[start_var_name]
        interval_minutes = globals()[interval_var_name]
        post_qty = globals()[post_qty_var_name]

        if current_msg_id is None:
            await asyncio.sleep(5)
            continue

        if not child_channels:

            await report_issue(
                f"❌ No channels remaining for {running_flag_name}"
            )

            globals()[running_flag_name] = False
            return

        target = child_channels[child_index]

        if target in disabled_channels:

            child_index += 1

            if child_index >= len(child_channels):
                child_index = 0

            await asyncio.sleep(1)
            continue

        sent_count = 0

        while sent_count < post_qty and globals()[running_flag_name]:

            try:

                msg = await bot.get_messages(
                    MASTER_CHANNEL_ID,
                    ids=current_msg_id
                )

                if not msg:
                    current_msg_id += 1
                    globals()[start_var_name] = current_msg_id
                    continue

                text = msg.text or msg.caption

                if not text:
                    current_msg_id += 1
                    globals()[start_var_name] = current_msg_id
                    continue

                links = extract_diskwala_links(text)

                if not links:
                    current_msg_id += 1
                    globals()[start_var_name] = current_msg_id
                    continue

                links_block = "\n\n➡️".join(links)

                new_text = f"""🎬 Vdo 😍** 🔗🔗यह रहा वीडियो लिंक 👇**

{links_block}

**🤔 How to Open Links see tutorial 👇🏻🤗| लिंक कैसे खोलें 👇**
https://t.me/howdisk/2

{footer_text}
"""

                # 🔥 BUTTON ROTATION
                BUTTON_COUNTER += 1

                if BUTTON_COUNTER % 4 == 0:
                    selected_button = TERABOX_BUTTON
                else:
                    selected_button = MAIN_BUTTON

                # -------- SEND --------

                if msg.media:

                    await bot.send_file(
                        target,
                        msg.media,
                        caption=new_text,
                        buttons=selected_button
                    )

                else:

                    await bot.send_message(
                        target,
                        new_text,
                        buttons=selected_button
                    )

                print(
                    f"[{running_flag_name}] Posted {current_msg_id} → {target}"
                )

                sent_count += 1
                current_msg_id += 1

                # 🔥 LIVE UPDATE START ID
                globals()[start_var_name] = current_msg_id

                await asyncio.sleep(1)

            except FloodWaitError as e:

                print(f"FloodWait {e.seconds}s")

                await asyncio.sleep(e.seconds)

            except (
                PeerIdInvalidError,
                ChannelPrivateError,
                ChatWriteForbiddenError
            ) as e:

                disabled_channels.add(target)

                await report_issue(
                    f"❌ Disabled channel `{target}`\n"
                    f"{type(e).__name__}: {e}"
                )

                print(f"Disabled {target}: {e}")

                break

            except Exception as e:

                print(
                    f"Error msg {current_msg_id} → {target}: {e}"
                )

                await report_issue(
                    f"⚠️ Error on `{current_msg_id}` → `{target}`\n"
                    f"{type(e).__name__}: {e}"
                )

                current_msg_id += 1
                globals()[start_var_name] = current_msg_id

        # -------- ROTATE CHANNEL --------

        child_index += 1

        if child_index >= len(child_channels):
            child_index = 0

        # -------- ALL DEAD --------

        if len(disabled_channels) == len(child_channels):

            await report_issue(
                f"🛑 All channels disabled for {running_flag_name}"
            )

            globals()[running_flag_name] = False
            break

        print(
            f"[{running_flag_name}] Waiting {interval_minutes} mins..."
        )

        # 🔥 LIVE INTERVAL SLEEP
        total_sleep = interval_minutes * 60

        for _ in range(total_sleep):

            if not globals()[running_flag_name]:
                break

            await asyncio.sleep(1)

    print(f"{running_flag_name} stopped")

# ---------------- START EVERYTHING ----------------

if __name__ == "__main__":

    print("Starting Flask keep-alive server...")

    threading.Thread(target=run_web).start()

    print("Starting Telegram bot...")

    bot.run_until_disconnected()
