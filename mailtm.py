import aiohttp
import string
import random
import logging
from config import MAIL_TM_BASE

logger = logging.getLogger(__name__)


def _random_string(length: int = 10) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


async def get_domains() -> list[str]:
    """Return list of available mail.tm domains."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{MAIL_TM_BASE}/domains") as resp:
            data = await resp.json()
            members = data.get("hydra:member", [])
            return [d["domain"] for d in members if not d.get("isPrivate", False)]


async def create_account() -> dict | None:
    """
    Create a random mailbox on mail.tm.
    Returns dict with keys: address, password, token, account_id
    """
    domains = await get_domains()
    if not domains:
        logger.error("No domains available from mail.tm")
        return None

    domain   = domains[0]
    username = _random_string(10)
    address  = f"{username}@{domain}"
    password = _random_string(16)

    async with aiohttp.ClientSession() as session:
        # 1. Register account
        async with session.post(
            f"{MAIL_TM_BASE}/accounts",
            json={"address": address, "password": password},
            headers={"Content-Type": "application/json"},
        ) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                logger.error("Failed to create account: %s – %s", resp.status, text)
                return None
            account_data = await resp.json()
            account_id = account_data.get("id", "")

        # 2. Get JWT token
        async with session.post(
            f"{MAIL_TM_BASE}/token",
            json={"address": address, "password": password},
            headers={"Content-Type": "application/json"},
        ) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                logger.error("Failed to get token: %s – %s", resp.status, text)
                return None
            token_data = await resp.json()
            token = token_data.get("token", "")

    return {
        "address":    address,
        "password":   password,
        "token":      token,
        "account_id": account_id,
    }


async def get_messages(token: str) -> list[dict]:
    """Fetch inbox messages for the given token."""
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{MAIL_TM_BASE}/messages", headers=headers) as resp:
            if resp.status == 401:
                logger.warning("Token expired / invalid")
                return []
            if resp.status != 200:
                return []
            data = await resp.json()
            return data.get("hydra:member", [])


async def get_message_body(token: str, message_id: str) -> str:
    """Fetch full text/html body of a single message."""
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{MAIL_TM_BASE}/messages/{message_id}", headers=headers) as resp:
            if resp.status != 200:
                return ""
            data = await resp.json()
            # Prefer plain text, fall back to html stripped
            text = data.get("text", "")
            if not text:
                html = data.get("html", [""])
                if isinstance(html, list):
                    html = "\n".join(html)
                # Very basic strip
                import re
                text = re.sub(r"<[^>]+>", "", html)
            return text.strip()


async def delete_account(token: str, account_id: str) -> bool:
    """Delete a mail.tm account."""
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession() as session:
        async with session.delete(
            f"{MAIL_TM_BASE}/accounts/{account_id}", headers=headers
        ) as resp:
            return resp.status in (200, 204)
