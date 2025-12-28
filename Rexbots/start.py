# Rexbots
# Don't Remove Credit
# Telegram Channel @RexBots_Official

import os
import asyncio
import random
import time
import shutil
import math

import pyrogram
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import (
    FloodWait,
    AuthKeyUnregistered,
    UserDeactivated,
    UserDeactivatedBan
)

from config import API_ID, API_HASH, ERROR_MESSAGE
from database.db import db
from plugins.strings import HELP_TXT, COMMANDS_TXT
from logger import LOGGER

logger = LOGGER(__name__)

# =========================
# Utils
# =========================

def humanbytes(size):
    if not size:
        return "0 B"
    power = 1024
    n = 0
    Dic = {0: "B", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}
    while size > power and n < 4:
        size /= power
        n += 1
    return f"{round(size, 2)} {Dic[n]}"

def TimeFormatter(milliseconds: int) -> str:
    seconds, _ = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    result = []
    if hours:
        result.append(f"{hours}h")
    if minutes:
        result.append(f"{minutes}m")
    if seconds:
        result.append(f"{seconds}s")

    return " ".join(result) if result else "0s"

# =========================
# Batch State
# =========================

class BatchState:
    ACTIVE = {}

# =========================
# Progress Bar
# =========================

PROGRESS_BAR = """\
<b>{percent}%</b>
{bar}
<b>Speed:</b> {speed}/s
<b>Size:</b> {current}/{total}
<b>ETA:</b> {eta}
"""

def progress(current, total, message: Message, tag):
    if BatchState.ACTIVE.get(message.from_user.id) is False:
        raise Exception("Cancelled")

    now = time.time()
    key = f"{message.id}_{tag}"

    if not hasattr(progress, "last"):
        progress.last = {}
        progress.start = {}

    if key not in progress.start:
        progress.start[key] = now

    if key in progress.last and now - progress.last[key] < 3:
        return

    percent = int(current * 100 / total)
    filled = int(percent / 10)
    bar = "▰" * filled + "▱" * (10 - filled)

    speed = current / max(now - progress.start[key], 1)
    eta = (total - current) / speed if speed else 0

    text = PROGRESS_BAR.format(
        percent=percent,
        bar=bar,
        speed=humanbytes(speed),
        current=humanbytes(current),
        total=humanbytes(total),
        eta=TimeFormatter(eta * 1000)
    )

    with open(f"{message.id}_{tag}.txt", "w") as f:
        f.write(text)

    progress.last[key] = now
# =========================
# /start Command
# =========================

@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🆘 How To Use", callback_data="help_btn"),
                InlineKeyboardButton("ℹ️ About Bot", callback_data="about_btn")
            ],
            [
                InlineKeyboardButton("⚙️ Commands", callback_data="settings_btn")
            ],
            [
                InlineKeyboardButton("📢 Official Channel", url="https://t.me/RexBots_Official")
            ]
        ]
    )

    await client.send_message(
        chat_id=message.chat.id,
        text=(
            f"<blockquote><b>👋 Welcome {message.from_user.mention}!</b></blockquote>\n\n"
            "<b>Save Restricted Content Bot</b>\n\n"
            "<blockquote>"
            "• Save restricted posts\n"
            "• Public & private channels\n"
            "• Batch / bulk supported\n"
            "</blockquote>\n\n"
            "<b>⚠️ Use <code>/login</code> before private downloads.</b>"
        ),
        reply_markup=buttons,
        parse_mode=enums.ParseMode.HTML
    )

# =========================
# Help Command
# =========================

@Client.on_message(filters.command("help") & filters.private)
async def help_cmd(client: Client, message: Message):
    await message.reply_text(
        HELP_TXT,
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )

# =========================
# Cancel Command
# =========================

@Client.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client: Client, message: Message):
    BatchState.ACTIVE[message.from_user.id] = False
    await message.reply_text("❌ Batch process cancelled.")

# =========================
# Inline Button Callbacks
# =========================

@Client.on_callback_query()
async def callbacks(client: Client, query):
    data = query.data
    msg = query.message

    if data == "help_btn":
        await msg.edit_text(
            HELP_TXT,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back", callback_data="start_btn")]]
            )
        )

    elif data == "about_btn":
        await msg.edit_text(
            "<b>Save Restricted Content Bot</b>\n\n"
            "Built using Pyrogram\n"
            "By @RexBots_Official",
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back", callback_data="start_btn")]]
            )
        )

    elif data == "settings_btn":
        await msg.edit_text(
            COMMANDS_TXT,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back", callback_data="start_btn")]]
            )
        )

    elif data == "start_btn":
        await start_cmd(client, msg)

    await query.answer()
# =========================
# Link / Batch Handler
# =========================

@Client.on_message(filters.private & filters.text & ~filters.command([]))
async def link_handler(client: Client, message: Message):
    text = message.text.strip()

    if "https://t.me/" not in text:
        return

    user_id = message.from_user.id

    # Prevent double batch
    if BatchState.ACTIVE.get(user_id) is False:
        return await message.reply_text(
            "⚠️ A batch is already running.\nUse /cancel to stop it."
        )

    BatchState.ACTIVE[user_id] = False

    parts = text.split("/")
    last = parts[-1].replace("?single", "")

    try:
        if "-" in last:
            start_id, end_id = map(int, last.split("-"))
        else:
            start_id = end_id = int(last)
    except:
        BatchState.ACTIVE[user_id] = True
        return await message.reply_text("❌ Invalid message range.")

    is_private = "/c/" in text

    # Get user session if needed
    acc = None
    if is_private:
        session = await db.get_session(user_id)
        if not session:
            BatchState.ACTIVE[user_id] = True
            return await message.reply_text(
                "❌ Private content requires /login first."
            )

        acc = Client(
            f"user_{user_id}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session,
            in_memory=True
        )
        await acc.connect()

    for msg_id in range(start_id, end_id + 1):
        if BatchState.ACTIVE.get(user_id):
            break

        try:
            # ---------- PUBLIC ----------
            if not is_private:
                username = parts[3]
                msg = await client.get_messages(username, msg_id)
                await client.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=msg.chat.id,
                    message_id=msg.id
                )
                await asyncio.sleep(1)
                continue

            # ---------- PRIVATE ----------
            chat_id = int("-100" + parts[4])
            msg = await acc.get_messages(chat_id, msg_id)

            await handle_private_message(
                client=client,
                acc=acc,
                src_msg=msg,
                dest_chat=message.chat.id,
                reply_to=message.id
            )

            await asyncio.sleep(2)

        except FloodWait as fw:
            await asyncio.sleep(fw.value)
        except Exception as e:
            if ERROR_MESSAGE:
                await message.reply_text(f"❌ Error: {e}")

    if acc:
        await acc.disconnect()

    BatchState.ACTIVE[user_id] = True
# =========================
# Private Message Handler
# =========================

async def handle_private_message(
    client: Client,
    acc: Client,
    src_msg: Message,
    dest_chat: int,
    reply_to: int
):
    if not src_msg or src_msg.empty:
        return

    # ---------- TEXT ----------
    if src_msg.text:
        await client.send_message(
            chat_id=dest_chat,
            text=src_msg.text,
            entities=src_msg.entities,
            reply_to_message_id=reply_to,
            parse_mode=enums.ParseMode.HTML
        )
        return

    status = await client.send_message(
        dest_chat,
        "⬇️ **Downloading...**",
        reply_to_message_id=reply_to
    )

    # ---------- TEMP DIR ----------
    base_dir = f"downloads/{dest_chat}_{src_msg.id}"
    os.makedirs(base_dir, exist_ok=True)

    file_path = None

    try:
        # ---------- DOWNLOAD ----------
        file_path = await acc.download_media(
            src_msg,
            file_name=base_dir + "/",
            progress=progress,
            progress_args=[status, "down"]
        )

        # ---------- UPLOAD ----------
        await status.edit_text("⬆️ **Uploading...**")

        caption = src_msg.caption or ""

        # ---------- DOCUMENT ----------
        if src_msg.document:
            await client.send_document(
                dest_chat,
                file_path,
                caption=caption,
                reply_to_message_id=reply_to,
                progress=progress,
                progress_args=[status, "up"]
            )

        # ---------- VIDEO (FIXED DURATION) ----------
        elif src_msg.video:
            await client.send_video(
                dest_chat,
                file_path,
                duration=src_msg.video.duration,
                width=src_msg.video.width,
                height=src_msg.video.height,
                supports_streaming=True,
                caption=caption,
                reply_to_message_id=reply_to,
                progress=progress,
                progress_args=[status, "up"]
            )

        # ---------- AUDIO ----------
        elif src_msg.audio:
            await client.send_audio(
                dest_chat,
                file_path,
                caption=caption,
                reply_to_message_id=reply_to,
                progress=progress,
                progress_args=[status, "up"]
            )

        # ---------- VOICE ----------
        elif src_msg.voice:
            await client.send_voice(
                dest_chat,
                file_path,
                caption=caption,
                reply_to_message_id=reply_to,
                progress=progress,
                progress_args=[status, "up"]
            )

        # ---------- PHOTO ----------
        elif src_msg.photo:
            await client.send_photo(
                dest_chat,
                file_path,
                caption=caption,
                reply_to_message_id=reply_to
            )

        # ---------- ANIMATION ----------
        elif src_msg.animation:
            await client.send_animation(
                dest_chat,
                file_path,
                caption=caption,
                reply_to_message_id=reply_to
            )

        # ---------- STICKER ----------
        elif src_msg.sticker:
            await client.send_sticker(
                dest_chat,
                file_path,
                reply_to_message_id=reply_to
            )

    except Exception as e:
        if ERROR_MESSAGE:
            await client.send_message(
                dest_chat,
                f"❌ Error while processing media:\n{e}",
                reply_to_message_id=reply_to
            )

    finally:
        # ---------- CLEANUP ----------
        try:
            await status.delete()
        except:
            pass

        if base_dir and os.path.exists(base_dir):
            try:
                shutil.rmtree(base_dir)
            except:
                pass
# =========================
# Safety: Session Errors
# =========================

@Client.on_message(filters.command("ping") & filters.private)
async def ping_cmd(client: Client, message: Message):
    await message.reply_text("🏓 Pong! Bot is alive.")


@Client.on_message(filters.command("status") & filters.private)
async def status_cmd(client: Client, message: Message):
    running = BatchState.ACTIVE.get(message.from_user.id, True)
    await message.reply_text(
        "🟢 Idle" if running else "🟡 Batch Running"
    )


# =========================
# Global Error Guard
# =========================

@Client.on_message(filters.private)
async def fallback_handler(client: Client, message: Message):
    """
    Fallback to prevent silent crashes.
    Does NOT override commands or links.
    """
    if message.text and message.text.startswith("/"):
        return

    if "t.me/" not in (message.text or ""):
        return

    # If control reaches here, link handler already processed
    return


# =========================
# FINAL NOTES (DO NOT REMOVE)
# =========================
# This file is Pyrogram v2 compatible
# Folder name: plugins
# strings.py must be inside plugins/
# No telebot / no flask / no gunicorn here
# Run bot as BACKGROUND WORKER on Render
#
# Start command:
#   python3 bot.py
#
# If bot does not reply:
# - check BOT_TOKEN
# - check API_ID / API_HASH
# - check database connection
#
# Rexbots
# Telegram Channel: @RexBots_Official
# =========================