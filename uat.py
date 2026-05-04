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

# Diskwala
DISKWALA_SOURCE_CHANNEL = -1003324660206
CHILD_CHANNEL_IDS = [
    -1003662286694,
    -1003906114728,
    -1003440216101,
    -1003509258780,
    -1003610491355,
    -1003471521632,
]

# Terabox
TERABOX_SOURCE_CHANNEL = -1003792045938  # 🔴 replace
TERABOX_CHILD_CHANNELS = []

# ---------------- STATE ----------------

# Diskwala
DW_RUNNING = False
DW_START_ID = None
DW_INTERVAL = None
DW_POST_QTY = 1

# Terabox
TB_RUNNING = False
TB_START_ID = None
TB_INTERVAL = None
TB_POST_QTY = 1

# ---------------- CLIENT ----------------

bot = TelegramClient("manager_bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# ---------------- FLASK ----------------

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Running", 200

def run_web():
    app.run(host="0.0.0.0", port=8080)

# ---------------- UTIL ----------------

def extract_diskwala_links(text):
    return re.findall(r"https?://(?:www\.)?diskwala\.com/\S+", text)

def extract_terabox_links(text):
    return re.findall(r"https?://\S*terabox\S+", text)

# ---------------- BUTTONS ----------------

DW_BUTTONS = [
    [Button.url("Click and See more 🤫", "t.me/Viral_diskwala_bot?start=1")]
]

TB_BUTTONS = [
    [Button.url("Join Terabox Hub 🚀", "https://t.me/addlist/99-X694MGUM3NzM1")]
]

# ---------------- COMMANDS ----------------

@bot.on(events.NewMessage(pattern=r"^/start$"))
async def start(event):
    txt='''
𝑱𝒐𝒊𝒏 𝑭𝒐𝒓 𝑫𝒊𝒔𝒌𝒘𝒂𝒍𝒂 𝑽𝒊𝒅𝒆𝒐𝒔 ⏬⏬
https://t.me/addlist/gu7nU3yNklJhMTc9
    '''
    await event.respond(txt)

# ---- Diskwala ----

@bot.on(events.NewMessage(pattern=r"^/dw_start_(\d+)$"))
async def dw_start(event):
    global DW_START_ID
    DW_START_ID = int(event.pattern_match.group(1))
    await event.respond(f"DW Start = {DW_START_ID}")

@bot.on(events.NewMessage(pattern=r"^/dw_interval_(\d+)$"))
async def dw_interval(event):
    global DW_INTERVAL
    DW_INTERVAL = int(event.pattern_match.group(1))
    await event.respond(f"DW Interval = {DW_INTERVAL} min")

@bot.on(events.NewMessage(pattern=r"^/dw_postqty_(\d+)$"))
async def dw_qty(event):
    global DW_POST_QTY
    DW_POST_QTY = int(event.pattern_match.group(1))
    await event.respond(f"DW Qty = {DW_POST_QTY}")

# ---- Terabox ----

@bot.on(events.NewMessage(pattern=r"^/tb_start_(\d+)$"))
async def tb_start(event):
    global TB_START_ID
    TB_START_ID = int(event.pattern_match.group(1))
    await event.respond(f"TB Start = {TB_START_ID}")

@bot.on(events.NewMessage(pattern=r"^/tb_interval_(\d+)$"))
async def tb_interval(event):
    global TB_INTERVAL
    TB_INTERVAL = int(event.pattern_match.group(1))
    await event.respond(f"TB Interval = {TB_INTERVAL} min")

@bot.on(events.NewMessage(pattern=r"^/tb_postqty_(\d+)$"))
async def tb_qty(event):
    global TB_POST_QTY
    TB_POST_QTY = int(event.pattern_match.group(1))
    await event.respond(f"TB Qty = {TB_POST_QTY}")

# # ---- RUN ----
#
# @bot.on(events.NewMessage(pattern=r"^/run$"))
# async def run_cmd(event):
#     global IS_RUNNING
#
#     if not DW_START_ID or not DW_INTERVAL:
#         await event.respond("Set Diskwala config first")
#         return
#
#     if not TB_START_ID or not TB_INTERVAL:
#         await event.respond("Set Terabox config first")
#         return
#
#     if IS_RUNNING:
#         await event.respond("Already running")
#         return
#
#     IS_RUNNING = True
#
#     asyncio.create_task(copy_loop_dw())
#     asyncio.create_task(copy_loop_tb())
#
#     await event.respond("Both pipelines started 🚀")
#
# @bot.on(events.NewMessage(pattern=r"^/stopbot$"))
# async def stop_cmd(event):
#     global IS_RUNNING
#     IS_RUNNING = False
#     await event.respond("Stopped ❌")

# ---- RUN COMMANDS ----

@bot.on(events.NewMessage(pattern=r"^/DW_Run$"))
async def run_dw(event):
    global DW_RUNNING

    if not DW_START_ID or not DW_INTERVAL:
        await event.respond("Set Diskwala config first")
        return

    if DW_RUNNING:
        await event.respond("Diskwala already running")
        return

    DW_RUNNING = True
    asyncio.create_task(copy_loop_dw())

    await event.respond("🚀 Diskwala started")


@bot.on(events.NewMessage(pattern=r"^/TB_Run$"))
async def run_tb(event):
    global TB_RUNNING

    if not TB_START_ID or not TB_INTERVAL:
        await event.respond("Set Terabox config first")
        return

    if TB_RUNNING:
        await event.respond("Terabox already running")
        return

    TB_RUNNING = True
    asyncio.create_task(copy_loop_tb())

    await event.respond("🚀 Terabox started")

# ---- STOP ----

@bot.on(events.NewMessage(pattern=r"^/dw_stop$"))
async def stop_dw(event):
    global DW_RUNNING
    DW_RUNNING = False
    await event.respond("🛑 Diskwala stopped")

@bot.on(events.NewMessage(pattern=r"^/tb_stop$"))
async def stop_tb(event):
    global TB_RUNNING
    TB_RUNNING = False
    await event.respond("🛑 Terabox stopped")

# ---------------- DISKWALA LOOP ----------------

async def copy_loop_dw():
    global DW_RUNNING, DW_START_ID, DW_INTERVAL, DW_POST_QTY

    child_index = 0
    current_msg_id = DW_START_ID

    while DW_RUNNING:

        target = CHILD_CHANNEL_IDS[child_index]
        sent = 0

        while sent < DW_POST_QTY and DW_RUNNING:
            try:
                msg = await bot.get_messages(DISKWALA_SOURCE_CHANNEL, ids=current_msg_id)

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

                new_text = f"""**🎬 Vdo 😍 🔗🔗यह रहा वीडियो लिंक 👇 👇**

{links_block}

🤔 𝙃𝙤𝙬 𝙩𝙤 𝙊𝙥𝙚𝙣 𝙑𝙞𝙙𝙚𝙤 | लिंक कैसे खोलें 👇𝙨𝙚𝙚 𝙩𝙪𝙩𝙤𝙧𝙞𝙖𝙡 👇🏻🤗
https://t.me/howdisk/2

𝑷𝒍𝒆𝒂𝒔𝒆 𝑱𝒐𝒊𝒏 𝑩𝒆𝒍𝒐𝒘 Backup 𝑪𝒉𝒂𝒏𝒏𝒆𝒍𝒔 Must 🙏
1. https://t.me/+izgCF5xr9MkyMTQ1
2. https://t.me/+Ys9iGWzqk-BjZWJl
"""

                if msg.media:
                    await bot.send_file(target, msg.media, caption=new_text, buttons=DW_BUTTONS)
                else:
                    await bot.send_message(target, new_text, buttons=DW_BUTTONS)

                print(f"[DW] {current_msg_id} → {target}")

                sent += 1
                current_msg_id += 1
                await asyncio.sleep(1)

            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)

            except Exception as e:
                print(f"[DW ERROR] {current_msg_id}: {e}")
                current_msg_id += 1

        child_index = (child_index + 1) % len(CHILD_CHANNEL_IDS)
        await asyncio.sleep(DW_INTERVAL * 60)

# ---------------- TERABOX LOOP ----------------

async def copy_loop_tb():
    global TB_RUNNING, TB_START_ID, TB_INTERVAL, TB_POST_QTY

    child_index = 0
    current_msg_id = TB_START_ID

    while TB_RUNNING:

        target = TERABOX_CHILD_CHANNELS[child_index]
        sent = 0

        while sent < TB_POST_QTY and TB_RUNNING:
            try:
                msg = await bot.get_messages(TERABOX_SOURCE_CHANNEL, ids=current_msg_id)

                if not msg:
                    current_msg_id += 1
                    continue

                text = msg.text or msg.caption
                if not text:
                    current_msg_id += 1
                    continue

                links = extract_terabox_links(text)
                if not links:
                    current_msg_id += 1
                    continue

                links_block = "\n\n➡️".join(links)

                new_text = f"""📦 **🎬 Vdo 😍 🔗🔗यह रहा वीडियो लिंक 👇👇**

{links_block}
🤔 𝙃𝙤𝙬 𝙩𝙤 𝙊𝙥𝙚𝙣 𝙑𝙞𝙙𝙚𝙤 | लिंक कैसे खोलें 👇𝙨𝙚𝙚 𝙩𝙪𝙩𝙤𝙧𝙞𝙖𝙡 👇🏻🤗
https://t.me/diskhow/5

𝑷𝒍𝒆𝒂𝒔𝒆 𝑱𝒐𝒊𝒏 𝑩𝒆𝒍𝒐𝒘 𝑪𝒉𝒂𝒏𝒏𝒆𝒍𝒔 𝒂𝒔 𝒃𝒂𝒄𝒌𝒖𝒑
🥹👇🏻👇🏻

1. t.me/+V1NC04vP1hYwMzQy
2. t.me/+gvA2-ktq5oQ2ZDZi
"""

                if msg.media:
                    await bot.send_file(target, msg.media, caption=new_text, buttons=TB_BUTTONS)
                else:
                    await bot.send_message(target, new_text, buttons=TB_BUTTONS)

                print(f"[TB] {current_msg_id} → {target}")

                sent += 1
                current_msg_id += 1
                await asyncio.sleep(1)

            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)

            except Exception as e:
                print(f"[TB ERROR] {current_msg_id}: {e}")
                current_msg_id += 1

        child_index = (child_index + 1) % len(TERABOX_CHILD_CHANNELS)
        await asyncio.sleep(TB_INTERVAL * 60)

# ---------------- START ----------------

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    print("Bot started...")
    bot.run_until_disconnected()
