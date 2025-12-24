import os
import asyncio
import re

from pyrogram import Client, filters
from pyrogram.errors import FloodWait, RPCError
from dotenv import load_dotenv
from quart import Quart
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

MASTER_CHANNEL_ID = -1003324660206

# CHILD_CHANNEL_IDS = [
#     -1003588263421,
#     -1003551833177,
#     -1003563364372
# ]
CHILD_CHANNEL_IDS = [
    -1003440216101,
    -1002993106861,
    -1002406969774
]
# ================== RUNTIME STATE ==================
START_FROM_MSG_ID = None
INTERVAL_MINUTES = None
IS_RUNNING = False

# ===================================================

app = Client(
    "my_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

bot = Quart(__name__)


# ================== COMMAND HANDLERS ==================
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    # await app.send_message(message.chat.id, "ahaann")
    await app.forward_messages(
        chat_id=message.chat.id,
        from_chat_id=-1002482808575,
        message_ids=3,

    )

@app.on_message(filters.regex("startfrom"))
async def start_from_handler(client, message):
    global START_FROM_MSG_ID
    try:
        START_FROM_MSG_ID = int(message.text.split("_")[1])
        await message.reply(f"✅ Start from message ID set to {START_FROM_MSG_ID}")
    except:
        await message.reply("❌ Invalid format. Use /startfrom_1999")


@app.on_message(filters.regex("interval"))
async def interval_handler(client, message):
    global INTERVAL_MINUTES
    try:
        INTERVAL_MINUTES = int(message.text.split("_")[1])
        print(INTERVAL_MINUTES)
        await message.reply(f"⏱ Interval set to {INTERVAL_MINUTES} minutes")
    except:
        await message.reply("❌ Invalid format. Use /interval_20")


@app.on_message(filters.command("run"))
async def run_handler(client, message):
    global IS_RUNNING

    if not START_FROM_MSG_ID or not INTERVAL_MINUTES:
        await message.reply("❌ Set /startfrom and /interval first")
        return

    if IS_RUNNING:
        await message.reply("⚠️ Bot already running")
        return

    IS_RUNNING = True
    asyncio.create_task(copy_loop())
    await message.reply("🚀 Copy loop started")


@app.on_message(filters.command("stopbot"))
async def stop_handler(client, message):
    global IS_RUNNING
    IS_RUNNING = False
    await message.reply("🛑 Bot stopped")

def extract_diskwala_links(text: str) -> list[str]:
    return re.findall(
        r"https?://(?:www\.)?diskwala\.com/\S+",
        text
    )

Promo = InlineKeyboardMarkup(
    [[
        InlineKeyboardButton(
            "Click here to See more 🤫",
            url="https://t.me/addlist/gu7nU3yNklJhMTc9"
        )
    ]]
)

# ================== CORE LOOP ==================

async def copy_loop():
    global IS_RUNNING, START_FROM_MSG_ID

    child_index = 0
    current_msg_id = START_FROM_MSG_ID

    while IS_RUNNING:
        try:
            # Try to fetch single message by ID
            msg = await app.get_messages(
                chat_id=MASTER_CHANNEL_ID,
                message_ids=current_msg_id
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

            new_text = f"""🎬 ** 🔗🔗🔗 :👇**
{links_block}

🤔 **How to Open Links 👇👇 see tutorial Video 👇🏻🤗**
https://t.me/diskhow/3

𝐉𝐨𝐢𝐧 this 𝐁𝐚𝐜𝐤𝐮𝐩 𝐂𝐡𝐚𝐧𝐧𝐞𝐥 💾 for All New trending Videos 👇🏻👇🏻
https://t.me/+HQmvZytWmeI2YWM1
"""

            target_channel = CHILD_CHANNEL_IDS[child_index]

            if msg.media:
                await msg.copy(
                    chat_id=target_channel,
                    caption=new_text,
                    reply_markup=Promo
                )
            else:
                await app.send_message(
                    chat_id=target_channel,
                    text=new_text,
                    reply_markup=Promo
                )

            print(f"Posted msg {current_msg_id} → {target_channel}")

            child_index = (child_index + 1) % len(CHILD_CHANNEL_IDS)
            await asyncio.sleep(INTERVAL_MINUTES * 60)

        except FloodWait as e:
            await asyncio.sleep(e.value)

        except RPCError:
            # message not accessible / deleted / before bot joined
            pass

        except Exception as e:
            print(f"Error on msg {current_msg_id}: {e}")

        current_msg_id += 1

    print("Loop stopped")





# ================== QUART SETUP ==================

@bot.before_serving
async def before_serving():
    await app.start()


@bot.after_serving
async def after_serving():
    await app.stop()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(bot.run_task(host='0.0.0.0', port=8080))
    loop.run_forever()
