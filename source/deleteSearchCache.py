#!/usr/bin/env python3
"""
Delete cached EPUB search artifacts by cache ID.

Usage:
  python3 deleteSearchCache.py <cache_id> [--alfred]
"""

import glob
import json
import os
import re
import sys
import tempfile


def _cache_root():
    try:
        from config import CACHE_FOLDER
    except Exception:
        CACHE_FOLDER = tempfile.gettempdir()
    root = os.path.join(CACHE_FOLDER, "epub_search")
    os.makedirs(root, exist_ok=True)
    return root


def _validate_cache_id(cache_id):
    value = (cache_id or "").strip()
    if re.fullmatch(r"[0-9a-f]{8,64}", value):
        return value
    return ""


def _emit(text, ok=False, alfred=False):
    if not alfred:
        print(text)
        return
    payload = {
        "items": [
            {
                "uid": "delete-cache-result",
                "title": text,
                "subtitle": "",
                "icon": {"path": "icon.png"},
                "valid": False,
            }
        ],
        "skipknowledge": True,
    }
    if not ok:
        payload["items"][0]["icon"] = {"path": "icons/Warning.png"}
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main():
    args = sys.argv[1:]
    alfred = False
    if "--alfred" in args:
        alfred = True
        args = [a for a in args if a != "--alfred"]

    cache_id = _validate_cache_id(args[0] if args else "")
    if not cache_id:
        _emit("Invalid cache ID", ok=False, alfred=alfred)
        return 1

    root = _cache_root()
    removed = []
    cached_query = ""
    main_cache = os.path.join(root, f"search_{cache_id}.json")
    if os.path.isfile(main_cache):
        try:
            with open(main_cache, "r", encoding="utf-8") as f:
                payload = json.load(f)
            cached_query = (payload.get("search_text") or "").strip()
        except Exception:
            cached_query = ""
        try:
            os.remove(main_cache)
            removed.append(main_cache)
        except OSError:
            pass

    # Best-effort cleanup of background job artifacts that include this ID.
    bg_dir = os.path.join(root, "bg_jobs")
    if os.path.isdir(bg_dir):
        patterns = [
            os.path.join(bg_dir, f"*{cache_id}*.job.json"),
            os.path.join(bg_dir, f"*{cache_id}*.status.json"),
            os.path.join(bg_dir, f"*{cache_id}*.log"),
        ]
        for pat in patterns:
            for p in glob.glob(pat):
                try:
                    os.remove(p)
                    removed.append(p)
                except OSError:
                    pass

    if removed:
        query_part = f" for '{cached_query}'" if cached_query else ""
        _emit(
            f"Deleted cache{query_part} ({len(removed)} file{'s' if len(removed) != 1 else ''})",
            ok=True,
            alfred=alfred,
        )
        return 0

    _emit(f"Cache {cache_id} not found", ok=False, alfred=alfred)
    return 1


if __name__ == "__main__":
    sys.exit(main())

