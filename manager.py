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
    ChatRestrictedError,
    UserBannedInChannelError,
    BotMethodInvalidError,
)
from telethon.tl.types import (
    MessageMediaPhoto,
    MessageMediaDocument,
    MessageEmpty,
)
from dotenv import load_dotenv

# ---------------- LOAD ENV ----------------

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ---------------- CONFIG ----------------

MASTER_CHANNEL_ID = -1003324660206
# MASTER_CHANNEL_ID2 = -1003792045938
MASTER_CHANNEL_ID2 = -1003324660206

# -------- PIPELINE 1 CHANNELS --------

CHILD_CHANNEL_IDS = [
    -1003662286694,
    -1003440216101,
    -1003509258780,
    -1003610491355,
    -1003471521632,
    -1003981620549
]

# -------- PIPELINE 2 CHANNELS --------

CHILD_CHANNEL_IDS_2 = [
    -1004332767188,
    -1003729451436,
    -1003852141524,
    -1004482717052,
    -1003315790833,
    -1003655989898
]

# -------- PIPELINE 3 TERABOX CHANNELS --------

CHILD_CHANNEL_IDS_3 = [
    -1004384690409,
    -1004357248388,
    -1003882375411,
    -1003786388714
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
    "start_msg_id": {"1": None, "2": None, "3": None},
    "current_msg_id": {"1": None, "2": None, "3": None},
    "last_posted_id": {"1": None, "2": None, "3": None},
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

PIPELINE_TASKS = {"1": None, "2": None, "3": None}

# Consecutive missing message ids fallback limit if source end cannot be queried.
SOURCE_ID_MISS_LIMIT = 150

LOG_USER_ID = 6796879431
ADMIN_USER_ID = LOG_USER_ID

runtime_config = {}
pending_admin_action = {}

# ---------------- TELETHON CLIENT ----------------

bot = TelegramClient("diskwala_bot", API_ID, API_HASH)


async def fetch_source_message(source_channel_id, message_id):
    """Fetch one message by id (GetMessages — not GetHistory). Bot must be in source channel."""
    result = await bot.get_messages(source_channel_id, ids=int(message_id))
    if isinstance(result, list):
        return result[0] if result else None
    return result


async def get_source_latest_message_id(source_channel_id):
    """Fetch the latest message ID currently in the source channel."""
    try:
        result = await bot.get_messages(source_channel_id, limit=1)
        if result and len(result) > 0:
            return result[0].id
    except Exception as err:
        print(f"Failed to fetch latest source id from {source_channel_id}: {err}")
    return None

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
            merged["channels"][pipeline_key] = [
                int(channel_id) for channel_id in loaded["channels"][pipeline_key]
            ]
        if pipeline_key in loaded.get("disabled", {}):
            merged["disabled"][pipeline_key] = [
                int(channel_id) for channel_id in loaded["disabled"][pipeline_key]
            ]
        if pipeline_key in loaded.get("interval_minutes", {}):
            merged["interval_minutes"][pipeline_key] = int(
                loaded["interval_minutes"][pipeline_key]
            )
        if pipeline_key in loaded.get("post_qty", {}):
            merged["post_qty"][pipeline_key] = int(loaded["post_qty"][pipeline_key])
        start_ids = loaded.get("start_msg_id", {})
        if pipeline_key in start_ids and start_ids[pipeline_key] is not None:
            merged["start_msg_id"][pipeline_key] = int(start_ids[pipeline_key])
        curr_ids = loaded.get("current_msg_id", {})
        if pipeline_key in curr_ids and curr_ids[pipeline_key] is not None:
            merged["current_msg_id"][pipeline_key] = int(curr_ids[pipeline_key])
        last_ids = loaded.get("last_posted_id", {})
        if pipeline_key in last_ids and last_ids[pipeline_key] is not None:
            merged["last_posted_id"][pipeline_key] = int(last_ids[pipeline_key])

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
    global START_FROM_MSG_ID, START_FROM_MSG_ID_2, START_FROM_MSG_ID_3

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

    start_ids = runtime_config.setdefault("start_msg_id", {"1": None, "2": None, "3": None})
    curr_ids = runtime_config.setdefault("current_msg_id", {"1": None, "2": None, "3": None})

    # Never overwrite a live running pointer with old config during settings changes!
    if not pipeline_is_running("1"):
        START_FROM_MSG_ID = curr_ids.get("1") if curr_ids.get("1") is not None else start_ids.get("1")
    if not pipeline_is_running("2"):
        START_FROM_MSG_ID_2 = curr_ids.get("2") if curr_ids.get("2") is not None else start_ids.get("2")
    if not pipeline_is_running("3"):
        START_FROM_MSG_ID_3 = curr_ids.get("3") if curr_ids.get("3") is not None else start_ids.get("3")


def set_pipeline_start_id(pipeline_key, message_id):
    pipeline_key = str(pipeline_key)
    message_id = int(message_id)
    runtime_config.setdefault("start_msg_id", {"1": None, "2": None, "3": None})[
        pipeline_key
    ] = message_id
    runtime_config.setdefault("current_msg_id", {"1": None, "2": None, "3": None})[
        pipeline_key
    ] = message_id
    runtime_config.setdefault("last_posted_id", {"1": None, "2": None, "3": None})[
        pipeline_key
    ] = None
    save_runtime_config()

    var_map = {
        "1": "START_FROM_MSG_ID",
        "2": "START_FROM_MSG_ID_2",
        "3": "START_FROM_MSG_ID_3",
    }
    globals()[var_map[pipeline_key]] = message_id


def get_pipeline_start_id(pipeline_key):
    start_ids = runtime_config.get("start_msg_id", {})
    return start_ids.get(str(pipeline_key))


def save_pipeline_progress(pipeline_key, current_id, last_posted_id=None):
    pipeline_key = str(pipeline_key)
    runtime_config.setdefault("current_msg_id", {"1": None, "2": None, "3": None})[
        pipeline_key
    ] = int(current_id)
    if last_posted_id is not None:
        runtime_config.setdefault("last_posted_id", {"1": None, "2": None, "3": None})[
            pipeline_key
        ] = int(last_posted_id)
    save_runtime_config()


def set_pipeline_last_posted_id(pipeline_key, message_id):
    pipeline_key = str(pipeline_key)
    runtime_config.setdefault("last_posted_id", {"1": None, "2": None, "3": None})[
        pipeline_key
    ] = int(message_id)
    save_runtime_config()


def get_pipeline_last_posted_id(pipeline_key):
    last_ids = runtime_config.get("last_posted_id", {})
    return last_ids.get(str(pipeline_key))


def get_pipeline_current_msg_id(pipeline_key):
    pipeline_key = str(pipeline_key)
    var_map = {
        "1": "START_FROM_MSG_ID",
        "2": "START_FROM_MSG_ID_2",
        "3": "START_FROM_MSG_ID_3",
    }
    var_name = var_map.get(pipeline_key)
    live_val = globals().get(var_name) if var_name else None
    if live_val is not None:
        return live_val
    curr_ids = runtime_config.get("current_msg_id", {})
    if curr_ids.get(pipeline_key) is not None:
        return curr_ids[pipeline_key]
    return get_pipeline_start_id(pipeline_key)


def pipeline_is_running(pipeline_key):
    running_map = {"1": "IS_RUNNING", "2": "IS_RUNNING_2", "3": "IS_RUNNING_3"}
    return bool(globals()[running_map[pipeline_key]])


def stop_pipeline(pipeline_key):
    pipeline_key = str(pipeline_key)
    running_map = {"1": "IS_RUNNING", "2": "IS_RUNNING_2", "3": "IS_RUNNING_3"}
    globals()[running_map[pipeline_key]] = False
    task = PIPELINE_TASKS.get(pipeline_key)
    if task and not task.done():
        task.cancel()
    PIPELINE_TASKS[pipeline_key] = None


def is_admin(user_id):
    return user_id == ADMIN_USER_ID


def pipeline_channels(pipeline_key):
    return list(runtime_config["channels"][pipeline_key])


def pipeline_disabled_set(pipeline_key):
    return set(int(channel_id) for channel_id in runtime_config["disabled"][pipeline_key])


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


async def notify_source_id_exhausted(
    running_flag_name, start_var_name, miss_streak, source_channel_id
):
    current_msg_id = globals()[start_var_name]
    pipeline_key = "1" if running_flag_name == "IS_RUNNING" else ("2" if "2" in running_flag_name else "3")
    last_posted = get_pipeline_last_posted_id(pipeline_key)
    last_posted_line = f"\nLast posted msg id: `{last_posted}`" if last_posted is not None else ""
    await report_issue(
        f"🛑 `{running_flag_name}` auto-stopped\n"
        f"No message at `{miss_streak}` ids in a row (from `{current_msg_id - miss_streak}`)."
        f"{last_posted_line}\n"
        f"Source: `{source_channel_id}`\n"
        f"Likely past last post — set a new start id or use /stopbot."
    )
    globals()[running_flag_name] = False


CHANNEL_POST_FAILURES = (
    PeerIdInvalidError,
    ChannelPrivateError,
    ChatWriteForbiddenError,
    ChatRestrictedError,
    UserBannedInChannelError,
)


async def deliver_post_to_channel(target, msg, new_text, selected_button):
    """Send to one child channel; text-only fallback if media is restricted."""
    if isinstance(msg.media, (MessageMediaPhoto, MessageMediaDocument)):
        try:
            await bot.send_file(
                target,
                msg.media,
                caption=new_text,
                buttons=selected_button,
                parse_mode="html",
            )
            return
        except ChatRestrictedError:
            print(f"Media restricted in {target}, sending text-only")

    await bot.send_message(
        target,
        new_text,
        buttons=selected_button,
        parse_mode="html",
        link_preview=True,
    )


async def mark_posting_channel_failed(
    pipeline_key, target, running_flag_name, disabled_channels, error
):
    disabled_channels.add(target)
    channel_id = int(target)
    config_disabled = runtime_config["disabled"][pipeline_key]
    if channel_id not in config_disabled:
        config_disabled.append(channel_id)
        save_runtime_config()

    await report_issue(
        f"❌ Skipping channel `{target}` for `{running_flag_name}`\n"
        f"{type(error).__name__}: {error}\n"
        f"Turned off in /admin (✅ to re-enable when fixed)."
    )
    print(f"Skipped {target}: {error}")


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
            Button.inline(
                "⏹ Stop" if pipeline_is_running(pk) else "▶ Run",
                f"adm:{'stop' if pipeline_is_running(pk) else 'run'}:{pk}".encode(),
            ),
            Button.inline("✏ Start ID", f"adm:set:{pk}".encode()),
        ],
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
    pk = str(pipeline_key)
    start_id = get_pipeline_start_id(pk)
    last_posted_id = get_pipeline_last_posted_id(pk)
    current_scan_id = get_pipeline_current_msg_id(pk)
    running_label = "🟢 Running" if pipeline_is_running(pk) else "⚪ Stopped"
    lines = [
        f"**{admin_pipeline_title(pk)}**",
        "",
        f"Status: {running_label}",
        f"Start msg id: `{start_id if start_id is not None else 'not set'}`",
        f"Current msg id: `{current_scan_id if current_scan_id is not None else 'not set'}`",
        f"Last posted id: `{last_posted_id if last_posted_id is not None else 'None yet'}`",
    ]

    source_id = MASTER_CHANNEL_ID if pk in ("1", "2") else MASTER_CHANNEL_ID2
    src_latest = await get_source_latest_message_id(source_id)
    if src_latest is not None:
        lines.append(f"Source latest id: `{src_latest}`")
        ref_id = current_scan_id if current_scan_id is not None else (last_posted_id or start_id)
        if ref_id is not None:
            rem = max(0, src_latest - ref_id + 1)
            lines.append(f"Remaining in source: `~{rem}`")

    lines.extend(
        [
            f"Interval: `{runtime_config['interval_minutes'][pk]}` min",
            f"Post qty: `{runtime_config['post_qty'][pk]}`",
            "",
            "**Channels:**",
        ]
    )

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
        "https://t.me/Viral_diskwala_bot?start=1"
    )]
]

TERABOX_BUTTON = [
    [Button.url(
        "🥵 See Other Channels ⏬",
        "https://t.me/Viral_diskwala_bot?start=1"
    )]
]



FOOTER_1 = """<b>🤔 How to Open Links? | लिंक कैसे खोलें 👇</b>
<b><i><a href="https://t.me/howdisk/2">📖 View Tutorial</a></i></b>

😉<b>Join Backup Must 👇</b>
  t.me/+zSaZL31c2EM5N2E9
"""

FOOTER_2 = """<b>🤔 How to Open Links? | लिंक कैसे खोलें 👇</b>
<b><i><a href="https://t.me/howdisk/2">📖 View Tutorial</a></i></b>

😉<b>Join Backup Must 👇</b>
  t.me/+zSaZL31c2EM5N2E9
"""

FOOTER_3 ="""<b>🤔 How to Open Links? | लिंक कैसे खोलें 👇</b>
<b><i><a href="https://t.me/howdisk/2">📖 View Tutorial</a></i></b>

😉<b>Join Backup Must 👇</b>
  t.me/+zSaZL31c2EM5N2E9
"""


def build_run_pipeline_kwargs(pipeline_key):
    if pipeline_key == "1":
        return {
            "pipeline_key": "1",
            "source_channel_id": MASTER_CHANNEL_ID,
            "start_var_name": "START_FROM_MSG_ID",
            "interval_var_name": "INTERVAL_MINUTES",
            "post_qty_var_name": "POST_QTY",
            "footer_text": FOOTER_1,
            "running_flag_name": "IS_RUNNING",
            "link_extractor": extract_diskwala_links,
            "buttons": MAIN_BUTTON,
        }
    if pipeline_key == "2":
        return {
            "pipeline_key": "2",
            "source_channel_id": MASTER_CHANNEL_ID,
            "start_var_name": "START_FROM_MSG_ID_2",
            "interval_var_name": "INTERVAL_MINUTES_2",
            "post_qty_var_name": "POST_QTY_2",
            "footer_text": FOOTER_2,
            "running_flag_name": "IS_RUNNING_2",
            "link_extractor": extract_diskwala_links,
            "buttons": MAIN_BUTTON,
        }
    return {
        "pipeline_key": "3",
        "source_channel_id": MASTER_CHANNEL_ID2,
        "start_var_name": "START_FROM_MSG_ID_3",
        "interval_var_name": "INTERVAL_MINUTES_3",
        "post_qty_var_name": "POST_QTY_3",
        "footer_text": FOOTER_3,
        "running_flag_name": "IS_RUNNING_3",
        "link_extractor": extract_diskwala_links,
        "buttons": TERABOX_BUTTON,
    }


async def launch_pipeline(pipeline_key):
    pipeline_key = str(pipeline_key)
    if pipeline_key not in ("1", "2", "3"):
        return False, "Invalid set"

    kwargs = build_run_pipeline_kwargs(pipeline_key)
    running_var = kwargs["running_flag_name"]
    start_var = kwargs["start_var_name"]

    existing_task = PIPELINE_TASKS.get(pipeline_key)
    if existing_task and not existing_task.done() and globals()[running_var]:
        return False, "Already running"

    if existing_task and not existing_task.done():
        existing_task.cancel()
        try:
            await existing_task
        except (asyncio.CancelledError, Exception):
            pass

    if globals()[start_var] is None:
        return False, "Set start message id first"

    if not pipeline_active_channels(pipeline_key):
        return False, "No active channels in this set"

    globals()[running_var] = True
    PIPELINE_TASKS[pipeline_key] = asyncio.create_task(run_pipeline(**kwargs))
    return True, f"Set {pipeline_key} started 🚀"


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

    if action == "run" and len(parts) == 3:
        pipeline_key = parts[2]
        ok, msg = await launch_pipeline(pipeline_key)
        await event.edit(
            await admin_pipeline_text(pipeline_key),
            buttons=await build_admin_pipeline_buttons(pipeline_key),
            parse_mode="md",
        )
        await event.answer(msg[:200], alert=not ok)
        return

    if action == "stop" and len(parts) == 3:
        pipeline_key = parts[2]
        stop_pipeline(pipeline_key)
        await event.edit(
            await admin_pipeline_text(pipeline_key),
            buttons=await build_admin_pipeline_buttons(pipeline_key),
            parse_mode="md",
        )
        await event.answer(f"Set {pipeline_key} stopped 🛑")
        return

    if action == "set" and len(parts) == 3:
        pipeline_key = parts[2]
        pending_admin_action[event.sender_id] = {
            "action": "set_start_id",
            "pipeline": pipeline_key,
        }
        current = get_pipeline_start_id(pipeline_key)
        hint = f" current: {current}" if current is not None else ""
        await event.answer(
            f"Send start message id (number).{hint}",
            alert=True,
        )
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

    if pending.get("action") == "add_channel":
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
        return

    if pending.get("action") == "set_start_id":
        pipeline_key = pending["pipeline"]
        del pending_admin_action[event.sender_id]
        set_pipeline_start_id(pipeline_key, int(text))
        await event.respond(
            f"Set {pipeline_key} start msg id = `{int(text)}`",
            buttons=await build_admin_pipeline_buttons(pipeline_key),
            parse_mode="md",
        )
        return

# =========================================================
# ================= PIPELINE 1 COMMANDS ===================
# =========================================================

@bot.on(events.NewMessage(pattern=r"^/startfrom_(\d+)$"))
async def startfrom(event):

    global START_FROM_MSG_ID

    START_FROM_MSG_ID = int(event.pattern_match.group(1))
    set_pipeline_start_id("1", START_FROM_MSG_ID)

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

    ok, msg = await launch_pipeline("1")
    await event.respond(msg if ok else f"❌ {msg}")

@bot.on(events.NewMessage(pattern=r"^/stopbot$"))
async def stop_cmd(event):

    stop_pipeline("1")
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
    set_pipeline_start_id("2", START_FROM_MSG_ID_2)

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

    ok, msg = await launch_pipeline("2")
    await event.respond(msg if ok else f"❌ {msg}")

@bot.on(events.NewMessage(pattern=r"^/stopbot_2$"))
async def stopbot2(event):

    stop_pipeline("2")
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
    set_pipeline_start_id("3", START_FROM_MSG_ID_3)

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

    ok, msg = await launch_pipeline("3")
    await event.respond(msg if ok else f"❌ {msg}")

@bot.on(events.NewMessage(pattern=r"^/stopbot_?3$"))
async def stopbot3(event):

    stop_pipeline("3")
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
    try:
        await _run_pipeline_loop(
            pipeline_key,
            source_channel_id,
            start_var_name,
            interval_var_name,
            post_qty_var_name,
            footer_text,
            running_flag_name,
            link_extractor,
            buttons,
        )
    except asyncio.CancelledError:
        print(f"[{running_flag_name}] Task cancelled cleanly")
        globals()[running_flag_name] = False
    except Exception as pipeline_error:
        print(f"{running_flag_name} crashed: {pipeline_error}")
        await report_issue(
            f"⚠️ `{running_flag_name}` crashed\n"
            f"{type(pipeline_error).__name__}: {pipeline_error}"
        )
        globals()[running_flag_name] = False


async def _run_pipeline_loop(
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
    source_miss_streak = 0

    while globals()[running_flag_name]:
        child_channels = pipeline_active_channels(pipeline_key)
        postable = [
            ch for ch in child_channels if ch not in disabled_channels
        ]

        current_msg_id = globals()[start_var_name]
        interval_minutes = globals()[interval_var_name]
        post_qty = globals()[post_qty_var_name]

        if current_msg_id is None:
            await asyncio.sleep(5)
            continue

        if not postable:
            await report_issue(
                f"🛑 All posting channels failed for {running_flag_name}"
            )
            globals()[running_flag_name] = False
            return

        # Check latest post in source channel
        latest_source_id = await get_source_latest_message_id(source_channel_id)
        if latest_source_id is not None and current_msg_id > latest_source_id:
            print(
                f"[{running_flag_name}] At msg {current_msg_id} > source latest {latest_source_id}. Waiting for new posts..."
            )
            total_sleep = max(1, interval_minutes) * 60
            for _ in range(total_sleep):
                if not globals()[running_flag_name]:
                    break
                await asyncio.sleep(1)
            continue

        target = postable[child_index % len(postable)]
        sent_count = 0

        while sent_count < post_qty and globals()[running_flag_name]:
            if latest_source_id is not None and current_msg_id > latest_source_id:
                latest_source_id = await get_source_latest_message_id(source_channel_id)
                if latest_source_id is not None and current_msg_id > latest_source_id:
                    print(
                        f"[{running_flag_name}] Reached end of source posts (latest: {latest_source_id}). Waiting for new posts..."
                    )
                    break

            send_started = False
            try:
                msg = await fetch_source_message(
                    source_channel_id,
                    current_msg_id,
                )

                if not msg or isinstance(msg, MessageEmpty):
                    source_miss_streak += 1
                    current_msg_id += 1
                    globals()[start_var_name] = current_msg_id
                    save_pipeline_progress(pipeline_key, current_msg_id)

                    if latest_source_id is None and source_miss_streak >= SOURCE_ID_MISS_LIMIT:
                        await notify_source_id_exhausted(
                            running_flag_name,
                            start_var_name,
                            source_miss_streak,
                            source_channel_id,
                        )
                        return

                    await asyncio.sleep(0.05)
                    continue

                source_miss_streak = 0
                text = msg.text or msg.caption

                if not text:
                    current_msg_id += 1
                    globals()[start_var_name] = current_msg_id
                    save_pipeline_progress(pipeline_key, current_msg_id)
                    continue

                links = link_extractor(text)
                if not links:
                    current_msg_id += 1
                    globals()[start_var_name] = current_msg_id
                    save_pipeline_progress(pipeline_key, current_msg_id)
                    continue

                links_block = "\n\n➡️".join(links)
                new_text = f"""🎬 Vdo 😍** 🔗🔗यह रहा वीडियो लिंक 👇**

{links_block}

{footer_text}
"""
                selected_button = buttons

                # -------- SEND --------
                send_started = True
                await deliver_post_to_channel(
                    target, msg, new_text, selected_button
                )
                print(
                    f"[{running_flag_name}] Posted {current_msg_id} → {target}"
                )

                sent_count += 1
                posted_id = current_msg_id
                current_msg_id += 1
                globals()[start_var_name] = current_msg_id
                save_pipeline_progress(pipeline_key, current_msg_id, last_posted_id=posted_id)

                await asyncio.sleep(1)

            except FloodWaitError as e:
                print(f"FloodWait {e.seconds}s")
                await asyncio.sleep(e.seconds)

            except CHANNEL_POST_FAILURES as e:
                await mark_posting_channel_failed(
                    pipeline_key,
                    target,
                    running_flag_name,
                    disabled_channels,
                    e,
                )
                break

            except BotMethodInvalidError as e:
                await report_issue(
                    f"❌ Cannot read source `{source_channel_id}` msg `{current_msg_id}` as bot.\n"
                    f"Add this bot as **admin** in the master/source channel, then /run again.\n"
                    f"{e}"
                )
                globals()[running_flag_name] = False
                return

            except Exception as e:
                print(
                    f"Error msg {current_msg_id} → {target}: {e}"
                )
                if send_started:
                    await mark_posting_channel_failed(
                        pipeline_key,
                        target,
                        running_flag_name,
                        disabled_channels,
                        e,
                    )
                    break

                await report_issue(
                    f"⚠️ Error on source msg `{current_msg_id}` (not sent)\n"
                    f"{type(e).__name__}: {e}"
                )
                current_msg_id += 1
                globals()[start_var_name] = current_msg_id
                save_pipeline_progress(pipeline_key, current_msg_id)

        # -------- ROTATE CHANNEL --------
        child_index += 1
        postable_after = [
            ch
            for ch in pipeline_active_channels(pipeline_key)
            if ch not in disabled_channels
        ]
        if postable_after:
            child_index %= len(postable_after)

        # -------- ALL DEAD --------
        if postable_after and len(disabled_channels) >= len(child_channels):
            await report_issue(
                f"🛑 All channels disabled for {running_flag_name}"
            )
            globals()[running_flag_name] = False
            break

        print(
            f"[{running_flag_name}] Waiting {interval_minutes} mins..."
        )

        total_sleep = max(1, interval_minutes) * 60
        for _ in range(total_sleep):
            if not globals()[running_flag_name]:
                break
            await asyncio.sleep(1)

    print(f"{running_flag_name} stopped")

# ---------------- START EVERYTHING ----------------

if __name__ == "__main__":

    print("Starting Flask keep-alive server...")

    threading.Thread(target=run_web, daemon=True).start()

    print("Starting Telegram bot...")


    async def startup():
        await bot.start(bot_token=BOT_TOKEN)
        print("Bot ready — source messages fetched by id via bot (no chat history)")

    bot.loop.run_until_complete(startup())
    bot.run_until_disconnected()
