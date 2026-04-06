import asyncpg
import logging
from config import DATABASE_URL

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL)
    return _pool


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          BIGSERIAL PRIMARY KEY,
                tg_id       BIGINT UNIQUE NOT NULL,
                username    TEXT,
                first_name  TEXT,
                is_banned   BOOLEAN DEFAULT FALSE,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS mailboxes (
                id          BIGSERIAL PRIMARY KEY,
                tg_id       BIGINT NOT NULL REFERENCES users(tg_id) ON DELETE CASCADE,
                address     TEXT UNIQUE NOT NULL,
                password    TEXT NOT NULL,
                token       TEXT NOT NULL,
                account_id  TEXT NOT NULL,
                is_active   BOOLEAN DEFAULT TRUE,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS messages (
                id          BIGSERIAL PRIMARY KEY,
                mailbox_id  BIGINT NOT NULL REFERENCES mailboxes(id) ON DELETE CASCADE,
                message_id  TEXT UNIQUE NOT NULL,
                from_addr   TEXT,
                subject     TEXT,
                intro       TEXT,
                received_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
    logger.info("Database initialised")


# ─── Users ────────────────────────────────────────────────────────────────────

async def upsert_user(tg_id: int, username: str | None, first_name: str | None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (tg_id, username, first_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (tg_id) DO UPDATE
                SET username   = EXCLUDED.username,
                    first_name = EXCLUDED.first_name
        """, tg_id, username, first_name)


async def get_all_users() -> list[asyncpg.Record]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM users ORDER BY created_at DESC")


async def get_user(tg_id: int) -> asyncpg.Record | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE tg_id = $1", tg_id)


async def ban_user(tg_id: int, banned: bool):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET is_banned = $1 WHERE tg_id = $2", banned, tg_id)


async def is_banned(tg_id: int) -> bool:
    user = await get_user(tg_id)
    return bool(user and user["is_banned"])


# ─── Mailboxes ─────────────────────────────────────────────────────────────────

async def create_mailbox(tg_id: int, address: str, password: str, token: str, account_id: str) -> asyncpg.Record:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("""
            INSERT INTO mailboxes (tg_id, address, password, token, account_id)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """, tg_id, address, password, token, account_id)


async def get_user_mailboxes(tg_id: int) -> list[asyncpg.Record]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM mailboxes WHERE tg_id = $1 AND is_active = TRUE ORDER BY created_at DESC",
            tg_id
        )


async def get_all_active_mailboxes() -> list[asyncpg.Record]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM mailboxes WHERE is_active = TRUE")


async def deactivate_mailbox(mailbox_id: int, tg_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE mailboxes SET is_active = FALSE WHERE id = $1 AND tg_id = $2",
            mailbox_id, tg_id
        )


async def get_mailbox_by_id(mailbox_id: int) -> asyncpg.Record | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM mailboxes WHERE id = $1", mailbox_id)


# ─── Messages ─────────────────────────────────────────────────────────────────

async def message_exists(message_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM messages WHERE message_id = $1", message_id)
        return row is not None


async def save_message(mailbox_id: int, message_id: str, from_addr: str, subject: str, intro: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO messages (mailbox_id, message_id, from_addr, subject, intro)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT DO NOTHING
        """, mailbox_id, message_id, from_addr, subject, intro)


# ─── Stats ────────────────────────────────────────────────────────────────────

async def get_stats() -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        total_users    = await conn.fetchval("SELECT COUNT(*) FROM users")
        banned_users   = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_banned = TRUE")
        total_mailbox  = await conn.fetchval("SELECT COUNT(*) FROM mailboxes")
        active_mailbox = await conn.fetchval("SELECT COUNT(*) FROM mailboxes WHERE is_active = TRUE")
        total_messages = await conn.fetchval("SELECT COUNT(*) FROM messages")
    return {
        "total_users":    total_users,
        "banned_users":   banned_users,
        "total_mailbox":  total_mailbox,
        "active_mailbox": active_mailbox,
        "total_messages": total_messages,
    }
