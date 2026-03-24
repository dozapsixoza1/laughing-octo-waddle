"""
╔══════════════════════════════════════════════════════════════╗
║           🔥 CHAT MANAGER BOT — BY KENT & CREW 🔥           ║
║         Telegram Chat Manager with Anti-Spam System          ║
╚══════════════════════════════════════════════════════════════╝

УСТАНОВКА:
    pip install python-telegram-bot==20.7

ЗАПУСК:
    python chat_manager_bot.py
"""

import logging
import asyncio
import time
import re
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatPermissions
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from telegram.constants import ParseMode

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                        🔧 КОНФИГ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BOT_TOKEN = "8602508429:AAEsjeV-66FKYvCuQpuJ7qxyUTINI2YJcC0"       # Получи у @BotFather

OWNER_IDS = [
    7950038145,      # Овнер 1 — замени на свой Telegram ID
    7780853114,      # Овнер 2 — замени на ID кента
]

# ID основного чата (для авто-разбана через анти-спам заявки)
MAIN_CHAT_ID: Optional[int] = -1003751235862   # Например: -1001234567890

# Настройки антиспама
SPAM_MSG_LIMIT    = 5    # сообщений за окно = спам
SPAM_TIME_WINDOW  = 10   # секунд
SPAM_MUTE_MINUTES = 30   # мьют при спаме
SPAM_BAN_AFTER    = 3    # варнов до автобана

BAD_WORDS = ["плохоеслово1", "плохоеслово2"]  # Добавь свои

ALLOWED_DOMAINS = ["t.me", "youtube.com", "youtu.be", "github.com"]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                      📊 ДАННЫЕ В ПАМЯТИ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

spam_tracker: dict = defaultdict(list)
warnings:     dict = defaultdict(int)
mutes:        dict = {}
antispam_requests: dict = {}

stats = {
    "messages_total": 0, "spam_blocked": 0,
    "bans_total": 0,     "mutes_total": 0,
    "warns_total": 0,    "antispam_granted": 0,
}

chat_settings: dict = defaultdict(lambda: {
    "antiflood": True, "antilinks": True,
    "badwords":  True, "welcome":   True,
    "antispam":  True,
})

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                        🛠 УТИЛИТЫ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def is_owner(user_id: int) -> bool:
    return user_id in OWNER_IDS

def mention(user) -> str:
    name = user.full_name if hasattr(user, "full_name") and user.full_name else str(user.id)
    return f'<a href="tg://user?id={user.id}">{name}</a>'

async def is_admin(chat_id, user_id, bot) -> bool:
    if is_owner(user_id):
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

def get_settings_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    s = chat_settings[chat_id]
    def tog(key): return "✅" if s[key] else "❌"
    kb = [
        [InlineKeyboardButton(f"{tog('antiflood')} Антифлуд",   callback_data=f"set_antiflood_{chat_id}"),
         InlineKeyboardButton(f"{tog('antilinks')} Антиссылки", callback_data=f"set_antilinks_{chat_id}")],
        [InlineKeyboardButton(f"{tog('badwords')} Фильтр слов", callback_data=f"set_badwords_{chat_id}"),
         InlineKeyboardButton(f"{tog('welcome')} Приветствие",  callback_data=f"set_welcome_{chat_id}")],
        [InlineKeyboardButton(f"{tog('antispam')} Антиспам",    callback_data=f"set_antispam_{chat_id}"),
         InlineKeyboardButton("🔄 Обновить",                    callback_data=f"refresh_settings_{chat_id}")],
        [InlineKeyboardButton("❌ Закрыть",                     callback_data="close")],
    ]
    return InlineKeyboardMarkup(kb)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#               🤖 КОМАНДЫ — СТАРТ И ПОМОЩЬ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Команды",    callback_data="show_help"),
         InlineKeyboardButton("⚙️ Настройки", callback_data="show_settings_info")],
        [InlineKeyboardButton("📊 Статистика", callback_data="show_stats"),
         InlineKeyboardButton("🚨 Анти-Спам",  callback_data="help_antispam")],
        [InlineKeyboardButton("👑 Овнеры",     callback_data="show_owners")],
    ])
    text = (
        f"👋 Привет, {mention(user)}!\n\n"
        "🔥 <b>CHAT MANAGER BOT</b>\n\n"
        "🛡 Умею:\n"
        "• Банить / мьютить / варнить нарушителей\n"
        "• Фильтровать спам, флуд и плохие слова\n"
        "• Блокировать запрещённые ссылки\n"
        "• Принимать заявки от забаненных юзеров\n"
        "• Управлять настройками чата\n\n"
        "📌 Добавь меня в чат с правами <b>администратора</b>!\n\n"
        "⬇️ Выбери раздел:"
    )
    await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👮 Модерация",  callback_data="help_mod"),
         InlineKeyboardButton("⚙️ Управление", callback_data="help_admin")],
        [InlineKeyboardButton("📊 Инфо",        callback_data="help_info"),
         InlineKeyboardButton("🚨 Анти-Спам",  callback_data="help_antispam")],
        [InlineKeyboardButton("❌ Закрыть",     callback_data="close")],
    ])
    await update.message.reply_text(
        "📖 <b>СПИСОК КОМАНД</b>\n\nВыбери категорию 👇",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                    ⚔️ МОДЕРАЦИЯ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat, user, msg = update.effective_chat, update.effective_user, update.message
    if not await is_admin(chat.id, user.id, ctx.bot):
        await msg.reply_text("🚫 Только администраторы!", parse_mode=ParseMode.HTML)
        return

    target, reason = None, "Не указана"
    if msg.reply_to_message:
        target = msg.reply_to_message.from_user
        reason = " ".join(ctx.args) if ctx.args else reason
    elif ctx.args:
        try:
            target = await ctx.bot.get_chat(int(ctx.args[0]))
            reason = " ".join(ctx.args[1:]) if len(ctx.args) > 1 else reason
        except Exception:
            await msg.reply_text("❌ Укажи ID или ответь на сообщение!", parse_mode=ParseMode.HTML)
            return

    if not target:
        await msg.reply_text("❌ Укажи пользователя!", parse_mode=ParseMode.HTML)
        return
    if is_owner(target.id):
        await msg.reply_text("👑 Нельзя забанить овнера!", parse_mode=ParseMode.HTML)
        return

    try:
        await ctx.bot.ban_chat_member(chat.id, target.id)
        stats["bans_total"] += 1
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔓 Разбанить", callback_data=f"unban_{target.id}_{chat.id}")]])
        await msg.reply_text(
            f"🔨 <b>БАН</b>\n\n"
            f"👤 {mention(target)}\n"
            f"👮 Модератор: {mention(user)}\n"
            f"📝 Причина: <i>{reason}</i>\n"
            f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await msg.reply_text(f"❌ Ошибка: {e}", parse_mode=ParseMode.HTML)


async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat, user, msg = update.effective_chat, update.effective_user, update.message
    if not await is_admin(chat.id, user.id, ctx.bot):
        await msg.reply_text("🚫 Только администраторы!", parse_mode=ParseMode.HTML)
        return
    if not ctx.args:
        await msg.reply_text("❌ /unban <id>", parse_mode=ParseMode.HTML)
        return
    try:
        uid = int(ctx.args[0])
        await ctx.bot.unban_chat_member(chat.id, uid)
        await msg.reply_text(f"✅ <b>Разбан</b>\n🆔 <code>{uid}</code>\n👮 {mention(user)}", parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.reply_text(f"❌ Ошибка: {e}", parse_mode=ParseMode.HTML)


async def cmd_mute(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat, user, msg = update.effective_chat, update.effective_user, update.message
    if not await is_admin(chat.id, user.id, ctx.bot):
        await msg.reply_text("🚫 Только администраторы!", parse_mode=ParseMode.HTML)
        return

    target, duration, reason = None, SPAM_MUTE_MINUTES, "Не указана"
    if msg.reply_to_message:
        target = msg.reply_to_message.from_user
        if ctx.args:
            try:
                duration = int(ctx.args[0])
                reason = " ".join(ctx.args[1:]) if len(ctx.args) > 1 else reason
            except ValueError:
                reason = " ".join(ctx.args)
    elif ctx.args:
        try:
            target = await ctx.bot.get_chat(int(ctx.args[0]))
            duration = int(ctx.args[1]) if len(ctx.args) > 1 else duration
            reason = " ".join(ctx.args[2:]) if len(ctx.args) > 2 else reason
        except Exception:
            await msg.reply_text("❌ /mute <id/reply> [мин] [причина]", parse_mode=ParseMode.HTML)
            return

    if not target:
        await msg.reply_text("❌ Укажи пользователя!", parse_mode=ParseMode.HTML)
        return
    if is_owner(target.id):
        await msg.reply_text("👑 Нельзя замьютить овнера!", parse_mode=ParseMode.HTML)
        return

    until = datetime.now() + timedelta(minutes=duration)
    mutes[(chat.id, target.id)] = until
    try:
        await ctx.bot.restrict_chat_member(chat.id, target.id, ChatPermissions(can_send_messages=False), until_date=until)
        stats["mutes_total"] += 1
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔊 Размьютить", callback_data=f"unmute_{target.id}_{chat.id}")]])
        await msg.reply_text(
            f"🔇 <b>МЬЮТf</b>\n\n"
            f"👤 {mention(target)}\n"
            f"⏱ На <b>{duration} мин.</b>\n"
            f"👮 {mention(user)}\n"
            f"📝 <i>{reason}</i>",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await msg.reply_text(f"❌ Ошибка: {e}", parse_mode=ParseMode.HTML)


async def cmd_unmute(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat, user, msg = update.effective_chat, update.effective_user, update.message
    if not await is_admin(chat.id, user.id, ctx.bot):
        await msg.reply_text("🚫 Только администраторы!", parse_mode=ParseMode.HTML)
        return
    target = msg.reply_to_message.from_user if msg.reply_to_message else None
    if not target and ctx.args:
        try:
            target = await ctx.bot.get_chat(int(ctx.args[0]))
        except Exception:
            pass
    if not target:
        await msg.reply_text("❌ Укажи пользователя!", parse_mode=ParseMode.HTML)
        return
    try:
        await ctx.bot.restrict_chat_member(
            chat.id, target.id,
            ChatPermissions(can_send_messages=True, can_send_media_messages=True,
                            can_send_other_messages=True, can_add_web_page_previews=True)
        )
        mutes.pop((chat.id, target.id), None)
        await msg.reply_text(f"🔊 <b>Размьют</b>\n👤 {mention(target)}\n👮 {mention(user)}", parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.reply_text(f"❌ Ошибка: {e}", parse_mode=ParseMode.HTML)


async def cmd_warn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat, user, msg = update.effective_chat, update.effective_user, update.message
    if not await is_admin(chat.id, user.id, ctx.bot):
        await msg.reply_text("🚫 Только администраторы!", parse_mode=ParseMode.HTML)
        return

    target, reason = None, "Не указана"
    if msg.reply_to_message:
        target = msg.reply_to_message.from_user
        reason = " ".join(ctx.args) if ctx.args else reason
    elif ctx.args:
        try:
            target = await ctx.bot.get_chat(int(ctx.args[0]))
            reason = " ".join(ctx.args[1:]) if len(ctx.args) > 1 else reason
        except Exception:
            await msg.reply_text("❌ Укажи пользователя!", parse_mode=ParseMode.HTML)
            return

    if not target:
        await msg.reply_text("❌ Укажи пользователя!", parse_mode=ParseMode.HTML)
        return
    if is_owner(target.id):
        await msg.reply_text("👑 Нельзя варнить овнера!", parse_mode=ParseMode.HTML)
        return

    key = (chat.id, target.id)
    warnings[key] += 1
    count = warnings[key]
    stats["warns_total"] += 1

    if count >= SPAM_BAN_AFTER:
        await ctx.bot.ban_chat_member(chat.id, target.id)
        warnings[key] = 0
        stats["bans_total"] += 1
        await msg.reply_text(
            f"🔨 {mention(target)} <b>автобан</b> — набрал {count} варнов!\n"
            f"📝 Причина: <i>{reason}</i>\n"
            f"💬 Забаненный может написать боту /antispam",
            parse_mode=ParseMode.HTML
        )
        return

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑 Снять варн", callback_data=f"unwarn_{target.id}_{chat.id}")]])
    await msg.reply_text(
        f"⚠️ <b>ПРЕДУПРЕЖДЕНИЕ</b>\n\n"
        f"👤 {mention(target)}\n"
        f"📊 Варнов: <b>{count}/{SPAM_BAN_AFTER}</b>\n"
        f"📝 <i>{reason}</i>\n"
        f"⚡ До бана: <b>{SPAM_BAN_AFTER - count}</b>",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )


async def cmd_unwarn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat, user, msg = update.effective_chat, update.effective_user, update.message
    if not await is_admin(chat.id, user.id, ctx.bot):
        await msg.reply_text("🚫 Только администраторы!", parse_mode=ParseMode.HTML)
        return
    target = msg.reply_to_message.from_user if msg.reply_to_message else None
    if not target and ctx.args:
        try:
            target = await ctx.bot.get_chat(int(ctx.args[0]))
        except Exception:
            pass
    if not target:
        await msg.reply_text("❌ Укажи пользователя!", parse_mode=ParseMode.HTML)
        return
    key = (chat.id, target.id)
    if warnings[key] > 0:
        warnings[key] -= 1
    await msg.reply_text(
        f"✅ Варн снят с {mention(target)}\n📊 Осталось: <b>{warnings[key]}</b>",
        parse_mode=ParseMode.HTML
    )


async def cmd_kick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat, user, msg = update.effective_chat, update.effective_user, update.message
    if not await is_admin(chat.id, user.id, ctx.bot):
        await msg.reply_text("🚫 Только администраторы!", parse_mode=ParseMode.HTML)
        return
    if not msg.reply_to_message:
        await msg.reply_text("❌ Ответь на сообщение!", parse_mode=ParseMode.HTML)
        return
    target = msg.reply_to_message.from_user
    if is_owner(target.id):
        await msg.reply_text("👑 Нельзя кикнуть овнера!", parse_mode=ParseMode.HTML)
        return
    reason = " ".join(ctx.args) if ctx.args else "Не указана"
    try:
        await ctx.bot.ban_chat_member(chat.id, target.id)
        await ctx.bot.unban_chat_member(chat.id, target.id)
        await msg.reply_text(
            f"👢 <b>КИК</b>\n👤 {mention(target)}\n👮 {mention(user)}\n📝 <i>{reason}</i>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await msg.reply_text(f"❌ Ошибка: {e}", parse_mode=ParseMode.HTML)


async def cmd_ro(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat, user, msg = update.effective_chat, update.effective_user, update.message
    if not await is_admin(chat.id, user.id, ctx.bot):
        await msg.reply_text("🚫 Только администраторы!", parse_mode=ParseMode.HTML)
        return
    if not msg.reply_to_message:
        await msg.reply_text("❌ Ответь на сообщение!", parse_mode=ParseMode.HTML)
        return
    target = msg.reply_to_message.from_user
    duration = int(ctx.args[0]) if ctx.args else 60
    until = datetime.now() + timedelta(minutes=duration)
    try:
        await ctx.bot.restrict_chat_member(
            chat.id, target.id,
            ChatPermissions(can_send_messages=False, can_send_media_messages=False),
            until_date=until
        )
        await msg.reply_text(
            f"👁 <b>Режим чтения</b>\n👤 {mention(target)}\n⏱ На <b>{duration} мин.</b>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await msg.reply_text(f"❌ Ошибка: {e}", parse_mode=ParseMode.HTML)


async def cmd_purge(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat, user, msg = update.effective_chat, update.effective_user, update.message
    if not await is_admin(chat.id, user.id, ctx.bot):
        await msg.reply_text("🚫 Только администраторы!", parse_mode=ParseMode.HTML)
        return
    if not msg.reply_to_message:
        await msg.reply_text("❌ Ответь на первое сообщение для очистки!", parse_mode=ParseMode.HTML)
        return
    start_id, end_id, deleted = msg.reply_to_message.message_id, msg.message_id, 0
    for mid in range(start_id, end_id + 1):
        try:
            await ctx.bot.delete_message(chat.id, mid)
            deleted += 1
        except Exception:
            pass
    notice = await ctx.bot.send_message(
        chat.id, f"🗑 Удалено <b>{deleted}</b> сообщений — {mention(user)}", parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(5)
    try:
        await notice.delete()
    except Exception:
        pass

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                   📊 ИНФОРМАЦИЯ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def cmd_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg  = update.message
    chat = update.effective_chat
    target = msg.reply_to_message.from_user if msg.reply_to_message else update.effective_user
    key    = (chat.id, target.id)
    warn_count = warnings.get(key, 0)
    mute_until = mutes.get(key)
    mute_str   = mute_until.strftime("%d.%m.%Y %H:%M") if mute_until and mute_until > datetime.now() else "Нет"

    try:
        member = await ctx.bot.get_chat_member(chat.id, target.id)
        status_map = {
            "creator": "👑 Создатель", "administrator": "⚙️ Администратор",
            "member": "👤 Участник",   "restricted": "🔒 Ограничен",
            "left": "🚪 Покинул",      "kicked": "🔨 Забанен",
        }
        status = status_map.get(member.status, member.status)
    except Exception:
        status = "❓ Неизвестно"

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⚠️ Варн", callback_data=f"quick_warn_{target.id}_{chat.id}"),
        InlineKeyboardButton("🔇 Мьют", callback_data=f"quick_mute_{target.id}_{chat.id}"),
        InlineKeyboardButton("🔨 Бан",  callback_data=f"quick_ban_{target.id}_{chat.id}"),
    ]])
    await msg.reply_text(
        f"👤 <b>ИНФОРМАЦИЯ</b>\n\n"
        f"🆔 ID: <code>{target.id}</code>\n"
        f"📛 Имя: {mention(target)}\n"
        f"🔖 @{target.username or '—'}\n"
        f"📊 Статус: {status}\n"
        f"⚠️ Варнов: <b>{warn_count}/{SPAM_BAN_AFTER}</b>\n"
        f"🔇 Мьют до: <b>{mute_str}</b>\n"
        f"👑 Овнер: {'Да ✅' if is_owner(target.id) else 'Нет ❌'}",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )


async def cmd_warns(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg  = update.message
    chat = update.effective_chat
    target = msg.reply_to_message.from_user if msg.reply_to_message else update.effective_user
    key    = (chat.id, target.id)
    await msg.reply_text(
        f"⚠️ Предупреждения {mention(target)}: <b>{warnings.get(key, 0)}/{SPAM_BAN_AFTER}</b>",
        parse_mode=ParseMode.HTML
    )


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 <b>СТАТИСТИКА</b>\n\n"
        f"💬 Сообщений: <b>{stats['messages_total']}</b>\n"
        f"🚫 Спама: <b>{stats['spam_blocked']}</b>\n"
        f"🔨 Банов: <b>{stats['bans_total']}</b>\n"
        f"🔇 Мьютов: <b>{stats['mutes_total']}</b>\n"
        f"⚠️ Варнов: <b>{stats['warns_total']}</b>\n"
        f"✅ Анти-спам выдано: <b>{stats['antispam_granted']}</b>\n\n"
        f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        parse_mode=ParseMode.HTML
    )


async def cmd_chatinfo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    try:
        count = await ctx.bot.get_chat_member_count(chat.id)
    except Exception:
        count = "?"
    await update.message.reply_text(
        f"💬 <b>ИНФОРМАЦИЯ О ЧАТЕ</b>\n\n"
        f"📛 {chat.title}\n"
        f"🆔 <code>{chat.id}</code>\n"
        f"👥 Участников: <b>{count}</b>\n"
        f"🔗 @{chat.username or '—'}\n"
        f"📋 Тип: <b>{chat.type}</b>",
        parse_mode=ParseMode.HTML
    )


async def cmd_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat, user = update.effective_chat, update.effective_user
    if chat.type == "private":
        await update.message.reply_text("⚙️ Только для групп!", parse_mode=ParseMode.HTML)
        return
    if not await is_admin(chat.id, user.id, ctx.bot):
        await update.message.reply_text("🚫 Только администраторы!", parse_mode=ParseMode.HTML)
        return
    await update.message.reply_text(
        f"⚙️ <b>НАСТРОЙКИ</b> — {chat.title}",
        reply_markup=get_settings_keyboard(chat.id),
        parse_mode=ParseMode.HTML
    )


async def cmd_rules(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📜 <b>ПРАВИЛА ЧАТА</b>\n\n"
        "1️⃣ Уважай собеседников\n"
        "2️⃣ Без флуда и спама\n"
        "3️⃣ Без оскорблений\n"
        "4️⃣ Без рекламы без разрешения\n"
        "5️⃣ Только по теме чата\n"
        "6️⃣ Без 18+ контента\n"
        "7️⃣ Слушай администраторов\n\n"
        "⚠️ Нарушения: варн → мьют → бан",
        parse_mode=ParseMode.HTML
    )


async def cmd_admins(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("❌ Только для групп!", parse_mode=ParseMode.HTML)
        return
    try:
        admins = await ctx.bot.get_chat_administrators(chat.id)
        lines = ["👮 <b>АДМИНИСТРАТОРЫ</b>\n"]
        for a in admins:
            u = a.user
            if u.is_bot:
                role = "🤖 Бот"
            elif a.status == "creator":
                role = "👑 Создатель"
            else:
                role = "⚙️ Админ"
            lines.append(f"{role} — {mention(u)}")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}", parse_mode=ParseMode.HTML)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                 🚨 АНТИ-СПАМ СИСТЕМА
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def cmd_antispam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Забаненный пишет боту в личку: /antispam <причина>"""
    user, msg = update.effective_user, update.message
    if update.effective_chat.type != "private":
        await msg.reply_text(
            "🚨 Команда работает только в <b>личных сообщениях</b> с ботом!\n"
            "Напиши мне в личку 👇",
            parse_mode=ParseMode.HTML
        )
        return

    reason = " ".join(ctx.args) if ctx.args else "Причина не указана"
    antispam_requests[user.id] = {
        "username":  user.username or "",
        "full_name": user.full_name or str(user.id),
        "reason":    reason,
        "timestamp": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Разбанить",       callback_data=f"as_approve_{user.id}"),
         InlineKeyboardButton("❌ Отказать",         callback_data=f"as_deny_{user.id}")],
        [InlineKeyboardButton("📋 Инфо о юзере",    callback_data=f"as_info_{user.id}")],
    ])
    notif = (
        f"🚨 <b>ЗАЯВКА АНТИ-СПАМ</b>\n\n"
        f"👤 {mention(user)}\n"
        f"🆔 <code>{user.id}</code>\n"
        f"📝 Причина: <i>{reason}</i>\n"
        f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    for oid in OWNER_IDS:
        try:
            await ctx.bot.send_message(oid, notif, reply_markup=kb, parse_mode=ParseMode.HTML)
        except Exception:
            pass

    await msg.reply_text(
        "📨 <b>Заявка отправлена!</b>\n\n"
        "Твоя просьба о разбане ушла администраторам.\n"
        "⏳ Ждём рассмотрения — обычно до 24 часов.\n\n"
        "Не отправляй заявку повторно!",
        parse_mode=ParseMode.HTML
    )


async def cmd_antispam_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("🚫 Только для овнеров!", parse_mode=ParseMode.HTML)
        return
    if not antispam_requests:
        await update.message.reply_text("📭 Активных заявок нет!", parse_mode=ParseMode.HTML)
        return
    lines = ["📋 <b>ЗАЯВКИ АНТИ-СПАМ</b>\n"]
    for uid, info in antispam_requests.items():
        lines.append(
            f"👤 {info['full_name']} (@{info['username'] or '—'})\n"
            f"🆔 <code>{uid}</code>\n"
            f"📝 {info['reason']}\n"
            f"🕐 {info['timestamp']}\n——————"
        )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑 Очистить всё", callback_data="as_clear_all")]])
    await update.message.reply_text("\n".join(lines), reply_markup=kb, parse_mode=ParseMode.HTML)


async def cmd_grant_antispam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("🚫 Только для овнеров!", parse_mode=ParseMode.HTML)
        return
    if len(ctx.args) < 2:
        await update.message.reply_text("❌ /grant_antispam <chat_id> <user_id>", parse_mode=ParseMode.HTML)
        return
    try:
        chat_id = int(ctx.args[0])
        user_id = int(ctx.args[1])
        await ctx.bot.unban_chat_member(chat_id, user_id)
        stats["antispam_granted"] += 1
        await update.message.reply_text(
            f"✅ <b>Анти-спам выдан</b>\n🆔 <code>{user_id}</code>\n💬 Чат: <code>{chat_id}</code>",
            parse_mode=ParseMode.HTML
        )
        try:
            await ctx.bot.send_message(
                user_id,
                "🎉 <b>Заявка одобрена!</b>\nТы можешь вернуться в чат. Больше не нарушай! 🙏",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}", parse_mode=ParseMode.HTML)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                   🎛 ПРОЧИЕ КОМАНДЫ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def cmd_pin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat, user, msg = update.effective_chat, update.effective_user, update.message
    if not await is_admin(chat.id, user.id, ctx.bot):
        await msg.reply_text("🚫 Только администраторы!", parse_mode=ParseMode.HTML)
        return
    if not msg.reply_to_message:
        await msg.reply_text("❌ Ответь на сообщение!", parse_mode=ParseMode.HTML)
        return
    try:
        await ctx.bot.pin_chat_message(chat.id, msg.reply_to_message.message_id)
        await msg.reply_text(f"📌 <b>Сообщение закреплено</b> — {mention(user)}", parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.reply_text(f"❌ Ошибка: {e}", parse_mode=ParseMode.HTML)


async def cmd_unpin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat, user, msg = update.effective_chat, update.effective_user, update.message
    if not await is_admin(chat.id, user.id, ctx.bot):
        await msg.reply_text("🚫 Только администраторы!", parse_mode=ParseMode.HTML)
        return
    try:
        await ctx.bot.unpin_all_chat_messages(chat.id)
        await msg.reply_text("📌 <b>Все закреплённые сняты</b>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.reply_text(f"❌ Ошибка: {e}", parse_mode=ParseMode.HTML)


async def cmd_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg  = update.message
    chat = update.effective_chat
    target = msg.reply_to_message.from_user if msg.reply_to_message else update.effective_user
    await msg.reply_text(
        f"🆔 <b>ID</b>\n\n"
        f"👤 Пользователь: <code>{target.id}</code>\n"
        f"💬 Чат: <code>{chat.id}</code>",
        parse_mode=ParseMode.HTML
    )


async def cmd_ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    start = time.time()
    sent = await update.message.reply_text("🏓 Пинг...")
    delta = int((time.time() - start) * 1000)
    await sent.edit_text(f"🏓 Понг! <b>{delta}ms</b>", parse_mode=ParseMode.HTML)


async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("🚫 Только для овнеров!", parse_mode=ParseMode.HTML)
        return
    if not ctx.args:
        await update.message.reply_text("❌ /broadcast <текст>", parse_mode=ParseMode.HTML)
        return
    await update.message.reply_text(
        f"📢 <b>BROADCAST</b>\n\n{' '.join(ctx.args)}", parse_mode=ParseMode.HTML
    )


async def cmd_setbio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat, user = update.effective_chat, update.effective_user
    if not await is_admin(chat.id, user.id, ctx.bot):
        await update.message.reply_text("🚫 Только администраторы!", parse_mode=ParseMode.HTML)
        return
    if not ctx.args:
        await update.message.reply_text("❌ /setbio <текст>", parse_mode=ParseMode.HTML)
        return
    try:
        await ctx.bot.set_chat_description(chat.id, " ".join(ctx.args))
        await update.message.reply_text("✅ <b>Описание обновлено!</b>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}", parse_mode=ParseMode.HTML)


async def cmd_invitelink(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat, user = update.effective_chat, update.effective_user
    if not await is_admin(chat.id, user.id, ctx.bot):
        await update.message.reply_text("🚫 Только администраторы!", parse_mode=ParseMode.HTML)
        return
    try:
        link = await ctx.bot.export_chat_invite_link(chat.id)
        await update.message.reply_text(f"🔗 <b>Ссылка:</b>\n{link}", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}", parse_mode=ParseMode.HTML)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#               🛡 АВТО-МОДЕРАЦИЯ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def auto_moderate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg  = update.message
    if not msg or not msg.text:
        return
    chat, user = update.effective_chat, update.effective_user
    if not user or chat.type == "private":
        return
    if await is_admin(chat.id, user.id, ctx.bot):
        return

    settings = chat_settings[chat.id]
    text = msg.text
    stats["messages_total"] += 1

    # Антифлуд
    if settings["antiflood"]:
        now   = time.time()
        times = spam_tracker[user.id]
        times = [t for t in times if now - t < SPAM_TIME_WINDOW]
        times.append(now)
        spam_tracker[user.id] = times
        if len(times) >= SPAM_MSG_LIMIT:
            try:
                await msg.delete()
            except Exception:
                pass
            stats["spam_blocked"] += 1
            spam_tracker[user.id] = []
            await _auto_warn(chat, user, ctx, "Флуд")
            return

    # Антиссылки
    if settings["antilinks"]:
        url_pat = re.compile(r"(https?://|www\.|t\.me/|@\w{5,})", re.IGNORECASE)
        if url_pat.search(text) and not any(d in text for d in ALLOWED_DOMAINS):
            try:
                await msg.delete()
            except Exception:
                pass
            stats["spam_blocked"] += 1
            await _auto_warn(chat, user, ctx, "Запрещённая ссылка")
            return

    # Фильтр слов
    if settings["badwords"]:
        lower = text.lower()
        for bw in BAD_WORDS:
            if bw.lower() in lower:
                try:
                    await msg.delete()
                except Exception:
                    pass
                stats["spam_blocked"] += 1
                await _auto_warn(chat, user, ctx, "Нецензурная лексика")
                return


async def _auto_warn(chat, user, ctx, reason: str):
    key = (chat.id, user.id)
    warnings[key] += 1
    count = warnings[key]
    stats["warns_total"] += 1

    if count >= SPAM_BAN_AFTER:
        try:
            await ctx.bot.ban_chat_member(chat.id, user.id)
        except Exception:
            pass
        stats["bans_total"] += 1
        warnings[key] = 0
        await ctx.bot.send_message(
            chat.id,
            f"🔨 {mention(user)} <b>автобан</b> — {reason}\n"
            f"📊 {count}/{SPAM_BAN_AFTER} варнов\n\n"
            f"💬 Считаешь ошибкой? Напиши боту в личку: /antispam",
            parse_mode=ParseMode.HTML
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔓 Разбанить", callback_data=f"unban_{user.id}_{chat.id}")]])
        for oid in OWNER_IDS:
            try:
                await ctx.bot.send_message(
                    oid,
                    f"🔨 <b>Автобан</b>\n👤 {mention(user)}\n💬 {chat.title}\n📝 {reason}",
                    reply_markup=kb, parse_mode=ParseMode.HTML
                )
            except Exception:
                pass
    else:
        warn_msg = await ctx.bot.send_message(
            chat.id,
            f"⚠️ {mention(user)} авто-варн ({count}/{SPAM_BAN_AFTER}) — {reason}\n⚡ До бана: {SPAM_BAN_AFTER - count}",
            parse_mode=ParseMode.HTML
        )
        await asyncio.sleep(8)
        try:
            await warn_msg.delete()
        except Exception:
            pass

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                   👋 ПРИВЕТСТВИЕ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def on_member_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat_settings[chat.id]["welcome"]:
        return
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        stats["joins_total"] = stats.get("joins_total", 0) + 1
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("📜 Правила",   callback_data="show_rules"),
            InlineKeyboardButton("ℹ️ О чате",   callback_data="show_chat_info"),
        ]])
        await update.message.reply_text(
            f"👋 Привет, {mention(member)}!\n\n"
            f"🎉 Добро пожаловать в <b>{chat.title}</b>!\n"
            f"📜 Прочти правила перед тем как писать.",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                   🎛 КНОПКИ (CALLBACKS)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data
    user  = query.from_user
    await query.answer()

    # ЗАКРЫТЬ
    if data == "close":
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    # ГЛАВНОЕ МЕНЮ
    if data == "show_main_menu":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Команды",    callback_data="show_help"),
             InlineKeyboardButton("⚙️ Настройки", callback_data="show_settings_info")],
            [InlineKeyboardButton("📊 Статистика", callback_data="show_stats"),
             InlineKeyboardButton("🚨 Анти-Спам",  callback_data="help_antispam")],
            [InlineKeyboardButton("👑 Овнеры",     callback_data="show_owners")],
        ])
        await query.message.edit_text(
            "🔥 <b>CHAT MANAGER BOT</b>\n\nВыбери раздел:",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
        return

    # ПОМОЩЬ — МОДЕРАЦИЯ
    if data in ("show_help", "help_mod"):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ Управление", callback_data="help_admin"),
             InlineKeyboardButton("📊 Инфо",       callback_data="help_info")],
            [InlineKeyboardButton("🚨 Анти-Спам",  callback_data="help_antispam"),
             InlineKeyboardButton("◀️ Назад",      callback_data="show_main_menu")],
        ])
        await query.message.edit_text(
            "⚔️ <b>МОДЕРАЦИЯ</b>\n\n"
            "/ban — Забанить (ответ/ID)\n"
            "/unban <id> — Разбанить\n"
            "/mute [мин] [причина] — Замьютить\n"
            "/unmute — Размьютить\n"
            "/warn [причина] — Предупреждение\n"
            "/unwarn — Снять варн\n"
            "/kick — Кикнуть (ответ)\n"
            "/ro [мин] — Только чтение\n"
            "/purge — Очистить сообщения",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
        return

    # ПОМОЩЬ — УПРАВЛЕНИЕ
    if data == "help_admin":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚔️ Модерация",  callback_data="help_mod"),
             InlineKeyboardButton("📊 Инфо",        callback_data="help_info")],
            [InlineKeyboardButton("◀️ Назад",       callback_data="show_main_menu")],
        ])
        await query.message.edit_text(
            "⚙️ <b>УПРАВЛЕНИЕ</b>\n\n"
            "/settings — Настройки чата\n"
            "/pin — Закрепить (ответ)\n"
            "/unpin — Открепить всё\n"
            "/invitelink — Ссылка приглашения\n"
            "/setbio <текст> — Описание чата\n"
            "/broadcast <текст> — Рассылка (овнеры)\n"
            "/grant_antispam — Разбанить вручную\n"
            "/antispam_list — Список заявок",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
        return

    # ПОМОЩЬ — ИНФО
    if data == "help_info":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚔️ Модерация",  callback_data="help_mod"),
             InlineKeyboardButton("⚙️ Управление", callback_data="help_admin")],
            [InlineKeyboardButton("◀️ Назад",       callback_data="show_main_menu")],
        ])
        await query.message.edit_text(
            "📊 <b>ИНФОРМАЦИЯ</b>\n\n"
            "/info — Инфо о пользователе (ответ)\n"
            "/warns — Предупреждения\n"
            "/stats — Статистика бота\n"
            "/chatinfo — Инфо о чате\n"
            "/admins — Список администраторов\n"
            "/rules — Правила чата\n"
            "/id — Получить ID\n"
            "/ping — Проверка бота",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
        return

    # ПОМОЩЬ — АНТИСПАМ
    if data == "help_antispam":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="show_main_menu")]])
        await query.message.edit_text(
            "🚨 <b>АНТИ-СПАМ СИСТЕМА</b>\n\n"
            "<b>Схема работы:</b>\n\n"
            "1️⃣ Бот банит юзера за спам\n"
            "2️⃣ Юзер пишет боту в <b>личку</b>\n"
            "3️⃣ Отправляет команду:\n"
            "   <code>/antispam Я не спамер, был случайный флуд</code>\n"
            "4️⃣ Овнеры получают уведомление с кнопками\n"
            "5️⃣ Нажимают ✅ Разбанить или ❌ Отказать\n\n"
            "📋 /antispam_list — Список заявок (овнеры)\n"
            "✅ /grant_antispam <chat_id> <user_id> — Ручной разбан",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
        return

    # СТАТИСТИКА
    if data == "show_stats":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="show_main_menu")]])
        await query.message.edit_text(
            "📊 <b>СТАТИСТИКА</b>\n\n"
            f"💬 Сообщений: <b>{stats['messages_total']}</b>\n"
            f"🚫 Спама: <b>{stats['spam_blocked']}</b>\n"
            f"🔨 Банов: <b>{stats['bans_total']}</b>\n"
            f"🔇 Мьютов: <b>{stats['mutes_total']}</b>\n"
            f"⚠️ Варнов: <b>{stats['warns_total']}</b>\n"
            f"✅ Анти-спам: <b>{stats['antispam_granted']}</b>",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
        return

    # ОВНЕРЫ
    if data == "show_owners":
        lines = ["👑 <b>ОВНЕРЫ БОТА</b>\n"]
        for oid in OWNER_IDS:
            try:
                o = await ctx.bot.get_chat(oid)
                lines.append(f"👑 {mention(o)} — <code>{oid}</code>")
            except Exception:
                lines.append(f"👑 ID: <code>{oid}</code>")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="show_main_menu")]])
        await query.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    # ПРАВИЛА
    if data == "show_rules":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Понял!", callback_data="close")]])
        await query.message.edit_text(
            "📜 <b>ПРАВИЛА ЧАТА</b>\n\n"
            "1️⃣ Уважай всех участников\n"
            "2️⃣ Без флуда и спама\n"
            "3️⃣ Без оскорблений\n"
            "4️⃣ Без рекламы\n"
            "5️⃣ Только по теме\n"
            "6️⃣ Без 18+ контента\n"
            "7️⃣ Слушай администраторов\n\n"
            "⚠️ Нарушения: варн → мьют → бан",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
        return

    # НАСТРОЙКИ
    if data.startswith("set_") or data.startswith("refresh_settings_"):
        msg_chat = query.message.chat
        if msg_chat and not await is_admin(msg_chat.id, user.id, ctx.bot) and not is_owner(user.id):
            await query.answer("🚫 Только администраторы!", show_alert=True)
            return

        if data.startswith("refresh_settings_"):
            chat_id = int(data.split("_")[-1])
        else:
            parts   = data.split("_")
            setting = parts[1]
            chat_id = int(parts[-1])
            if setting in chat_settings[chat_id]:
                chat_settings[chat_id][setting] = not chat_settings[chat_id][setting]

        try:
            await query.message.edit_text(
                "⚙️ <b>НАСТРОЙКИ ЧАТА</b>",
                reply_markup=get_settings_keyboard(chat_id),
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        return

    # РАЗБАН
    if data.startswith("unban_"):
        parts = data.split("_")
        target_id, chat_id = int(parts[1]), int(parts[2])
        if not is_owner(user.id):
            try:
                if not await is_admin(chat_id, user.id, ctx.bot):
                    await query.answer("🚫 Только администраторы!", show_alert=True)
                    return
            except Exception:
                if not is_owner(user.id):
                    await query.answer("🚫 Только администраторы!", show_alert=True)
                    return
        try:
            await ctx.bot.unban_chat_member(chat_id, target_id)
            await query.message.edit_text(
                query.message.text_html + f"\n\n✅ <b>Разбанен</b> — {mention(user)}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await query.answer(f"❌ {e}", show_alert=True)
        return

    # РАЗМЬЮТ
    if data.startswith("unmute_"):
        parts = data.split("_")
        target_id, chat_id = int(parts[1]), int(parts[2])
        try:
            await ctx.bot.restrict_chat_member(
                chat_id, target_id,
                ChatPermissions(can_send_messages=True, can_send_media_messages=True,
                                can_send_other_messages=True, can_add_web_page_previews=True)
            )
            mutes.pop((chat_id, target_id), None)
            await query.message.edit_text(
                query.message.text_html + f"\n\n✅ <b>Размьючен</b> — {mention(user)}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await query.answer(f"❌ {e}", show_alert=True)
        return

    # СНЯТЬ ВАРН
    if data.startswith("unwarn_"):
        parts = data.split("_")
        target_id, chat_id = int(parts[1]), int(parts[2])
        key = (chat_id, target_id)
        if warnings[key] > 0:
            warnings[key] -= 1
        await query.answer(f"✅ Варн снят! Осталось: {warnings[key]}", show_alert=True)
        return

    # АНТИ-СПАМ: ОДОБРИТЬ
    if data.startswith("as_approve_"):
        if not is_owner(user.id):
            await query.answer("🚫 Только для овнеров!", show_alert=True)
            return
        target_id = int(data.split("_")[2])
        antispam_requests.pop(target_id, None)
        stats["antispam_granted"] += 1
        if MAIN_CHAT_ID:
            try:
                await ctx.bot.unban_chat_member(MAIN_CHAT_ID, target_id)
            except Exception:
                pass
        try:
            await query.message.edit_text(
                query.message.text_html + f"\n\n✅ <b>ОДОБРЕНО</b> — {mention(user)}",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        try:
            await ctx.bot.send_message(
                target_id,
                "🎉 <b>Заявка одобрена!</b>\nТы можешь вернуться. Больше не нарушай! 🙏",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        return

    # АНТИ-СПАМ: ОТКАЗАТЬ
    if data.startswith("as_deny_"):
        if not is_owner(user.id):
            await query.answer("🚫 Только для овнеров!", show_alert=True)
            return
        target_id = int(data.split("_")[2])
        antispam_requests.pop(target_id, None)
        try:
            await query.message.edit_text(
                query.message.text_html + f"\n\n❌ <b>ОТКАЗАНО</b> — {mention(user)}",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        try:
            await ctx.bot.send_message(
                target_id,
                "❌ <b>Заявка отклонена.</b>\nАдминистраторы отказали в разбане.",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        return

    # АНТИ-СПАМ: ИНФОo
    if data.startswith("as_info_"):
        target_id = int(data.split("_")[2])
        req = antispam_requests.get(target_id, {})
        await query.answer(
            f"Имя: {req.get('full_name','—')}\n"
            f"@{req.get('username','—')}\n"
            f"ID: {target_id}\n"
            f"Причина: {req.get('reason','—')}\n"
            f"Время: {req.get('timestamp','—')}",
            show_alert=True
        )
        return

    # АНТИ-СПАМ: ОЧИСТИТЬ ВСЁ
    if data == "as_clear_all":
        if not is_owner(user.id):
            await query.answer("🚫 Только для овнеров!", show_alert=True)
            return
        antispam_requests.clear()
        await query.answer("✅ Список очищен!", show_alert=True)
        try:
            await query.message.edit_text("📭 Список заявок очищен.", parse_mode=ParseMode.HTML)
        except Exception:
            pass
        return

    # БЫСТРЫЕ ДЕЙСТВИЯ
    if data.startswith("quick_"):
        parts  = data.split("_")
        action = parts[1]
        tid    = int(parts[2])
        cid    = int(parts[3])
        if not is_owner(user.id) and not await is_admin(cid, user.id, ctx.bot):
            await query.answer("🚫 Только администраторы!", show_alert=True)
            return
        if action == "ban":
            await ctx.bot.ban_chat_member(cid, tid)
            stats["bans_total"] += 1
            await query.answer("🔨 Забанен!", show_alert=True)
        elif action == "mute":
            until = datetime.now() + timedelta(minutes=SPAM_MUTE_MINUTES)
            await ctx.bot.restrict_chat_member(cid, tid, ChatPermissions(can_send_messages=False), until_date=until)
            stats["mutes_total"] += 1
            await query.answer(f"🔇 Замьючен на {SPAM_MUTE_MINUTES} мин!", show_alert=True)
        elif action == "warn":
            key = (cid, tid)
            warnings[key] += 1
            stats["warns_total"] += 1
            await query.answer(f"⚠️ Варн! Всего: {warnings[key]}", show_alert=True)
        return

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                      🚀 ЗАПУСК
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    for cmd, func in [
        ("start",          cmd_start),
        ("help",           cmd_help),
        ("ban",            cmd_ban),
        ("unban",          cmd_unban),
        ("mute",           cmd_mute),
        ("unmute",         cmd_unmute),
        ("warn",           cmd_warn),
        ("unwarn",         cmd_unwarn),
        ("kick",           cmd_kick),
        ("ro",             cmd_ro),
        ("purge",          cmd_purge),
        ("info",           cmd_info),
        ("warns",          cmd_warns),
        ("stats",          cmd_stats),
        ("chatinfo",       cmd_chatinfo),
        ("settings",       cmd_settings),
        ("rules",          cmd_rules),
        ("admins",         cmd_admins),
        ("pin",            cmd_pin),
        ("unpin",          cmd_unpin),
        ("id",             cmd_id),
        ("ping",           cmd_ping),
        ("broadcast",      cmd_broadcast),
        ("setbio",         cmd_setbio),
        ("invitelink",     cmd_invitelink),
        ("antispam",       cmd_antispam),
        ("antispam_list",  cmd_antispam_list),
        ("grant_antispam", cmd_grant_antispam),
    ]:
        app.add_handler(CommandHandler(cmd, func))

    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
        auto_moderate
    ))
    app.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        on_member_join
    ))

    logger.info("🔥 Chat Manager Bot запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
