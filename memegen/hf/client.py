"""Thin Higgsfield REST client.

Written directly on httpx (instead of higgsfield-client) so billing-relevant behaviour is explicit:
generation POSTs are never retried after an ambiguous failure (the docs warn this can double-charge).
The only automatic resubmit is on the concurrency-limit 400, where the request was never accepted.
"""

from __future__ import annotations

import mimetypes
import random
import time
from pathlib import Path
from typing import Any, Callable

import httpx

from memegen.hf.endpoints import BASE_URL

TERMINAL_STATUSES = {"completed", "failed", "nsfw", "canceled"}


class HFError(RuntimeError):
    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Higgsfield API {status_code}: {detail}")

    @property
    def is_concurrency_limit(self) -> bool:
        return self.status_code == 400 and "concurrent" in str(self.detail).lower()


class GenerationFailed(RuntimeError):
    def __init__(self, result: dict):
        self.result = result
        super().__init__(f"request {result.get('request_id')} ended as {result.get('status')}: {result.get('error')}")


def _detail(response: httpx.Response) -> Any:
    try:
        data = response.json()
    except ValueError:
        return response.text
    return data.get("detail") or data.get("message") or data.get("error") or data


class HiggsfieldClient:
    def __init__(self, key: str, base_url: str = BASE_URL, timeout: float = 60.0):
        if not key or ":" not in key:
            raise ValueError("HF_KEY must look like 'KEY_ID:KEY_SECRET' (create one at console.higgsfield.ai)")
        self._http = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={"Authorization": f"Key {key}", "User-Agent": "memegen/0.1"},
        )
        # Presigned storage URLs must NOT receive our credentials.
        self._storage = httpx.Client(timeout=300.0)

    # ---- low level -------------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> dict:
        response = self._http.request(method, path, **kwargs)
        if response.status_code >= 400:
            raise HFError(response.status_code, _detail(response))
        return response.json() if response.content else {}

    # ---- uploads ---------------------------------------------------------------------------

    def upload_file(self, path: str | Path) -> str:
        """Upload a local file and return its public URL (usable as video_url / image_urls)."""
        path = Path(path)
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        ticket = self._request("POST", "/files/generate-upload-url", json={"content_type": content_type})
        headers = ticket.get("upload_headers") or {"Content-Type": content_type}
        response = self._storage.put(ticket["upload_url"], content=path.read_bytes(), headers=headers)
        if response.status_code >= 400:
            raise HFError(response.status_code, f"upload PUT failed: {response.text[:300]}")
        return ticket["public_url"]

    # ---- async generation ------------------------------------------------------------------

    def submit(self, model_path: str, arguments: dict, *, concurrency_wait: float = 15.0,
               max_concurrency_retries: int = 20) -> dict:
        """POST a generation. Returns {request_id, status_url, cancel_url, status}."""
        for attempt in range(max_concurrency_retries + 1):
            try:
                return self._request("POST", f"/{model_path}", json=arguments)
            except HFError as error:
                if error.is_concurrency_limit and attempt < max_concurrency_retries:
                    time.sleep(concurrency_wait)
                    continue
                raise
        raise AssertionError("unreachable")

    def status(self, request_id: str) -> dict:
        return self._request("GET", f"/requests/{request_id}/status")

    def cancel(self, request_id: str) -> None:
        self._request("POST", f"/requests/{request_id}/cancel")

    def wait(self, request_id: str, *, timeout: float = 1800.0,
             on_update: Callable[[dict], None] | None = None) -> dict:
        """Poll with the documented backoff (2s, x1.5, cap 10s, +jitter) until a terminal status."""
        delay, deadline, last = 2.0, time.monotonic() + timeout, None
        while True:
            result = self.status(request_id)
            if on_update and result.get("status") != last:
                on_update(result)
            last = result.get("status")
            if last in TERMINAL_STATUSES:
                return result
            if time.monotonic() > deadline:
                raise TimeoutError(f"request {request_id} still {last} after {timeout:.0f}s")
            time.sleep(delay + random.uniform(0, 0.5))
            delay = min(delay * 1.5, 10.0)

    def run(self, model_path: str, arguments: dict, **wait_kwargs) -> dict:
        """submit + wait; raises GenerationFailed unless completed."""
        ticket = self.submit(model_path, arguments)
        result = self.wait(ticket["request_id"], **wait_kwargs)
        if result.get("status") != "completed":
            raise GenerationFailed(result)
        return result

    def estimate(self, model_path: str, arguments: dict) -> dict:
        """Credits/USD estimate for the same body you would submit."""
        return self._request("POST", f"/estimate/{model_path}", json=arguments)

    # ---- outputs ---------------------------------------------------------------------------

    def download(self, url: str, dest: str | Path) -> Path:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self._storage.stream("GET", url, follow_redirects=True) as response:
            response.raise_for_status()
            with dest.open("wb") as fh:
                for chunk in response.iter_bytes():
                    fh.write(chunk)
        return dest


def output_urls(result: dict) -> list[str]:
    """Collect media URLs from a completed result (video / images / audio shapes)."""
    urls: list[str] = []
    if isinstance(result.get("video"), dict) and result["video"].get("url"):
        urls.append(result["video"]["url"])
    for image in result.get("images") or []:
        if image.get("url"):
            urls.append(image["url"])
    if isinstance(result.get("audio"), dict) and result["audio"].get("url"):
        urls.append(result["audio"]["url"])
    return urls
