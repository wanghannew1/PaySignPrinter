"""
Cache manager for DingTalk API responses.
Avoids repeated API calls by persisting query results to local JSON.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

CACHE_FILE = Path(__file__).parent / "approval_cache.json"


def _load_cache_file() -> Dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"instance_lists": {}, "instance_details": {}, "stats": {"hits": 0, "misses": 0}}


def _save_cache_file(cache: Dict) -> None:
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[cache] save failed: {e}")


def _list_cache_key(start_time: int, end_time: int, statuses: Optional[List[str]]) -> str:
    status_key = ",".join(sorted(statuses)) if statuses else "ALL"
    return f"{start_time}_{end_time}_{status_key}"


def get_cached_instance_list(
    start_time: int,
    end_time: int,
    statuses: Optional[List[str]],
) -> Optional[List[str]]:
    cache = _load_cache_file()
    key = _list_cache_key(start_time, end_time, statuses)
    entry = cache.get("instance_lists", {}).get(key)
    if entry and isinstance(entry.get("ids"), list):
        cache["stats"]["hits"] += 1
        _save_cache_file(cache)
        print(f"[cache] LIST HIT  key={key}  count={len(entry['ids'])}")
        return entry["ids"]
    cache["stats"]["misses"] += 1
    _save_cache_file(cache)
    print(f"[cache] LIST MISS key={key}")
    return None


def cache_instance_list(
    start_time: int,
    end_time: int,
    statuses: Optional[List[str]],
    ids: List[str],
) -> None:
    cache = _load_cache_file()
    key = _list_cache_key(start_time, end_time, statuses)
    cache.setdefault("instance_lists", {})[key] = {
        "ids": ids,
        "cached_at": time.time(),
    }
    _save_cache_file(cache)
    print(f"[cache] LIST SAVE key={key}  count={len(ids)}")


def get_cached_instance_details(instance_id: str) -> Optional[Dict[str, Any]]:
    cache = _load_cache_file()
    entry = cache.get("instance_details", {}).get(instance_id)
    if entry and isinstance(entry.get("data"), dict):
        cache["stats"]["hits"] += 1
        _save_cache_file(cache)
        status = entry["data"].get("status", "UNKNOWN")
        print(f"[cache] DETAIL HIT  id={instance_id[:20]}...  status={status}")
        return entry["data"]
    cache["stats"]["misses"] += 1
    _save_cache_file(cache)
    print(f"[cache] DETAIL MISS id={instance_id[:20]}...")
    return None


def cache_instance_details(instance_id: str, data: Dict[str, Any]) -> None:
    cache = _load_cache_file()
    cache.setdefault("instance_details", {})[instance_id] = {
        "data": data,
        "cached_at": time.time(),
    }
    _save_cache_file(cache)
    status = data.get("status", "UNKNOWN")
    print(f"[cache] DETAIL SAVE id={instance_id[:20]}...  status={status}")


def clear_cache() -> None:
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
    print("[cache] CLEARED")


def get_stats() -> Dict[str, int]:
    cache = _load_cache_file()
    return dict(cache.get("stats", {"hits": 0, "misses": 0}))


def cache_file_path() -> Path:
    return CACHE_FILE


DOWNLOAD_URL_TTL = 15 * 60


def _download_url_cache_key(instance_id: str, file_id: str) -> str:
    return f"{instance_id}:{file_id}"


def get_cached_download_url(instance_id: str, file_id: str) -> Optional[str]:
    cache = _load_cache_file()
    key = _download_url_cache_key(instance_id, file_id)
    entry = cache.get("download_urls", {}).get(key)
    if entry:
        url = entry.get("url")
        cached_at = entry.get("cached_at", 0)
        if url and (time.time() - cached_at) < DOWNLOAD_URL_TTL:
            print(f"[cache] URL HIT  key={key[:40]}...")
            return url
    print(f"[cache] URL MISS key={key[:40]}...")
    return None


def cache_download_url(instance_id: str, file_id: str, url: str) -> None:
    cache = _load_cache_file()
    key = _download_url_cache_key(instance_id, file_id)
    cache.setdefault("download_urls", {})[key] = {
        "url": url,
        "cached_at": time.time(),
    }
    _save_cache_file(cache)
    print(f"[cache] URL SAVE key={key[:40]}...")
