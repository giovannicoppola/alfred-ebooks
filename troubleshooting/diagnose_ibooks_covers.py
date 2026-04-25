#!/usr/bin/env python3
"""
List Apple Books titles whose workflow cover cache is missing or not a JPEG/PNG.

Covers are stored as extensionless files named by ZASSETID under
  {alfred_workflow_cache}/images/ibooks/
so Finder often labels them "data" or "document" even when valid.

Run from repo root or anywhere:
  python3 troubleshooting/diagnose_ibooks_covers.py

Optional:
  alfred_workflow_cache=/path/to/workflow/cache python3 ...

If alfred_workflow_cache is unset, the default Alfred 5 path for bundle
giovanni.alfred-ebooks is used.
"""
from __future__ import annotations

import os
import sqlite3
import sys

def _bklibrary_db() -> str:
    base = os.path.expanduser(
        "~/Library/Containers/com.apple.iBooksX/Data/Documents/BKLibrary/"
    )
    if not os.path.isdir(base):
        return ""
    dbs = [
        each
        for each in os.listdir(base)
        if each.endswith(".sqlite") and each.startswith("BKLibrary")
    ]
    if not dbs:
        return ""
    return os.path.join(base, dbs[0])


def _default_alfred_cache() -> str:
    home = os.path.expanduser("~")
    return os.path.join(
        home,
        "Library",
        "Caches",
        "com.runningwithcrayons.Alfred",
        "Workflow Data",
        "giovanni.alfred-ebooks",
    )


def _classify_file(path: str) -> tuple[str, str]:
    """
    Return (category, detail).
    category: missing | jpeg | png | gif | webp | heic | gzip | html | tiny | other
    """
    if not os.path.isfile(path):
        return ("missing", "")
    size = os.path.getsize(path)
    if size < 16:
        return ("tiny", f"{size} bytes")
    with open(path, "rb") as f:
        h = f.read(16)
    if h[:2] == b"\xff\xd8":
        return ("jpeg", f"{size} B")
    if h[:4] == b"\x89PNG":
        return ("png", f"{size} B")
    if h[:6] in (b"GIF87a", b"GIF89a"):
        return ("gif", f"{size} B")
    if h[:4] == b"RIFF" and h[8:12] == b"WEBP":
        return ("webp", f"{size} B")
    if h[4:8] == b"ftyp" and b"heic" in h[:12].lower():
        return ("heic", f"{size} B")
    if h[:2] == b"\x1f\x8b":
        return ("gzip", f"{size} B (often encrypted EPUB resource)")
    if h[:1] == b"<" or h[:4] == b"\xef\xbb\xbf<!":
        return ("html", f"{size} B (URL likely returned a web page)")
    if h[:4] == b"%PDF":
        return ("pdf", f"{size} B")
    return ("other", f"{size} B hex={h[:8].hex()}")


def _bc_cover_dir(asset_id: str) -> str:
    return os.path.expanduser(
        f"~/Library/Containers/com.apple.iBooksX/Data/Library/Caches/"
        f"BCCoverCache-1/BICDiskDataStore/{asset_id}"
    )


def main() -> int:
    cache = os.getenv("alfred_workflow_cache") or _default_alfred_cache()
    ibooks_dir = os.path.join(cache, "images", "ibooks")
    db = _bklibrary_db()
    if not db:
        print("Apple Books BKLibrary database not found.", file=sys.stderr)
        return 1
    if not os.path.isdir(ibooks_dir):
        print(f"iBooks image cache folder missing: {ibooks_dir}", file=sys.stderr)
        print("(Set alfred_workflow_cache if your workflow uses a different path.)", file=sys.stderr)

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        'SELECT "_rowid_",* FROM "main"."ZBKLIBRARYASSET" '
        "ORDER BY ZTITLE COLLATE NOCASE"
    )
    rows = cur.fetchall()
    conn.close()

    ok = {"jpeg", "png"}
    problems = []
    for row in rows:
        r = dict(row)
        if r.get("ZSTATE") == 5:
            continue
        aid = r.get("ZASSETID") or ""
        title = (r.get("ZTITLE") or "").strip() or "(no title)"
        path = r.get("ZPATH") or ""
        cover_url = r.get("ZCOVERURL")
        icon_path = os.path.join(ibooks_dir, aid) if aid else ""
        cat, detail = _classify_file(icon_path) if aid else ("missing", "no asset id")

        if cat in ok:
            continue

        bc = _bc_cover_dir(aid)
        has_bc_heic = False
        if os.path.isdir(bc):
            has_bc_heic = any(name.endswith(".heic") for name in os.listdir(bc))

        problems.append(
            {
                "title": title,
                "asset_id": aid,
                "file_kind": cat,
                "detail": detail,
                "zpath": path,
                "has_cover_url": cover_url is not None and str(cover_url).strip() != "",
                "epub": bool(path and str(path).lower().endswith(".epub")),
                "bcc_heic": has_bc_heic,
            }
        )

    print(f"Cache dir: {ibooks_dir}")
    print(f"BKLibrary: {db}")
    print(f"Total library rows (excl. ZSTATE=5): {len(rows)}")
    print(f"Titles without a JPEG/PNG cover file in cache: {len(problems)}")
    print()

    w = max(len(p["title"]) for p in problems) if problems else 10
    w = min(w, 56)
    hdr = f"{'TITLE':<{w}}  {'KIND':<8}  URL  EPUB  BC.heic  ASSET_ID"
    print(hdr)
    print("-" * len(hdr))
    for p in sorted(problems, key=lambda x: (x["file_kind"], x["title"].lower())):
        t = p["title"] if len(p["title"]) <= w else p["title"][: w - 1] + "…"
        url = "y" if p["has_cover_url"] else "n"
        ep = "y" if p["epub"] else "n"
        bc = "y" if p["bcc_heic"] else "n"
        print(
            f"{t:<{w}}  {p['file_kind']:<8}  {url}    {ep}    {bc}       {p['asset_id']}"
        )
        if p["detail"] and p["file_kind"] not in ("missing",):
            print(f"{' ' * w}    ({p['detail']})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
