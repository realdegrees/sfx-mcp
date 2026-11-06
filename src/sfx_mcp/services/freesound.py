from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import secrets
import time
from collections import deque

import httpx

from ..config import config

logger = logging.getLogger("sfx-mcp")


class FreeSoundAPI:
    """HTTP client for the FreeSound API v2.

    Handles rate limiting (~18 req/min to stay under the 20/min free tier cap),
    pagination, and auth via Bearer token.
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None
        self._request_times: deque[float] = deque()
        self._semaphore = asyncio.Semaphore(3)

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=config.API_BASE_URL,
                timeout=30.0,
                headers={"Authorization": f"Token {self.api_key}"},
            )
        return self._client

    async def _rate_limit(self) -> None:
        now = time.monotonic()
        while self._request_times and now - self._request_times[0] > 60:
            self._request_times.popleft()
        if len(self._request_times) >= 18:
            sleep_for = 60 - (now - self._request_times[0])
            if sleep_for > 0:
                logger.debug("Rate limit: sleeping %.1fs", sleep_for)
                await asyncio.sleep(sleep_for)
        self._request_times.append(time.monotonic())

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        async with self._semaphore:
            await self._rate_limit()
            try:
                response = await self.client.request(method, path, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                detail = e.response.text[:500]
                if status == 429:
                    logger.warning("FreeSound 429 (rate limited): %s", detail)
                    retry_after = int(e.response.headers.get("Retry-After", "60"))
                    await asyncio.sleep(retry_after)
                    return await self._request(method, path, **kwargs)
                if status == 401:
                    raise RuntimeError(
                        "FreeSound API key is invalid or missing. "
                        "Set FREESOUND_API_KEY in .env or environment."
                    ) from e
                raise RuntimeError(f"FreeSound API error {status}: {detail}") from e
            except httpx.TimeoutException as e:
                raise RuntimeError(
                    "FreeSound API request timed out. Check network connectivity."
                ) from e

    async def search(
        self,
        query: str,
        duration_max: int = 30,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 15,
    ) -> dict:
        """Search CC0 sounds on FreeSound.

        Returns paginated results with sound metadata.
        """
        params = {
            "query": query,
            "filter": f'license:"Creative Commons 0" duration:[0 TO {duration_max}]',
            "page": page,
            "page_size": min(page_size, 50),
            "fields": "id,name,description,duration,samplerate,tags,previews,url,download",
        }
        return await self._request("GET", "/search/text/", params=params)

    async def similar(self, sound_id: int, page: int = 1) -> dict:
        """Sounds acoustically similar to sound_id. This endpoint ignores the license filter."""
        return await self._request(
            "GET",
            f"/sounds/{sound_id}/similar/",
            params={
                "page": page,
                "page_size": 50,
                "fields": "id,name,description,duration,samplerate,tags,previews,url,license",
            },
        )

    async def get_sound_detail(self, sound_id: int) -> dict:
        """Get detailed metadata for a specific sound."""
        return await self._request(
            "GET",
            f"/sounds/{sound_id}/",
            params={
                "fields": "id,name,description,duration,samplerate,tags,previews,url,download,type"
            },
        )

    def authorize_url(self) -> str:
        verifier = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        os.makedirs(os.path.dirname(config.SFX_TOKEN_PATH) or ".", exist_ok=True)
        with open(self._verifier_path(), "w", encoding="utf-8") as f:
            f.write(verifier)
        return (
            f"{config.API_BASE_URL}/oauth2/authorize/"
            f"?client_id={config.FREESOUND_CLIENT_ID}&response_type=code"
            f"&code_challenge={challenge}&code_challenge_method=S256"
        )

    async def exchange_code(self, code: str) -> None:
        try:
            with open(self._verifier_path(), encoding="utf-8") as f:
                verifier = f.read().strip()
        except OSError as e:
            raise RuntimeError(
                "No pending authorization. Call authorize without a code first."
            ) from e
        await self._token_request(
            {"grant_type": "authorization_code", "code": code, "code_verifier": verifier}
        )
        os.remove(self._verifier_path())

    @staticmethod
    def _verifier_path() -> str:
        return os.path.join(os.path.dirname(config.SFX_TOKEN_PATH), "oauth_pkce_verifier")

    def has_oauth_token(self) -> bool:
        return self._load_token() is not None

    def _load_token(self) -> dict | None:
        try:
            with open(config.SFX_TOKEN_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    async def _token_request(self, grant: dict) -> dict:
        response = await self.client.post(
            "/oauth2/access_token/",
            data={
                "client_id": config.FREESOUND_CLIENT_ID,
                "client_secret": self.api_key,
                **grant,
            },
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"FreeSound OAuth2 token request failed ({response.status_code}): "
                f"{response.text[:300]}"
            )
        data = response.json()
        token = {
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            # Renew a minute early so a token never expires mid-download.
            "expires_at": time.time() + int(data.get("expires_in", 86400)) - 60,
        }
        os.makedirs(os.path.dirname(config.SFX_TOKEN_PATH) or ".", exist_ok=True)
        with open(config.SFX_TOKEN_PATH, "w", encoding="utf-8") as f:
            json.dump(token, f)
        return token

    async def _access_token(self) -> str:
        token = self._load_token()
        if token is None:
            raise RuntimeError(
                "Downloads need a one-time OAuth2 authorization. Call "
                "sfx_search(operation='authorize') for the URL, then pass the code "
                "it shows as sfx_search(operation='authorize', code=...)."
            )
        if time.time() >= token["expires_at"]:
            token = await self._token_request(
                {"grant_type": "refresh_token", "refresh_token": token["refresh_token"]}
            )
        return token["access_token"]

    async def download_original(self, sound_id: int) -> bytes:
        """Download a sound's original file. FreeSound accepts only OAuth2 here."""
        access = await self._access_token()
        async with self._semaphore:
            await self._rate_limit()
            response = await self.client.get(
                f"/sounds/{sound_id}/download/",
                headers={"Authorization": f"Bearer {access}"},
                follow_redirects=True,
                timeout=120.0,
            )
        if response.status_code != 200:
            raise RuntimeError(
                f"FreeSound download failed ({response.status_code}): {response.text[:300]}"
            )
        return response.content

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
