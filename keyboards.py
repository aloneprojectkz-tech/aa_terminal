from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ─── Main menu ────────────────────────────────────────────────────────────────

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📧 Создать почту"), KeyboardButton(text="📬 Мои почты")],
            [KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📧 Создать почту"), KeyboardButton(text="📬 Мои почты")],
            [KeyboardButton(text="👑 Админ панель"), KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )


# ─── Admin panel ──────────────────────────────────────────────────────────────

def admin_panel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика",         callback_data="admin:stats")
    builder.button(text="👥 Пользователи",        callback_data="admin:users")
    builder.button(text="📩 Все активные почты",  callback_data="admin:mailboxes")
    builder.button(text="📢 Рассылка",            callback_data="admin:broadcast")
    builder.adjust(2)
    return builder.as_markup()


def admin_users_kb(users: list, page: int = 0, page_size: int = 8) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = page * page_size
    chunk = users[start : start + page_size]
    for u in chunk:
        label = f"{'🚫 ' if u['is_banned'] else ''}@{u['username'] or u['tg_id']}"
        builder.button(text=label, callback_data=f"admin:user:{u['tg_id']}")
    builder.adjust(2)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"admin:users_page:{page-1}"))
    if start + page_size < len(users):
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"admin:users_page:{page+1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin:back"))
    return builder.as_markup()


def admin_user_actions_kb(tg_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    ban_text = "✅ Разбанить" if is_banned else "🚫 Забанить"
    builder.button(text=ban_text, callback_data=f"admin:toggle_ban:{tg_id}")
    builder.button(text="🔙 Назад",  callback_data="admin:users")
    builder.adjust(1)
    return builder.as_markup()


# ─── Mailboxes list ───────────────────────────────────────────────────────────

def mailboxes_kb(mailboxes: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for mb in mailboxes:
        builder.button(text=f"📧 {mb['address']}", callback_data=f"mb:info:{mb['id']}")
    builder.adjust(1)
    return builder.as_markup()


def mailbox_actions_kb(mailbox_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Удалить почту", callback_data=f"mb:delete:{mailbox_id}")
    builder.button(text="🔙 Назад",         callback_data="mb:list")
    builder.adjust(1)
    return builder.as_markup()


def confirm_delete_kb(mailbox_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=f"mb:confirm_delete:{mailbox_id}")
    builder.button(text="❌ Отмена",       callback_data=f"mb:info:{mailbox_id}")
    builder.adjust(2)
    return builder.as_markup()
