# Feasibility: Setting tags / labels from the workflow

**Date:** 2026-04-21
**Status:** Exploratory — not implemented

Today `alfred-eBooks` only *reads* tags / Collections from each supported
library (see `source/kindle_fun.py`: `get_calibre`, `get_yomu`, `get_ibooks`,
`_get_ibooks_collections`). This note captures what it would take to also
*write* tags back, per source.

## Summary

| Source      | Feasible? | Mechanism                                | Risk level |
| ----------- | --------- | ---------------------------------------- | ---------- |
| Calibre     | Yes       | `calibredb set_metadata` CLI (official)  | Low        |
| Apple Books | Partially | Direct SQLite writes to `BKLibrary`      | High       |
| Yomu        | Partially | Direct SQLite writes to CoreData store   | High       |
| Kindle      | No        | No local tag storage; cloud-only, no API | —          |

## 1. Calibre — fully feasible, officially supported

Current read path: `metadata.db` → `books_tags_link` ⋈ `tags`
(`source/kindle_fun.py` lines ~279–288).

Calibre ships `calibredb`, the supported CLI for mutating a library. Setting
tags is a one-liner:

```bash
"/Applications/calibre.app/Contents/MacOS/calibredb" set_metadata \
    --library-path "$CALIBRE_LIBRARY_PATH" \
    --field "tags:science,fiction,favorites" \
    <book_id>
```

- Handles creating missing tag rows, updating the link table, bumping
  modification timestamps.
- Works while Calibre is running (uses the library lock correctly).
- `set_custom` / `add_custom_column` available for custom columns.
- Round-trips cleanly: next `::books-refresh` surfaces the new tag via the
  existing `get_calibre()` query.

This is the easy win and a good first step to validate the UX.

## 2. Apple Books (iBooks / Collections) — unsupported, fragile

Current read path: `BKLibrary*.sqlite` → `ZBKCOLLECTION` +
`ZBKCOLLECTIONMEMBER` (`_get_ibooks_collections`, line ~608).

Writing back is possible but painful:

- **No AppleScript / URL-scheme / public API** for Collections. Books.app
  exposes essentially nothing for Collection membership.
- **Direct SQLite writes**: insert into `ZBKCOLLECTIONMEMBER` joining
  `ZASSETID` to an existing `ZBKCOLLECTION.Z_PK` (create a row in
  `ZBKCOLLECTION` first if it's a new Collection).
- Books.app is CoreData-backed — also need to maintain
  `Z_PRIMARYKEY.Z_MAX` and set `ZMODIFICATIONDATE` /
  `ZSYNCHRONIZATIONSTATE` so iCloud doesn't treat the change as stale.
- Must be done with **Books.app quit** to avoid corrupting the CoreData
  cache vs. on-disk store.
- **iCloud clobber risk**: if iCloud Books sync is on, the cloud state may
  win and erase the local edit; no public endpoint to push up.

Doable if the user accepts "quit Books → edit SQLite → reopen" as a flow,
but clearly experimental. UI-driving via Accessibility is an alternative
but Books's Collection sidebar is even more hostile to AX than Kindle's
library.

## 3. Yomu — unsupported, CoreData-fragile

Current read path: `ZDOCUMENT` ⋈ `Z_4TAGS` ⋈ `ZTAG` (`get_yomu` query,
lines ~177–206).

Same class of problem as Apple Books: CoreData app, no public API, no URL
scheme for tagging.

Direct SQLite write path:

1. Quit Yomu.
2. `INSERT OR IGNORE INTO ZTAG (Z_ENT, Z_OPT, ZNAME) VALUES (<ZTAG-entity-id>, 1, 'mytag')`
   — entity id from `Z_PRIMARYKEY`.
3. `INSERT INTO Z_4TAGS (Z_4DOCUMENTS, Z_9TAGS) VALUES (<doc_pk>, <tag_pk>)`
   — the Z_4 / Z_9 numbers are entity IDs and can drift across Yomu
   versions; they're hardcoded in the current read query. They'd need to
   be discovered dynamically from `Z_PRIMARYKEY` / `sqlite_master`.
4. Bump `Z_PRIMARYKEY.Z_MAX` for the tag entity.
5. Optionally bump `ZDOCUMENT.ZMODIFIED` so Yomu re-indexes.

Feasible with a backup-before-write step, but inherently brittle against
Yomu schema changes (same class of fragility the README already flags for
the Kindle Lassen hack).

## 4. Kindle (Classic + new Lassen app) — not feasible locally

We currently surface **no** tag for Kindle — neither `get_kindleClassic`
(XML dump) nor `get_kindle` (KSDK `ZBOOK`) reads a tag/collection column.
That's because:

- Amazon's "Collections" live server-side on the Amazon account and sync
  read-only down to devices. The local KSDK SQLite has no writable
  Collection table.
- No public Amazon API for managing Kindle Collections from a third-party
  app. The only surface is `read.amazon.com/notebook` /
  `read.amazon.com/kindle-library` behind logged-in browser cookies.
  Reverse-engineering that plus handling auth (incl. 2FA) from an Alfred
  workflow is out of scope and would break on Amazon's next endpoint
  change.
- Faking it locally (extra column in a sidecar file) wouldn't be visible
  to the Kindle app — but it *would* still be searchable inside Alfred
  via the existing `--tag` operator. That may actually be the pragmatic
  fallback (see below).

## Pragmatic recommendation

For a single "tag this book from Alfred" action with consistent UX across
all four sources:

- **Calibre** — real write via `calibredb set_metadata`.
- **Apple Books / Yomu** — real SQLite write behind an opt-in workflow
  config (`Allow direct DB writes`), with the app-must-be-quit
  precondition enforced and a `.bak` copy taken first.
- **Kindle** — workflow-local sidecar tag store (JSON keyed by ASIN)
  merged into `Book.tags` at read time in `get_kindle*`. The tag lives
  only inside Alfred but is still filterable via `--tag`. Honest about
  what's possible; no pretense of pushing to Amazon.

### Suggested phasing

1. **Phase 1** — Calibre only. Small (~30 LoC), supported path,
   validates the Alfred UX (keyword, modifier, tag-picker vs. free-text).
2. **Phase 2** — Kindle sidecar. No external dependencies; proves the
   merge-at-read pattern.
3. **Phase 3** — Apple Books / Yomu direct writes, gated behind a config
   flag and with automatic `.bak` rotation. Ship with a clear
   "experimental" label in `README.md`, similar to the Lassen warning.

## Open questions

- Alfred UX: single free-text tag entry, or a two-step (pick book → pick
  from existing tags + "new…")?
- Should setting a tag in Alfred auto-refresh the affected source's
  pickle, or require `::books-refresh`?
- For Kindle sidecar tags: stored alongside existing pickles in the
  workflow cache, or in a user-editable file in the workflow data dir so
  they survive re-installs?
