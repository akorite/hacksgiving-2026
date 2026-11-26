from __future__ import annotations

import json

import httpx

from .gateway import GatewayClient


class TelegramClient:
    def __init__(self, gateway: GatewayClient, max_download: int = 16 * 1024 * 1024):
        self.gateway = gateway; self.max_download = max_download

    async def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None) -> dict:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
        if reply_markup: payload["reply_markup"] = reply_markup
        r = await self.gateway.request("POST", "sendMessage", json=payload); r.raise_for_status(); return r.json()["result"]

    async def send_photo(self, chat_id: int, png: bytes, caption: str, reply_markup: dict | None = None) -> dict:
        data = {"chat_id": str(chat_id), "caption": caption}
        if reply_markup: data["reply_markup"] = json.dumps(reply_markup)
        r = await self.gateway.request("POST", "sendPhoto", data=data, files={"photo": ("xray.png", png, "image/png")})
        r.raise_for_status(); return r.json()["result"]

    async def answer_callback_query(self, callback_id: str, text: str = "") -> None:
        r = await self.gateway.request("POST", "answerCallbackQuery", json={"callback_query_id": callback_id, "text": text}); r.raise_for_status()

    async def edit_message_reply_markup(self, chat_id: int, message_id: int, reply_markup: dict | None = None) -> None:
        r = await self.gateway.request("POST", "editMessageReplyMarkup", json={"chat_id": chat_id, "message_id": message_id, "reply_markup": reply_markup or {}}); r.raise_for_status()

    async def download_file(self, file_id: str) -> bytes:
        r = await self.gateway.request("POST", "getFile", json={"file_id": file_id}); r.raise_for_status()
        result = r.json()["result"]
        if result.get("file_size", 0) > 20 * 1024 * 1024:
            raise ValueError("Telegram-hosted Bot API cannot download files over 20 MB")
        path = result["file_path"]
        r = await self.gateway.request("GET", "file/" + path)
        r.raise_for_status()
        if len(r.content) > self.max_download:
            raise ValueError("file exceeds Cupbearer 16 MiB artifact cap")
        return r.content
