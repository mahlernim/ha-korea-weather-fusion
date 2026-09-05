"""Bounded reads shared by runtime polling and setup validation."""

import asyncio

import aiohttp

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
HEADERS = {
    "User-Agent": "Home Assistant Korea Weather Fusion",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
}


async def async_fetch_page(session: aiohttp.ClientSession, url: str) -> str:
    """Read a page without buffering an unbounded response."""
    async with asyncio.timeout(21):
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=20), headers=HEADERS
        ) as response:
            response.raise_for_status()
            if (response.content_length or 0) > MAX_RESPONSE_BYTES:
                raise ValueError("response_too_large")
            data = bytearray()
            async for chunk in response.content.iter_chunked(64 * 1024):
                if len(data) + len(chunk) > MAX_RESPONSE_BYTES:
                    raise ValueError("response_too_large")
                data.extend(chunk)
            try:
                return data.decode(response.charset or "utf-8")
            except (LookupError, UnicodeDecodeError) as err:
                raise ValueError("invalid_encoding") from err
