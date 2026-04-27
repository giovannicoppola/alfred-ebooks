# What's New: dev vs main (v0.2)

## Overview

The `dev` branch transforms the alfred-kindle workflow from a Kindle-only book library browser into a full-featured **eBook research tool** supporting Kindle, Apple Books, Yomu, and Calibre, with full-text EPUB search, cross-library highlights, and tag-based filtering.

---

## New Features

### Yomu and Calibre support

Books, highlights, and tags from Yomu and Calibre are now surfaced alongside Kindle and Apple Books. Each source can be individually toggled in Workflow Configuration (`USE_YOMU`, `USE_CALIBRE`).

### Tags / Collections

Tags are extracted from every source that supports them and stored in a `Book.tags` field:

- **Apple Books** user Collections (e.g. "Want to Read", "Finished", custom collections). Auto-managed shelves (All, Books, PDFs, etc.) are filtered out.
- **Calibre** tags from `metadata.db`.
- **Yomu** tags from the CoreData link table.

UI / filter additions:

- Tags render in each Alfred item's subtitle as `🏷️ tag, tag, tag`.
- `#` **tag shorthand**: type `#` to instantly list all available tags; keep typing to filter (e.g. `#bio`). Press ↩ to select and continue searching. Multiple tags stack (`#sci-fi #favorite`) and combine with other operators (`#sci-fi --highlights stoic`). Multi-word tags are parenthesized automatically: `#(Want to Read)`.
- `--tag <name>` long-form equivalent, stackable, substring case-insensitive.
- `--tagged` keeps only books with at least one tag.
- `SEARCH_SCOPE` gains two new values: `Tags` (search tags only) and `All` (title + author + tags).

### Highlights & notes

Each book carries a `highlights_count` integer. Highlights live in per-source pickles (`*_highlights_v1.pkl`), rebuilt on the same mtime trigger as books.

Sources:

- **Apple Books**: full highlight text, user note, CFI locator, style/color, timestamps. Deep-links via `ibooks://assetid/<id>`.
- **Calibre**: full highlight text + notes from the `annotations` table (Calibre 5+).
- **Yomu**: full highlight text + notes from `ZANNOTATION`.
- **Kindle**: counts + user-typed NOTE text only — Amazon does not store highlight passage text locally. Opens `https://read.amazon.com/notebook?asin=<ASIN>`.

UI / filter additions:

- Subtitle chip `💬 N` on every book with highlights.
- `--highlights` operator for cross-library highlight search. Bare `--highlights` shows a summary + top books by count. `--highlights <words>` returns matching highlights. Source filters compose: `--ib --highlights stoic`.
- **`--highlights` summary books** behave like regular book rows: ↩ opens the book, ⌃↩ searches inside it, ⌥↩ drills into highlights.
- **Per-book drill-down** via `⌥↩` on any book row — one highlight per Alfred row, full passage text as title, location/date/note in subtitle. Typing filters in place.
- Highlight row modifiers: `↩` opens the book, `⌘↩` copies text, `⌃↩` searches the owning book (EPUB sources), `⇧↩` opens the book.
- `⇧`/`Y` QuickLook preview renders the highlight as a typeset card (Newsreader Medium, auto-fit height, cached on disk, re-rendered when text changes).

### Open a specific book in the new Kindle for Mac app (Lassen)

Lassen exposes no deep-link, AppleScript dictionary, or AX-targetable book covers. `kindle-lassen-open.sh` drives the UI via accessibility: walks the AX tree to detect library vs reader view, clicks the back-arrow toolbar, focuses the search field, types the title, and double-clicks the first grid cell. Inherently hacky and fragile. Requires Accessibility permission for Alfred.

The sequence: Kindle is foregrounded, then the AX tree is walked to detect whether we're on the library (any `AXTextField` is exposed) or in reader view (only opaque `AXGroup`s and window chrome); if we're in reader view, the script slides the cursor into the auto-hiding top toolbar and clicks the back-arrow at its left edge to return to the library; the search text field is then clicked at its AX-reported center to focus it (Cmd+F doesn't refocus once the library is in search-results sub-state, and Catalyst ignores AX SetFocused); the existing query is cleared with Cmd+A + Delete, the book title is typed, Return filters the library to that book, and a Quartz-posted double-click on the first grid cell opens it. This requires granting **Accessibility permission to Alfred** in *System Settings → Privacy & Security → Accessibility*. Caveats: the back-arrow is clicked at `(winX+30, winY+55)` and the book-cell double-click at `(30%, 22%)` of the window — both are layout-dependent heuristics; tweak them in `kindle-lassen-open.sh` if they miss on your setup. The fully-rendered library window must be reachable from the current Kindle state for the workaround to work.

### Full-text EPUB search engine (`searchEPUB.py`)

A standalone search engine that searches the actual text content of EPUB files:

- Searches an entire folder of EPUBs or a single book
- Case-insensitive matching with context snippets
- Handles both standard `.epub` zip files and directory bundles (macOS Books)
- TOC-aware: identifies which chapter each match comes from
- **Proximity search**: two-word queries automatically find passages where both words appear within a configurable distance (default: 100 words)
- **Report generation**: Markdown reports and modified EPUB files with highlighted search terms

### Library-wide search UX

- **Typing guard** for `!!ksearch` — no longer fires an expensive scan on every keystroke. Shows a mirror row reflecting the query, with cached searches listed below. Press ↩ to confirm.
- **Live progress bar** via background worker + AppleScript fresh-session reopen (workaround for Alfred's `rerun` limitation with text in the search box). Progress shows match count, book count, and current book being searched. "You can close Alfred and check back later" message.
- **Search result caching** — results persisted on disk, reused for configurable cache duration (default: 11 days). Repeat searches return instantly. Cached searches are directly actionable from the `!!ksearch` overview.
- **Cache deletion** via `⌘⌥⌃↩` on cached search rows.
- **Multi-book drill-down** — folder-wide searches show a book overview sorted by match count; ↩ on a book drills into its individual matches (served from cache).
- **Overlapping search results merged** — nearby matches in the same chapter are combined into a single row with all occurrences highlighted.
- **Match row modifiers**: `⌘↩` copies to clipboard, `⇧↩` opens the book (with chapter location for Calibre), ↩ opens the markdown/context view.
- **Back button** (`⌘⌥↩`) on all-library search result screens (summary, book rows, no-results, cached results) to return to the search interface.

### Improved cover image extraction

- Downloaded and EPUB-extracted covers are validated against JPEG/PNG magic bytes.
- Corrupted or DRM-encrypted images are discarded.
- **BCCoverCache fallback**: when Apple Books encrypts the EPUB cover, the workflow reads Apple Books' own `BCCoverCache` (unencrypted HEIC thumbnails) and converts to JPEG via `sips`.
- OPF manifest parsing for cover discovery (handles `<meta name="cover">` metadata and manifest items with "cover" in their id/href).

---

## Smaller fixes and polish

- **Graceful handling of missing resources** — if a library source isn't installed, the workflow logs a message and skips it instead of crashing.
- **`⌃` modifier on book rows** shows whether full-text search is available, with a specific reason when it isn't.
- **Longer search excerpts** — subtitle context for search matches doubled from 80 to 160 characters.
- **Correct singular/plural grammar** — "1 match in 1 book", "1 word apart", etc.
- **Thousand separators** in match counts (e.g. "1,234 matches").
- **Bold highlight spacing** — space padding around `**` markers for Alfred markdown rendering.
- **Book titles resolved from EPUB metadata** instead of hex filenames.
- **Clean search box** — delete-cache and confirmation prefixes no longer leak text into Alfred's search box.
- **Highlight QuickLook cards** prefer Georgia over New York for better em-dash rendering.
- **`⌘↩` on highlight rows** copies the passage; the old `⌥` paste-into-query fallback is removed.
- **Streamlined book-row CMD modifier** — no longer shows the internal icon path.

---

## New Dependencies

| Package | Version | Purpose |
|---|---|---|
| `docopt` | 0.6.2 | CLI argument parsing for searchEPUB.py |
| `ebooklib` | 0.19 | EPUB reading/writing |
| `beautifulsoup4` | 4.13.5 | HTML parsing within EPUBs |
| `lxml` | (transitive) | Required by ebooklib |

Existing dependencies (`requests`, `xmltodict`, `biplist`) remain unchanged.

---

## Structural Changes

### New Files
| File | Purpose |
|---|---|
| `source/searchEPUB.py` | Full-text EPUB search engine |
| `source/deleteSearchCache.py` | Delete cached EPUB search artifacts |
| `source/highlight_images.py` | QuickLook JPG renderer for highlights |
| `source/kindle-lassen-open.sh` | UI-automation opener for new Kindle app |

### Modified Files
- `source/kindle_fun.py` — expanded cover image extraction, BCCoverCache fallback, image validation
- `source/kindle-query.py` — tags, highlights, `#` tag shorthand, drill-down, `--highlights` search
- `source/config.py` — new pickle paths, highlight config, Yomu/Calibre defaults
- `source/info.plist` — updated Alfred workflow graph (searchEPUB integration, modifiers, external triggers)
- `source/requirements.txt` — new dependencies
- `README.md` — updated usage docs, What's New section

### Cache versioning
- Book pickles: `*_v3.pkl` (v2 added tags, v3 added highlights_count)
- Highlight pickles: `*_highlights_v1.pkl`
- Highlight render version: `v3` (v1 initial, v2 Newsreader font + auto-height, v3 Georgia preference)
