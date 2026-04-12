# What's New: dev vs main (v0.2)

## Overview

The `dev` branch introduces a major expansion of the alfred-kindle workflow, transforming it from a book library browser into a full-featured **eBook research tool** with full-text search capabilities across EPUB libraries.

---

## New Features

### 1. Full-Text EPUB Search Engine (`searchEPUB.py`)

The biggest addition: a ~1,340-line standalone search engine that searches the **actual text content** of EPUB files, not just metadata.

- Searches across an entire folder of EPUBs or a single book
- Case-insensitive matching with context snippets
- Handles both standard `.epub` zip files and `.epub` directory bundles (as used by macOS Books app)
- TOC-aware: identifies which chapter each match comes from

### 2. Proximity Search

When a query has exactly two words (e.g., `"love death"`), the engine automatically switches to **proximity search mode**, finding passages where both words appear within a configurable distance.

- Default distance: 100 words
- Configurable via `--proximity=N`
- Distance semantics: 25 = same paragraph, 50 = nearby, 100 = same section, 200 = same chapter
- Results show `word1 ... word2 (N words apart)`

### 3. Alfred-Native Progressive Search

EPUB search is integrated into Alfred's UI with a progressive, stateful workflow:

- Uses Alfred's `rerun` mechanism to process one book per execution cycle
- Real-time progress bars: `(15/47) |-----x----------|`
- Persistent state via temp files across rerun invocations
- **Drill-down UI**: first shows a book overview (one row per book with match counts), then lets you drill into individual matches within a specific book
- Stable UIDs for consistent Alfred selection behavior

### 4. Report Generation

Search results can be exported in two formats:

- **Markdown reports**: formatted with matches grouped by book, context snippets, bold-highlighted search terms, and chapter attribution
- **Modified EPUB files** (`--epub` flag): generates new EPUB files with yellow-highlighted search terms and an injected search results index chapter

### 5. Improved Cover Image Extraction

The `fetchImageCover()` function in `kindle_fun.py` was significantly expanded (from ~10 lines to ~150 lines):

- **Before (main)**: only checked for `cover.jpeg` in the EPUB root directory
- **After (dev)**: parses OPF manifests to locate cover images, handles both zip and directory EPUB formats, tries multiple cover naming conventions (`cover.jpeg`, `cover.jpg`, `cover.png`, `cover.gif`), and searches manifest metadata for cover-tagged items

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
| `source/searchEPUB.py` | Full-text EPUB search engine (1,340 lines) |
| `source/DEPENDENCY_FIX.md` | Documents lxml/Python version mismatch fix for Alfred's system Python |
| `source/test_dependencies.py` | Validates all imports work under Alfred's Python 3.9.6 |
| `troubleshooting/README.md` | Full documentation for searchEPUB.py |
| `troubleshooting/CHANGELOG.md` | Version 1.0.0 release notes |
| `troubleshooting/CACHING_USAGE.md` | Caching system docs for library statistics |
| `troubleshooting/PROXIMITY_SEARCH_USAGE.md` | Proximity search usage guide |
| `troubleshooting/QUICK_REFERENCE.md` | Quick reference/cheat sheet for searchEPUB.py |
| `troubleshooting/createStats.py` | EPUB library statistics generator with JSON-based caching |
| `troubleshooting/*.py` | Various test and utility scripts |

### Removed Files
- Several ChatGPT-generated images removed from `images/` (cleanup of unused assets)

### Modified Files
- `source/kindle_fun.py` — expanded cover image extraction (+160 lines)
- `source/info.plist` — updated Alfred workflow configuration (+387 lines, adds searchEPUB integration)
- `source/requirements.txt` — 3 new dependencies added
- `.gitignore` — updated

---

## Planned / Future Enhancements (from CHANGELOG.md)

- Fuzzy matching
- Regular expression support
- CSV/JSON output formats
- Parallel processing for large libraries
- Built-in caching for search results
