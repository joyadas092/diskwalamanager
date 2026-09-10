import os
import re
import json
import asyncio
import threading
from pathlib import Path
from flask import Flask

from telethon import TelegramClient, events, Button
from telethon.errors import (
    FloodWaitError,
    PeerIdInvalidError,
    ChannelPrivateError,
    ChatWriteForbiddenError,
)
from telethon.tl.types import (
    MessageMediaPhoto,
    MessageMediaDocument,
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
# MASTER_CHANNEL_ID2 = -1003792045938
MASTER_CHANNEL_ID2 = -1003818431774

# -------- PIPELINE 1 CHANNELS --------

CHILD_CHANNEL_IDS = [
    -1003967952177,
    -1004426679858,
    -1003662286694,
    -1003440216101,
    -1003509258780,
    -1003610491355,
    -1003471521632,
]

# -------- PIPELINE 2 CHANNELS --------

CHILD_CHANNEL_IDS_2 = [
    -1004333853896,
    -1004332767188,
    -1003729451436,
    -1003852141524,
    -1004482717052,
    -1003315790833,
    -1003981620549,
    -1003655989898
]

# -------- PIPELINE 3 TERABOX CHANNELS --------

CHILD_CHANNEL_IDS_3 = [
    -1004384690409,
    -1003811817479    
]

CONFIG_PATH = Path(__file__).resolve().parent / "bot_runtime_config.json"

DEFAULT_RUNTIME_CONFIG = {
    "channels": {
        "1": list(CHILD_CHANNEL_IDS),
        "2": list(CHILD_CHANNEL_IDS_2),
        "3": list(CHILD_CHANNEL_IDS_3),
    },
    "disabled": {"1": [], "2": [], "3": []},
    "interval_minutes": {"1": 30, "2": 30, "3": 60},
    "post_qty": {"1": 1, "2": 1, "3": 2},
    "channel_titles": {},
}

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

# -------- PIPELINE 3 TERABOX --------

START_FROM_MSG_ID_3 = None
INTERVAL_MINUTES_3 = 60
POST_QTY_3 = 2
IS_RUNNING_3 = False



# ---------------- OTHER ----------------

LOG_USER_ID = 6796879431
ADMIN_USER_ID = LOG_USER_ID

runtime_config = {}
pending_admin_action = {}

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

def extract_terabox_links(text):
    return re.findall(
        r"https?://\S*terabox\S+",
        text,
        flags=re.IGNORECASE
    )


def load_runtime_config():
    global runtime_config

    if CONFIG_PATH.is_file():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as cfg_file:
                loaded = json.load(cfg_file)
        except (json.JSONDecodeError, OSError) as load_error:
            print(f"Config load failed, using defaults: {load_error}")
            loaded = {}
    else:
        loaded = {}

    merged = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))
    for pipeline_key in ("1", "2", "3"):
        if pipeline_key in loaded.get("channels", {}):
            merged["channels"][pipeline_key] = list(loaded["channels"][pipeline_key])
        if pipeline_key in loaded.get("disabled", {}):
            merged["disabled"][pipeline_key] = list(loaded["disabled"][pipeline_key])
        if pipeline_key in loaded.get("interval_minutes", {}):
            merged["interval_minutes"][pipeline_key] = int(
                loaded["interval_minutes"][pipeline_key]
            )
        if pipeline_key in loaded.get("post_qty", {}):
            merged["post_qty"][pipeline_key] = int(loaded["post_qty"][pipeline_key])

    if isinstance(loaded.get("channel_titles"), dict):
        merged["channel_titles"] = {
            str(channel_id): str(title)
            for channel_id, title in loaded["channel_titles"].items()
        }

    runtime_config = merged
    sync_globals_from_config()
    save_runtime_config()


def save_runtime_config():
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as cfg_file:
            json.dump(runtime_config, cfg_file, indent=2)
    except OSError as save_error:
        print(f"Config save failed: {save_error}")


def sync_globals_from_config():
    global CHILD_CHANNEL_IDS, CHILD_CHANNEL_IDS_2, CHILD_CHANNEL_IDS_3
    global INTERVAL_MINUTES, INTERVAL_MINUTES_2, INTERVAL_MINUTES_3
    global POST_QTY, POST_QTY_2, POST_QTY_3

    if not runtime_config:
        return

    CHILD_CHANNEL_IDS = list(runtime_config["channels"]["1"])
    CHILD_CHANNEL_IDS_2 = list(runtime_config["channels"]["2"])
    CHILD_CHANNEL_IDS_3 = list(runtime_config["channels"]["3"])

    INTERVAL_MINUTES = runtime_config["interval_minutes"]["1"]
    INTERVAL_MINUTES_2 = runtime_config["interval_minutes"]["2"]
    INTERVAL_MINUTES_3 = runtime_config["interval_minutes"]["3"]

    POST_QTY = runtime_config["post_qty"]["1"]
    POST_QTY_2 = runtime_config["post_qty"]["2"]
    POST_QTY_3 = runtime_config["post_qty"]["3"]


def is_admin(user_id):
    return user_id == ADMIN_USER_ID


def pipeline_channels(pipeline_key):
    return list(runtime_config["channels"][pipeline_key])


def pipeline_disabled_set(pipeline_key):
    return set(runtime_config["disabled"][pipeline_key])


def pipeline_active_channels(pipeline_key):
    disabled = pipeline_disabled_set(pipeline_key)
    return [ch for ch in pipeline_channels(pipeline_key) if ch not in disabled]


def set_pipeline_interval(pipeline_key, minutes):
    runtime_config["interval_minutes"][pipeline_key] = int(minutes)
    save_runtime_config()
    sync_globals_from_config()


def set_pipeline_post_qty(pipeline_key, qty):
    runtime_config["post_qty"][pipeline_key] = max(1, int(qty))
    save_runtime_config()
    sync_globals_from_config()


def toggle_pipeline_channel(pipeline_key, channel_id):
    channel_id = int(channel_id)
    channels = runtime_config["channels"][pipeline_key]
    if channel_id not in channels:
        return False, "Channel not in list"

    disabled = runtime_config["disabled"][pipeline_key]
    if channel_id in disabled:
        disabled.remove(channel_id)
        enabled = True
    else:
        disabled.append(channel_id)
        enabled = False

    save_runtime_config()
    state = "enabled ✅" if enabled else "disabled ❌"
    return True, f"`{channel_id}` {state}"


def add_pipeline_channel(pipeline_key, channel_id):
    channel_id = int(channel_id)
    channels = runtime_config["channels"][pipeline_key]
    if channel_id in channels:
        return False, "Already in list"
    channels.append(channel_id)
    disabled = runtime_config["disabled"][pipeline_key]
    if channel_id in disabled:
        disabled.remove(channel_id)
    save_runtime_config()
    sync_globals_from_config()
    return True, f"Added `{channel_id}`"


def remove_pipeline_channel(pipeline_key, channel_id):
    channel_id = int(channel_id)
    channels = runtime_config["channels"][pipeline_key]
    if channel_id not in channels:
        return False, "Not in list"
    channels.remove(channel_id)
    disabled = runtime_config["disabled"][pipeline_key]
    if channel_id in disabled:
        disabled.remove(channel_id)
    save_runtime_config()
    sync_globals_from_config()
    return True, f"Removed `{channel_id}`"


async def source_channel_latest_msg_id(source_channel_id):
    latest = await bot.get_messages(source_channel_id, limit=1)
    if not latest:
        return None
    msg = latest[0] if isinstance(latest, list) else latest
    if not msg or not getattr(msg, "id", None):
        return None
    return msg.id


async def stop_at_source_end(running_flag_name, start_var_name, source_channel_id):
    latest_id = await source_channel_latest_msg_id(source_channel_id)
    current_msg_id = globals()[start_var_name]
    if latest_id is None or current_msg_id is None:
        return False

    if current_msg_id > latest_id:
        await report_issue(
            f"🛑 Reached end of source channel for `{running_flag_name}`\n"
            f"Last message id: `{latest_id}`\n"
            f"Next start id: `{current_msg_id}`\n"
            f"Pipeline auto-stopped (same as /stopbot)."
        )
        globals()[running_flag_name] = False
        return True

    return False


def admin_pipeline_title(pipeline_key):
    titles = {
        "1": "Set 1 — Pipeline 1 (Diskwala)",
        "2": "Set 2 — Pipeline 2 (Diskwala)",
        "3": "Set 3 — Pipeline 3 (Terabox)",
    }
    return titles.get(pipeline_key, f"Set {pipeline_key}")


def build_admin_main_buttons():
    return [
        [
            Button.inline("📦 Set 1", b"adm:p1"),
            Button.inline("📦 Set 2", b"adm:p2"),
            Button.inline("📦 Set 3", b"adm:p3"),
        ]
    ]


def shorten_button_text(text, max_len=30):
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1] + "…"


def format_channel_button_label(mark, channel_id, channel_name, max_len=64):
    channel_id = int(channel_id)
    id_part = f"{mark} {channel_id} "
    full = id_part + channel_name
    if len(full) <= max_len:
        return full

    # Id first; shorten name if needed.
    room_for_name = max_len - len(id_part)
    if room_for_name < 4:
        return shorten_button_text(f"{mark} {channel_id}", max_len=max_len)
    short_name = channel_name[: room_for_name - 1] + "…"
    return id_part + short_name


def format_channel_line(mark, channel_id, channel_name):
    return f"{mark} `{channel_id}` **{channel_name}**"


async def fetch_channel_title(channel_id, refresh=False):
    channel_id = int(channel_id)
    key = str(channel_id)
    titles = runtime_config.setdefault("channel_titles", {})

    if not refresh and titles.get(key):
        return titles[key]

    try:
        entity = await bot.get_entity(channel_id)
        title = getattr(entity, "title", None)
        if not title:
            username = getattr(entity, "username", None)
            if username:
                title = f"@{username}"
            else:
                first = getattr(entity, "first_name", None) or ""
                last = getattr(entity, "last_name", None) or ""
                title = f"{first} {last}".strip() or key
        titles[key] = title
        save_runtime_config()
        return title
    except Exception as fetch_error:
        print(f"Channel title lookup failed for {channel_id}: {fetch_error}")
        fallback = titles.get(key) or f"Channel {key[-6:]}"
        return fallback


async def build_admin_pipeline_buttons(pipeline_key):
    pk = pipeline_key
    interval = runtime_config["interval_minutes"][pk]
    qty = runtime_config["post_qty"][pk]
    rows = [
        [
            Button.inline(f"⏱ {interval}m ✓", f"adm:i{pk}:{interval}".encode()),
        ],
        [
            Button.inline("15m", f"adm:i{pk}:15".encode()),
            Button.inline("30m", f"adm:i{pk}:30".encode()),
            Button.inline("45m", f"adm:i{pk}:45".encode()),
            Button.inline("60m", f"adm:i{pk}:60".encode()),
        ],
        [
            Button.inline("120m", f"adm:i{pk}:120".encode()),
            Button.inline("150m", f"adm:i{pk}:150".encode()),
        ],
        [
            Button.inline(f"📦 qty {qty} ✓", f"adm:q{pk}:{qty}".encode()),
        ],
        [
            Button.inline("1", f"adm:q{pk}:1".encode()),
            Button.inline("2", f"adm:q{pk}:2".encode()),
            Button.inline("3", f"adm:q{pk}:3".encode()),
            Button.inline("5", f"adm:q{pk}:5".encode()),
        ],
    ]

    disabled = pipeline_disabled_set(pk)
    for idx, channel_id in enumerate(pipeline_channels(pk)):
        mark = "✅" if channel_id not in disabled else "❌"
        channel_name = await fetch_channel_title(channel_id)
        label = format_channel_button_label(mark, channel_id, channel_name)
        rows.append(
            [
                Button.inline(label, f"adm:t{pk}:{idx}".encode()),
                Button.inline("🗑", f"adm:r{pk}:{idx}".encode()),
            ]
        )

    rows.append([Button.inline("➕ Add channel", f"adm:a{pk}".encode())])
    rows.append([Button.inline("« Back", b"adm:home")])
    return rows


async def admin_pipeline_text(pipeline_key):
    pk = pipeline_key
    lines = [
        f"**{admin_pipeline_title(pk)}**",
        "",
        f"Interval: `{runtime_config['interval_minutes'][pk]}` min",
        f"Post qty: `{runtime_config['post_qty'][pk]}`",
        "",
        "**Channels:**",
    ]

    disabled = pipeline_disabled_set(pk)
    for channel_id in pipeline_channels(pk):
        mark = "✅" if channel_id not in disabled else "❌"
        channel_name = await fetch_channel_title(channel_id)
        lines.append(format_channel_line(mark, channel_id, channel_name))

    lines.extend(
        [
            "",
            "Tap ✅/❌ on a channel name to enable/disable posting.",
            "🗑 removes channel from this set.",
        ]
    )
    if pk == "1":
        lines.append("Commands: `/interval_120`, `/postqty_2`, `/addch1_ID`")
    else:
        lines.append(
            f"Commands: `/interval{pk}_120`, `/postqty{pk}_2`, `/addch{pk}_ID`"
        )
    return "\n".join(lines)


load_runtime_config()

MAIN_BUTTON = [
    [Button.url(
        "🔞 Join and See More 😉",
        "https://t.me/Diskwala_Viral_bot?start=1"
    )]
]

TERABOX_BUTTON = [
    [Button.url(
        "🥵 See Other Channels ⏬",
        "https://t.me/Diskwala_Viral_bot?start=1"
    )]
]



# -------- FOOTERS --------
FOOTER_1 = """<b>🤔 How to Open Links? | लिंक कैसे खोलें 👇</b>
<b><i><a href="https://t.me/howdisk/2">📖 View Tutorial</a></i></b>

😉<b>Daily Trending. Open 👇</b>
  bitly.cx/diskwala
"""
# 𝑷𝒍𝒆𝒂𝒔𝒆 𝑱𝒐𝒊𝒏 Backup 𝑪𝒉𝒂𝒏𝒏𝒆𝒍𝒔 Must 🙏

# 1. https://t.me/+vnLPLvMn8vQxMDVl
# 2. https://t.me/+P-MVSzKF3hsxMjA1
FOOTER_2 = """<b>🤔 How to Open Links? | लिंक कैसे खोलें 👇</b>
<b><i><a href="https://t.me/howdisk/2">📖 View Tutorial</a></i></b>

😉<b>Save this Link!⏬Visit Now</b>
  bitly.cx/diskwala
"""

# 🔥 𝑱𝒐𝒊𝒏 𝑩𝒂𝒄𝒌𝒖𝒑 𝑪𝒉𝒂𝒏𝒏𝒆𝒍 Must👇

# 1. https://t.me/+A6ausbTNqyZkNGE1
# 2. https://t.me/+vnLPLvMn8vQxMDVl
# FOOTER_3 = """<b><i><a href="https://t.me/Diskwala_Viral_bot?start=1">📖 View Diskwala Channels</a></i></b>

# 😉<b>Daily Video ⏬Open</b>
#  bitly.cx/diskwala
# """
# 🔥 𝑱𝒐𝒊𝒏 𝑩𝒂𝒄𝒌𝒖𝒑 𝑪𝒉𝒂𝒏𝒏𝒆𝒍 Must👇

# 1. https://t.me/+vnLPLvMn8vQxMDVl
# 2. https://t.me/+A6ausbTNqyZkNGE1


FOOTER_3 = """<b>🤔 ଲିଙ୍କ କେମିତି ଖୋଲିବେ? 👇</b>
<b><i><a href="https://t.me/howdisk/2">📖 ଟ୍ୟୁଟୋରିଆଲ୍ ଦେଖନ୍ତୁ</a></i></b>

😉<b>ଏହି ଲିଙ୍କଟି ସେଭ୍ କର! ⏬</b>
  bitly.cx/diskwala
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


@bot.on(events.NewMessage(pattern=r"^/admin$"))
async def admin_menu(event):
    if not is_admin(event.sender_id):
        return

    await event.respond(
        "**Admin panel** — pick a channel set to configure:",
        buttons=build_admin_main_buttons(),
        parse_mode="md",
    )


@bot.on(events.CallbackQuery)
async def admin_callback(event):
    if not is_admin(event.sender_id):
        await event.answer("Not allowed.", alert=True)
        return

    data = event.data.decode("utf-8")
    parts = data.split(":")

    if len(parts) < 2 or parts[0] != "adm":
        return

    action = parts[1]

    if action == "home":
        await event.edit(
            "**Admin panel** — pick a channel set:",
            buttons=build_admin_main_buttons(),
        )
        await event.answer()
        return

    if action.startswith("p") and len(action) == 2 and action[1] in "123":
        pipeline_key = action[1]
        await event.edit(
            await admin_pipeline_text(pipeline_key),
            buttons=await build_admin_pipeline_buttons(pipeline_key),
            parse_mode="md",
        )
        await event.answer()
        return

    if action.startswith("i") and len(parts) == 3:
        pipeline_key = action[1]
        minutes = int(parts[2])
        set_pipeline_interval(pipeline_key, minutes)
        await event.edit(
            await admin_pipeline_text(pipeline_key),
            buttons=await build_admin_pipeline_buttons(pipeline_key),
            parse_mode="md",
        )
        await event.answer(f"Interval → {minutes} min")
        return

    if action.startswith("q") and len(parts) == 3:
        pipeline_key = action[1]
        qty = int(parts[2])
        set_pipeline_post_qty(pipeline_key, qty)
        await event.edit(
            await admin_pipeline_text(pipeline_key),
            buttons=await build_admin_pipeline_buttons(pipeline_key),
            parse_mode="md",
        )
        await event.answer(f"Post qty → {qty}")
        return

    if action.startswith("t") and len(parts) == 3:
        pipeline_key = action[1]
        idx = int(parts[2])
        channels = pipeline_channels(pipeline_key)
        if idx < 0 or idx >= len(channels):
            await event.answer("Channel not found.", alert=True)
            return
        ok, _ = toggle_pipeline_channel(pipeline_key, channels[idx])
        channel_name = await fetch_channel_title(channels[idx])
        if ok:
            if channels[idx] in pipeline_disabled_set(pipeline_key):
                msg = f"{channel_name}: posting off ❌"
            else:
                msg = f"{channel_name}: posting on ✅"
        else:
            msg = "Channel not in list"
        await event.edit(
            await admin_pipeline_text(pipeline_key),
            buttons=await build_admin_pipeline_buttons(pipeline_key),
            parse_mode="md",
        )
        await event.answer(msg[:200], alert=not ok)
        return

    if action.startswith("r") and len(parts) == 3:
        pipeline_key = action[1]
        idx = int(parts[2])
        channels = pipeline_channels(pipeline_key)
        if idx < 0 or idx >= len(channels):
            await event.answer("Channel not found.", alert=True)
            return
        channel_name = await fetch_channel_title(channels[idx])
        ok, msg = remove_pipeline_channel(pipeline_key, channels[idx])
        if ok:
            msg = f"Removed {channel_name}"
        await event.edit(
            await admin_pipeline_text(pipeline_key),
            buttons=await build_admin_pipeline_buttons(pipeline_key),
            parse_mode="md",
        )
        await event.answer(msg[:200], alert=not ok)
        return

    if action.startswith("a") and len(action) == 2 and action[1] in "123":
        pipeline_key = action[1]
        pending_admin_action[event.sender_id] = {
            "action": "add_channel",
            "pipeline": pipeline_key,
        }
        await event.answer("Send channel id (e.g. -1001234567890)", alert=True)
        return


@bot.on(events.NewMessage)
async def admin_pending_input(event):
    if not is_admin(event.sender_id):
        return

    pending = pending_admin_action.get(event.sender_id)
    if not pending:
        return

    text = (event.raw_text or "").strip()
    if text.startswith("/"):
        return

    match = re.match(r"^-?\d+$", text)
    if not match:
        return

    if pending.get("action") != "add_channel":
        return

    pipeline_key = pending["pipeline"]
    del pending_admin_action[event.sender_id]

    channel_id = int(text)
    ok, msg = add_pipeline_channel(pipeline_key, channel_id)
    if ok:
        channel_name = await fetch_channel_title(channel_id, refresh=True)
        msg = f"Added **{channel_name}**"
    await event.respond(
        msg,
        buttons=await build_admin_pipeline_buttons(pipeline_key),
    )

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
    set_pipeline_interval("1", INTERVAL_MINUTES)

    await event.respond(
        f"⏱ Pipeline1 Interval = {INTERVAL_MINUTES}"
    )

@bot.on(events.NewMessage(pattern=r"^/postqty_(\d+)$"))
async def postqty(event):

    global POST_QTY

    POST_QTY = int(event.pattern_match.group(1))
    set_pipeline_post_qty("1", POST_QTY)

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

    if not pipeline_active_channels("1"):
        await event.respond("No active channels (check /admin Set 1)")
        return

    IS_RUNNING = True

    asyncio.create_task(
        run_pipeline(
            pipeline_key="1",
            source_channel_id=MASTER_CHANNEL_ID,
            start_var_name="START_FROM_MSG_ID",
            interval_var_name="INTERVAL_MINUTES",
            post_qty_var_name="POST_QTY",
            footer_text=FOOTER_1,
            running_flag_name="IS_RUNNING",
            link_extractor=extract_diskwala_links,
            buttons=MAIN_BUTTON,
        )
    )

    await event.respond("🚀 Pipeline1 started")

@bot.on(events.NewMessage(pattern=r"^/stopbot$"))
async def stop_cmd(event):

    global IS_RUNNING

    IS_RUNNING = False

    await event.respond("🛑 Pipeline1 stopped")


@bot.on(events.NewMessage(pattern=r"^/addch1_(-?\d+)$"))
async def addch1(event):
    if not is_admin(event.sender_id):
        return
    ok, msg = add_pipeline_channel("1", int(event.pattern_match.group(1)))
    await event.respond(msg)


@bot.on(events.NewMessage(pattern=r"^/removech1_(-?\d+)$"))
async def removech1(event):
    if not is_admin(event.sender_id):
        return
    ok, msg = remove_pipeline_channel("1", int(event.pattern_match.group(1)))
    await event.respond(msg)

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
    set_pipeline_interval("2", INTERVAL_MINUTES_2)

    await event.respond(
        f"⏱ Pipeline2 Interval = {INTERVAL_MINUTES_2}"
    )

@bot.on(events.NewMessage(pattern=r"^/postqty2_(\d+)$"))
async def postqty2(event):

    global POST_QTY_2

    POST_QTY_2 = int(event.pattern_match.group(1))
    set_pipeline_post_qty("2", POST_QTY_2)

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

    if not pipeline_active_channels("2"):
        await event.respond("No active channels (check /admin Set 2)")
        return

    IS_RUNNING_2 = True

    asyncio.create_task(
        run_pipeline(
            pipeline_key="2",
            source_channel_id=MASTER_CHANNEL_ID,
            start_var_name="START_FROM_MSG_ID_2",
            interval_var_name="INTERVAL_MINUTES_2",
            post_qty_var_name="POST_QTY_2",
            footer_text=FOOTER_2,
            running_flag_name="IS_RUNNING_2",
            link_extractor=extract_diskwala_links,
            buttons=MAIN_BUTTON,
        )
    )

    await event.respond("🚀 Pipeline2 started")

@bot.on(events.NewMessage(pattern=r"^/stopbot_2$"))
async def stopbot2(event):

    global IS_RUNNING_2

    IS_RUNNING_2 = False

    await event.respond("🛑 Pipeline2 stopped")


@bot.on(events.NewMessage(pattern=r"^/addch2_(-?\d+)$"))
async def addch2(event):
    if not is_admin(event.sender_id):
        return
    ok, msg = add_pipeline_channel("2", int(event.pattern_match.group(1)))
    await event.respond(msg)


@bot.on(events.NewMessage(pattern=r"^/removech2_(-?\d+)$"))
async def removech2(event):
    if not is_admin(event.sender_id):
        return
    ok, msg = remove_pipeline_channel("2", int(event.pattern_match.group(1)))
    await event.respond(msg)

# =========================================================
# ================= PIPELINE 3 TERABOX COMMANDS ===========
# =========================================================

@bot.on(events.NewMessage(pattern=r"^/startfrom3(?:_|\s+)(\d+)$"))
async def startfrom3(event):

    global START_FROM_MSG_ID_3

    START_FROM_MSG_ID_3 = int(event.pattern_match.group(1))

    await event.respond(
        f"Pipeline3 Terabox Start ID = {START_FROM_MSG_ID_3}"
    )

@bot.on(events.NewMessage(pattern=r"^/interval3(?:_|\s+)(\d+)$"))
async def interval3(event):

    global INTERVAL_MINUTES_3

    INTERVAL_MINUTES_3 = int(event.pattern_match.group(1))
    set_pipeline_interval("3", INTERVAL_MINUTES_3)

    await event.respond(
        f"Pipeline3 Terabox Interval = {INTERVAL_MINUTES_3}"
    )

@bot.on(events.NewMessage(pattern=r"^/postqty3(?:_|\s+)(\d+)$"))
async def postqty3(event):

    global POST_QTY_3

    POST_QTY_3 = int(event.pattern_match.group(1))
    set_pipeline_post_qty("3", POST_QTY_3)

    await event.respond(
        f"Pipeline3 Terabox Qty = {POST_QTY_3}"
    )

@bot.on(events.NewMessage(pattern=r"^/footer3(?:\s+([\s\S]+))?$"))
async def footer3(event):

    global FOOTER_3

    new_footer = event.pattern_match.group(1)

    if not new_footer:
        reply = await event.get_reply_message()
        new_footer = reply.text if reply else None

    if not new_footer:
        await event.respond(
            "Send /footer3 your footer text, or reply /footer3 to a footer message."
        )
        return

    FOOTER_3 = new_footer.strip()

    await event.respond("Pipeline3 Terabox footer updated")

@bot.on(events.NewMessage(pattern=r"^/run3$"))
async def run3(event):

    global IS_RUNNING_3

    if START_FROM_MSG_ID_3 is None:
        await event.respond("Set /startfrom3_<id> first")
        return

    if not pipeline_active_channels("3"):
        await event.respond("No active Terabox child channels (check /admin Set 3)")
        return

    if IS_RUNNING_3:
        await event.respond("Pipeline3 Terabox already running")
        return

    IS_RUNNING_3 = True

    asyncio.create_task(
        run_pipeline(
            pipeline_key="3",
            source_channel_id=MASTER_CHANNEL_ID2,
            start_var_name="START_FROM_MSG_ID_3",
            interval_var_name="INTERVAL_MINUTES_3",
            post_qty_var_name="POST_QTY_3",
            footer_text=FOOTER_3,
            running_flag_name="IS_RUNNING_3",
            link_extractor=extract_diskwala_links,
            buttons=TERABOX_BUTTON,
        )
    )

    await event.respond("Pipeline3 Terabox started")

@bot.on(events.NewMessage(pattern=r"^/stopbot_?3$"))
async def stopbot3(event):

    global IS_RUNNING_3

    IS_RUNNING_3 = False

    await event.respond("Pipeline3 Terabox stopped")


@bot.on(events.NewMessage(pattern=r"^/addch3_(-?\d+)$"))
async def addch3(event):
    if not is_admin(event.sender_id):
        return
    ok, msg = add_pipeline_channel("3", int(event.pattern_match.group(1)))
    await event.respond(msg)


@bot.on(events.NewMessage(pattern=r"^/removech3_(-?\d+)$"))
async def removech3(event):
    if not is_admin(event.sender_id):
        return
    ok, msg = remove_pipeline_channel("3", int(event.pattern_match.group(1)))
    await event.respond(msg)

# =========================================================
# ==================== MAIN PIPELINE ======================
# =========================================================

async def run_pipeline(
    pipeline_key,
    source_channel_id,
    start_var_name,
    interval_var_name,
    post_qty_var_name,
    footer_text,
    running_flag_name,
    link_extractor,
    buttons,
):

    child_channels = pipeline_active_channels(pipeline_key)

    if not child_channels:

        await report_issue(
            f"❌ No active child channels for {running_flag_name} (Set {pipeline_key})"
        )

        globals()[running_flag_name] = False
        return

    child_index = 0
    disabled_channels = set()
    config_disabled = pipeline_disabled_set(pipeline_key)

    while globals()[running_flag_name]:

        child_channels = pipeline_active_channels(pipeline_key)
        config_disabled = pipeline_disabled_set(pipeline_key)

        # 🔥 LIVE VALUES
        current_msg_id = globals()[start_var_name]
        interval_minutes = globals()[interval_var_name]
        post_qty = globals()[post_qty_var_name]

        if current_msg_id is None:
            await asyncio.sleep(5)
            continue

        if await stop_at_source_end(
            running_flag_name, start_var_name, source_channel_id
        ):
            return

        if not child_channels:

            await report_issue(
                f"❌ No active channels for {running_flag_name} (Set {pipeline_key})"
            )

            globals()[running_flag_name] = False
            return

        target = child_channels[child_index % len(child_channels)]

        if target in disabled_channels or target in config_disabled:

            child_index += 1

            if child_index >= len(child_channels):
                child_index = 0

            await asyncio.sleep(1)
            continue

        sent_count = 0

        while sent_count < post_qty and globals()[running_flag_name]:

            try:

                if await stop_at_source_end(
                    running_flag_name, start_var_name, source_channel_id
                ):
                    return

                msg = await bot.get_messages(
                    source_channel_id,
                    ids=current_msg_id
                )

                if not msg:
                    current_msg_id += 1
                    globals()[start_var_name] = current_msg_id
                    if await stop_at_source_end(
                        running_flag_name, start_var_name, source_channel_id
                    ):
                        return
                    continue

                text = msg.text or msg.caption

                if not text:
                    current_msg_id += 1
                    globals()[start_var_name] = current_msg_id
                    continue

                links = link_extractor(text)

                if not links:
                    current_msg_id += 1
                    globals()[start_var_name] = current_msg_id
                    continue

                links_block = "\n\n➡️".join(links)

                new_text = f"""🎬 Vdo 😍** 🔗🔗यह रहा वीडियो लिंक 👇**

{links_block}

{footer_text}
"""

                # Pipeline-specific static button.
                selected_button = buttons

                # -------- SEND --------

                # if msg.media:
                #
                #     await bot.send_file(
                #         target,
                #         msg.media,
                #         caption=new_text,
                #         buttons=selected_button,
                #         parse_mode="html"
                #     )
                #
                # else:
                #
                #     await bot.send_message(
                #         target,
                #         new_text,
                #         buttons=selected_button,
                #         parse_mode="html"
                #     )
                if isinstance(msg.media, (MessageMediaPhoto, MessageMediaDocument)):

                    await bot.send_file(
                        target,
                        msg.media,
                        caption=new_text,
                        buttons=selected_button,
                        parse_mode="html"
                    )

                # Text OR webpage preview (Terabox/Diskwala link only)
                else:

                    await bot.send_message(
                        target,
                        new_text,
                        buttons=selected_button,
                        parse_mode="html",
                        link_preview=True
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
