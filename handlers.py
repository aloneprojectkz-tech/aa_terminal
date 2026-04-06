import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
import mailtm
from config import ADMIN_IDS
from keyboards import (
    main_menu, admin_menu,
    admin_panel_kb, admin_users_kb, admin_user_actions_kb,
    mailboxes_kb, mailbox_actions_kb, confirm_delete_kb,
)

logger = logging.getLogger(__name__)
router = Router()


# ══════════════════════════════════════════════════════════════════════════════
# FSM
# ══════════════════════════════════════════════════════════════════════════════

class BroadcastState(StatesGroup):
    waiting_text = State()


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def is_admin(tg_id: int) -> bool:
    return tg_id in ADMIN_IDS


async def check_banned(message: Message) -> bool:
    if await db.is_banned(message.from_user.id):
        await message.answer("🚫 Ваш аккаунт заблокирован.")
        return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# Start / Help
# ══════════════════════════════════════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(message: Message):
    await db.upsert_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    if await check_banned(message):
        return
    kb = admin_menu() if is_admin(message.from_user.id) else main_menu()
    await message.answer(
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        "Я помогу создать временную электронную почту и буду пересылать "
        "все входящие письма прямо в этот чат.\n\n"
        "Нажми <b>📧 Создать почту</b> чтобы начать.",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message):
    if await check_banned(message):
        return
    await message.answer(
        "📖 <b>Как пользоваться:</b>\n\n"
        "1️⃣ Нажми <b>📧 Создать почту</b> — бот создаст временный адрес.\n"
        "2️⃣ Используй этот адрес для регистрации на сайтах.\n"
        "3️⃣ Все входящие письма придут сюда автоматически.\n"
        "4️⃣ В <b>📬 Мои почты</b> можно увидеть список ящиков и удалить ненужные.\n\n"
        "⏱ Письма проверяются каждые ~30 секунд.",
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Create mailbox
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "📧 Создать почту")
async def create_mail(message: Message):
    if await check_banned(message):
        return

    # Limit per user (optional, set to None to disable)
    MAX_MAILBOXES = 5
    existing = await db.get_user_mailboxes(message.from_user.id)
    if len(existing) >= MAX_MAILBOXES:
        await message.answer(
            f"⚠️ У вас уже {MAX_MAILBOXES} активных почтовых ящиков.\n"
            "Удалите один из существующих, прежде чем создавать новый."
        )
        return

    msg = await message.answer("⏳ Создаю почту, подождите...")

    result = await mailtm.create_account()
    if not result:
        await msg.edit_text("❌ Не удалось создать почту. Попробуйте позже.")
        return

    await db.upsert_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    await db.create_mailbox(
        tg_id      = message.from_user.id,
        address    = result["address"],
        password   = result["password"],
        token      = result["token"],
        account_id = result["account_id"],
    )

    await msg.edit_text(
        f"✅ Почта создана!\n\n"
        f"📧 <code>{result['address']}</code>\n"
        f"🔑 Пароль: <code>{result['password']}</code>\n\n"
        "Все входящие письма будут автоматически пересылаться сюда.",
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════════════════════════
# My mailboxes
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "📬 Мои почты")
async def my_mailboxes(message: Message):
    if await check_banned(message):
        return
    mailboxes = await db.get_user_mailboxes(message.from_user.id)
    if not mailboxes:
        await message.answer("📭 У вас пока нет активных почтовых ящиков.")
        return
    await message.answer(
        f"📬 Ваши активные ящики ({len(mailboxes)}):",
        reply_markup=mailboxes_kb(mailboxes),
    )


@router.callback_query(F.data == "mb:list")
async def cb_mb_list(call: CallbackQuery):
    mailboxes = await db.get_user_mailboxes(call.from_user.id)
    if not mailboxes:
        await call.message.edit_text("📭 У вас пока нет активных почтовых ящиков.")
        return
    await call.message.edit_text(
        f"📬 Ваши активные ящики ({len(mailboxes)}):",
        reply_markup=mailboxes_kb(mailboxes),
    )
    await call.answer()


@router.callback_query(F.data.startswith("mb:info:"))
async def cb_mb_info(call: CallbackQuery):
    mailbox_id = int(call.data.split(":")[2])
    mb = await db.get_mailbox_by_id(mailbox_id)
    if not mb or mb["tg_id"] != call.from_user.id:
        await call.answer("❌ Ящик не найден.", show_alert=True)
        return
    await call.message.edit_text(
        f"📧 <b>{mb['address']}</b>\n\n"
        f"🔑 Пароль: <code>{mb['password']}</code>\n"
        f"📅 Создан: {mb['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
        "Что хотите сделать?",
        parse_mode="HTML",
        reply_markup=mailbox_actions_kb(mailbox_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("mb:delete:"))
async def cb_mb_delete(call: CallbackQuery):
    mailbox_id = int(call.data.split(":")[2])
    mb = await db.get_mailbox_by_id(mailbox_id)
    if not mb or mb["tg_id"] != call.from_user.id:
        await call.answer("❌ Ящик не найден.", show_alert=True)
        return
    await call.message.edit_text(
        f"❓ Удалить <b>{mb['address']}</b>?\n\n"
        "Все входящие письма перестанут пересылаться.",
        parse_mode="HTML",
        reply_markup=confirm_delete_kb(mailbox_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("mb:confirm_delete:"))
async def cb_mb_confirm_delete(call: CallbackQuery):
    mailbox_id = int(call.data.split(":")[2])
    mb = await db.get_mailbox_by_id(mailbox_id)
    if not mb or mb["tg_id"] != call.from_user.id:
        await call.answer("❌ Ящик не найден.", show_alert=True)
        return

    # Try to delete on mail.tm as well
    await mailtm.delete_account(mb["token"], mb["account_id"])
    await db.deactivate_mailbox(mailbox_id, call.from_user.id)

    await call.message.edit_text(f"🗑 Почта <b>{mb['address']}</b> удалена.", parse_mode="HTML")
    await call.answer()


# ══════════════════════════════════════════════════════════════════════════════
# Admin panel
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "👑 Админ панель")
@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("👑 <b>Админ-панель</b>", parse_mode="HTML", reply_markup=admin_panel_kb())


# ── Stats ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:stats")
async def cb_admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа.", show_alert=True)
    stats = await db.get_stats()
    text = (
        "📊 <b>Статистика</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"🚫 Забанено: <b>{stats['banned_users']}</b>\n"
        f"📧 Всего ящиков: <b>{stats['total_mailbox']}</b>\n"
        f"✅ Активных ящиков: <b>{stats['active_mailbox']}</b>\n"
        f"📩 Доставлено писем: <b>{stats['total_messages']}</b>"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=admin_panel_kb())
    await call.answer()


# ── Users list ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:users")
async def cb_admin_users(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа.", show_alert=True)
    users = await db.get_all_users()
    if not users:
        await call.message.edit_text("Пользователей нет.", reply_markup=admin_panel_kb())
    else:
        await call.message.edit_text(
            f"👥 Пользователи ({len(users)}):",
            reply_markup=admin_users_kb(users, page=0),
        )
    await call.answer()


@router.callback_query(F.data.startswith("admin:users_page:"))
async def cb_admin_users_page(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа.", show_alert=True)
    page = int(call.data.split(":")[2])
    users = await db.get_all_users()
    await call.message.edit_text(
        f"👥 Пользователи ({len(users)}):",
        reply_markup=admin_users_kb(users, page=page),
    )
    await call.answer()


@router.callback_query(F.data.startswith("admin:user:"))
async def cb_admin_user_detail(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа.", show_alert=True)
    tg_id = int(call.data.split(":")[2])
    user = await db.get_user(tg_id)
    if not user:
        return await call.answer("Пользователь не найден.", show_alert=True)
    mailboxes = await db.get_user_mailboxes(tg_id)
    text = (
        f"👤 <b>{user['first_name'] or 'N/A'}</b> (@{user['username'] or 'нет'})\n"
        f"🆔 ID: <code>{user['tg_id']}</code>\n"
        f"📅 Регистрация: {user['created_at'].strftime('%d.%m.%Y')}\n"
        f"🚫 Бан: {'да' if user['is_banned'] else 'нет'}\n"
        f"📧 Активных ящиков: {len(mailboxes)}"
    )
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_user_actions_kb(tg_id, user["is_banned"]),
    )
    await call.answer()


@router.callback_query(F.data.startswith("admin:toggle_ban:"))
async def cb_toggle_ban(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа.", show_alert=True)
    tg_id = int(call.data.split(":")[2])
    user = await db.get_user(tg_id)
    if not user:
        return await call.answer("Пользователь не найден.", show_alert=True)
    new_ban = not user["is_banned"]
    await db.ban_user(tg_id, new_ban)
    status = "заблокирован 🚫" if new_ban else "разблокирован ✅"
    await call.answer(f"Пользователь {status}", show_alert=True)
    # Refresh the user card
    user = await db.get_user(tg_id)
    mailboxes = await db.get_user_mailboxes(tg_id)
    text = (
        f"👤 <b>{user['first_name'] or 'N/A'}</b> (@{user['username'] or 'нет'})\n"
        f"🆔 ID: <code>{user['tg_id']}</code>\n"
        f"📅 Регистрация: {user['created_at'].strftime('%d.%m.%Y')}\n"
        f"🚫 Бан: {'да' if user['is_banned'] else 'нет'}\n"
        f"📧 Активных ящиков: {len(mailboxes)}"
    )
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_user_actions_kb(tg_id, user["is_banned"]),
    )


# ── Active mailboxes list ──────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:mailboxes")
async def cb_admin_mailboxes(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа.", show_alert=True)
    mbs = await db.get_all_active_mailboxes()
    if not mbs:
        await call.message.edit_text("Активных ящиков нет.", reply_markup=admin_panel_kb())
    else:
        lines = [f"• <code>{mb['address']}</code> (tg_id: {mb['tg_id']})" for mb in mbs[:50]]
        text = f"📩 Активные ящики ({len(mbs)}):\n\n" + "\n".join(lines)
        if len(mbs) > 50:
            text += f"\n… и ещё {len(mbs) - 50}"
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=admin_panel_kb())
    await call.answer()


# ── Back ───────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:back")
async def cb_admin_back(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.message.edit_text("👑 <b>Админ-панель</b>", parse_mode="HTML", reply_markup=admin_panel_kb())
    await call.answer()


# ── Broadcast ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:broadcast")
async def cb_admin_broadcast(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа.", show_alert=True)
    await call.message.answer("✏️ Введите текст рассылки (поддерживается HTML):")
    await state.set_state(BroadcastState.waiting_text)
    await call.answer()


@router.message(BroadcastState.waiting_text)
async def do_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    await state.clear()
    users = await db.get_all_users()
    sent = 0
    failed = 0
    for user in users:
        try:
            await message.bot.send_message(
                user["tg_id"],
                f"📢 <b>Сообщение от администратора:</b>\n\n{message.text or message.caption}",
                parse_mode="HTML",
            )
            sent += 1
        except Exception:
            failed += 1
    await message.answer(f"✅ Отправлено: {sent}\n❌ Не доставлено: {failed}")
