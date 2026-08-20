"""Shared, versioned instrument-directory state and GitHub persistence helpers."""
from __future__ import annotations

import base64
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hmac
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from instruments import InstrumentSpec


DIRECTORY_STATE_VERSION = 1
DIRECTORY_REPOSITORY = "milaotou001/etf-quant"
DIRECTORY_STATE_PATH = "mobile/instrument_directory.json"
DIRECTORY_BRANCH = "master"
_CN_CODE = re.compile(r"^\d{6}$")


class DirectoryStateError(ValueError):
    """Raised when the public directory JSON is malformed."""


class DirectoryRemoteError(RuntimeError):
    """Raised when the GitHub directory file cannot be read or saved safely."""


@dataclass(frozen=True)
class DirectorySnapshot:
    state: dict
    sha: str


def empty_directory_state() -> dict:
    """Return the canonical empty personal-directory state."""
    return {
        "version": DIRECTORY_STATE_VERSION,
        "custom_instruments": [],
        "hidden_symbols": [],
    }


def _normalize_symbol(value: object) -> str:
    symbol = str(value).strip().upper()
    if not _CN_CODE.fullmatch(symbol):
        raise DirectoryStateError("自定义标的必须是六位中国股票或 ETF 代码")
    return symbol


def _normalize_custom_entry(entry: object) -> dict:
    if not isinstance(entry, Mapping):
        raise DirectoryStateError("自定义标的记录格式无效")
    symbol = _normalize_symbol(entry.get("symbol", ""))
    name = str(entry.get("name", "")).strip()
    if not name:
        name = f"{symbol} · 自定义观察"
    market = str(entry.get("market", "CN")).strip() or "CN"
    category = str(entry.get("category", "自定义")).strip() or "自定义"
    return {"symbol": symbol, "name": name, "market": market, "category": category}


def normalize_directory_state(value: object) -> dict:
    """Validate and canonicalize the tracked directory state without losing order."""
    if not isinstance(value, Mapping):
        raise DirectoryStateError("共享目录格式无效")
    if value.get("version") != DIRECTORY_STATE_VERSION:
        raise DirectoryStateError(f"共享目录版本不兼容：需要 {DIRECTORY_STATE_VERSION}")

    raw_custom = value.get("custom_instruments")
    raw_hidden = value.get("hidden_symbols")
    if not isinstance(raw_custom, list) or not isinstance(raw_hidden, list):
        raise DirectoryStateError("共享目录缺少自定义标的或隐藏标的列表")

    custom_instruments = []
    custom_symbols = set()
    for entry in raw_custom:
        normalized = _normalize_custom_entry(entry)
        if normalized["symbol"] in custom_symbols:
            raise DirectoryStateError(f"自定义标的重复：{normalized['symbol']}")
        custom_symbols.add(normalized["symbol"])
        custom_instruments.append(normalized)

    hidden_symbols = []
    seen_hidden = set()
    for value in raw_hidden:
        symbol = str(value).strip().upper()
        if not symbol:
            raise DirectoryStateError("隐藏标的代码不能为空")
        if symbol not in seen_hidden:
            seen_hidden.add(symbol)
            hidden_symbols.append(symbol)

    return {
        "version": DIRECTORY_STATE_VERSION,
        "custom_instruments": custom_instruments,
        "hidden_symbols": hidden_symbols,
    }


def add_custom_instrument(state: object, symbol: object, name: object | None = None) -> dict:
    """Append a named observation instrument once, preserving directory order."""
    normalized = normalize_directory_state(state)
    custom_symbol = _normalize_symbol(symbol)
    custom_name = str(name or custom_symbol).strip() or custom_symbol
    if any(entry["symbol"] == custom_symbol for entry in normalized["custom_instruments"]):
        return normalized
    normalized["custom_instruments"].append(
        {"symbol": custom_symbol, "name": custom_name, "market": "CN", "category": "自定义"}
    )
    return normalized


def hide_instrument(state: object, symbol: object) -> dict:
    normalized = normalize_directory_state(state)
    target = str(symbol).strip().upper()
    if not target:
        raise DirectoryStateError("隐藏标的代码不能为空")
    if target not in normalized["hidden_symbols"]:
        normalized["hidden_symbols"].append(target)
    return normalized


def restore_instrument(state: object, symbol: object) -> dict:
    normalized = normalize_directory_state(state)
    target = str(symbol).strip().upper()
    normalized["hidden_symbols"] = [item for item in normalized["hidden_symbols"] if item != target]
    return normalized


def reset_directory_state() -> dict:
    return empty_directory_state()


def directory_admin_pin_matches(candidate: object, secrets: Mapping[str, object]) -> bool:
    """Compare a management PIN without treating an absent secret as an empty PIN."""
    configured = str(secrets.get("DIRECTORY_ADMIN_PIN", "")).strip()
    provided = str(candidate or "")
    return bool(configured) and hmac.compare_digest(provided, configured)


def apply_directory_state(base_specs: tuple[InstrumentSpec, ...], state: object) -> tuple[InstrumentSpec, ...]:
    """Apply personal additions and hides while leaving static strategy specs untouched."""
    normalized = normalize_directory_state(state)
    hidden = set(normalized["hidden_symbols"])
    base_symbols = {spec.symbol for spec in base_specs}
    visible = [spec for spec in base_specs if spec.symbol not in hidden]
    for entry in normalized["custom_instruments"]:
        if entry["symbol"] not in hidden and entry["symbol"] not in base_symbols:
            visible.append(
                InstrumentSpec(
                    entry["symbol"],
                    entry["name"],
                    entry["market"],
                    entry["category"],
                    False,
                )
            )
    return tuple(visible)


class GitHubDirectoryStore:
    """Read and atomically update only the tracked public directory JSON file."""

    def __init__(
        self,
        token: str | None,
        *,
        repository: str = DIRECTORY_REPOSITORY,
        path: str = DIRECTORY_STATE_PATH,
        branch: str = DIRECTORY_BRANCH,
        opener: Callable = urlopen,
    ) -> None:
        self.token = token.strip() if token else None
        self.repository = repository
        self.path = path
        self.branch = branch
        self._opener = opener

    @property
    def _url(self) -> str:
        return f"https://api.github.com/repos/{self.repository}/contents/{self.path}"

    def _request(self, method: str, payload: dict | None = None) -> Request:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "etf-quant-directory-sync",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        if data is not None:
            headers["Content-Type"] = "application/json"
        return Request(self._url, data=data, headers=headers, method=method)

    def _open_json(self, request: Request) -> dict:
        try:
            with self._opener(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code in {409, 422}:
                raise DirectoryRemoteError("共享目录已被其他设备修改，请刷新后重试") from exc
            if exc.code in {401, 403}:
                raise DirectoryRemoteError("GitHub 目录令牌无效或无权修改此仓库") from exc
            raise DirectoryRemoteError(f"GitHub 目录请求失败（HTTP {exc.code}）") from exc
        except URLError as exc:
            raise DirectoryRemoteError("网络不可用，暂时无法同步共享目录") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DirectoryRemoteError("GitHub 返回的共享目录数据无效") from exc

    def read(self) -> DirectorySnapshot:
        payload = self._open_json(self._request("GET"))
        try:
            encoded_content = "".join(str(payload["content"]).split())
            content = base64.b64decode(encoded_content.encode("ascii"), validate=True)
            state = normalize_directory_state(json.loads(content.decode("utf-8")))
            sha = str(payload["sha"])
        except (KeyError, UnicodeDecodeError, ValueError, json.JSONDecodeError, DirectoryStateError) as exc:
            raise DirectoryRemoteError("GitHub 中的共享目录文件无效") from exc
        return DirectorySnapshot(state=state, sha=sha)

    def write(self, snapshot: DirectorySnapshot, state: object, message: str) -> str:
        if not self.token:
            raise DirectoryRemoteError("云端未配置 DIRECTORY_GITHUB_TOKEN，目录保持只读")
        normalized = normalize_directory_state(state)
        content = json.dumps(normalized, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        response = self._open_json(
            self._request(
                "PUT",
                {
                    "message": message,
                    "content": base64.b64encode(content).decode("ascii"),
                    "sha": snapshot.sha,
                    "branch": self.branch,
                },
            )
        )
        try:
            return str(response["commit"]["sha"])
        except (KeyError, TypeError) as exc:
            raise DirectoryRemoteError("GitHub 未返回目录提交结果") from exc
