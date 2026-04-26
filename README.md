# alfred-eBooks📚


### List, search, and open your Kindle, Apple Books, Yomu, and Calibre ebooks with [Alfred 5](https://www.alfredapp.com/) 



<a href="https://github.com/giovannicoppola/alfred-kindle/releases/latest/">
<img alt="Downloads"
src="https://img.shields.io/github/downloads/giovannicoppola/alfred-kindle/total?color=purple&label=Downloads"><br/>
</a>

![](images/kindle.png)


<!-- MarkdownTOC autolink="true" bracket="round" depth="3" autoanchor="true" -->

- [What's new](#whats-new)
- [Motivation](#motivation)
- [Setting up](#setting-up)
- [Basic Usage](#usage)
- [Known Issues](#known-issues)
- [Acknowledgments](#acknowledgments)
- [Changelog](#changelog)
- [Feedback](#feedback)

<!-- /MarkdownTOC -->



<h1 id="whats-new">What's new ✨</h1>

### Version 0.3

- **Typing guard for library-wide search** — `!!ksearch` no longer fires an expensive full-library scan on every keystroke. Instead it shows a mirror row reflecting your query, with cached searches listed below. Press ↵ to confirm, and a live progress bar tracks the scan. Cached searches are directly actionable — press ↵ to reopen their results instantly.
- **Live progress bar via fresh-session reopen** — when a search is confirmed, the workflow spawns a background worker and reopens Alfred as a fresh session so the progress bar updates in real time (workaround for Alfred's `rerun` limitation with text in the search box).
- **Improved progress grammar** — progress text now correctly says "1 match in 1 book" instead of "1 matches in 0 books".
- **Graceful handling of missing resources** — if a user enables a library source (Kindle, Apple Books, Yomu, Calibre) that isn't installed, the workflow logs a clear message and skips it instead of crashing.
- **`⌃` modifier shows searchability** — holding ctrl on any book row now shows whether full-text search is available for that book, with a specific reason when it isn't (e.g. "Kindle books aren't searchable locally", "the .epub file isn't on disk").
- **Multi-book search drill-down** — folder-wide EPUB searches now show a book overview sorted by match count; pressing ↩ on a book drills into its individual matches instantly (served from cache, no re-scanning).
- **Search result caching** — full-text search results are persisted on disk and reused for the configurable cache duration (default: 11 days). Repeat searches return instantly. Cache duration is adjustable in Workflow Configuration → "Search cache duration (days)".
- **Overlapping search results merged** — nearby matches in the same chapter are merged into a single result row with all occurrences highlighted, instead of showing near-duplicate rows.
- **Longer search excerpts** — subtitle context for search matches doubled from 80 to 160 characters.
- **Singular/plural "word apart"** — proximity search now correctly says "1 word apart" instead of "1 words apart".
- **Improved highlight QuickLook cards** — the font cascade now prefers Georgia over New York for better readability and correct em-dash rendering on all Macs. Existing cards are automatically re-rendered.
- **Cleaner highlight modifiers** — `⌘↩` on any highlight row copies the passage to the clipboard; the old `⌥` fallback that pasted text into the Alfred query box is gone.
- **Streamlined book-row modifiers** — the CMD modifier no longer shows the internal icon path.
- **Thousand separators in match counts** — search results now display "1,234 matches" instead of "1234 matches" for easier scanning.
- **Improved cover image extraction** — downloaded and EPUB-extracted covers are now validated against JPEG/PNG magic bytes; corrupted or DRM-encrypted images are discarded and the workflow falls back to Apple Books' own `BCCoverCache` (HEIC → JPEG via `sips`), recovering covers that were previously missing.
- **`#` tag shorthand** — type `#` to instantly list all available tags; keep typing to filter (e.g. `#bio`). Press ↩ to select a tag and continue your search. Multiple tags can be stacked (`#sci-fi #favorite`) and combined with other operators (`#sci-fi --highlights stoic`). The existing `--tag` syntax still works.

### Version 0.2

Highlights of the v0.2 dev-branch work (full details in [whatsnew.md](whatsnew.md)):

- **Open a specific book in the new Kindle for Mac app (Lassen)** — previously the workflow could only foreground the app; now ↩️ on a Kindle book opens that exact book via UI automation. *Hacky and fragile* (driven by mouse moves, clicks, and keystrokes — see the [Limitations](#known-issues) section), but it works today.
- **Full-text EPUB search engine** with a 1,340-line standalone search engine, proximity search for two-word queries, an Alfred-native progressive UI, and Markdown / annotated-EPUB report generation.
- **Cross-library highlights & notes** — every highlight (and user note) from Apple Books, Calibre, Yomu, and Kindle is surfaced in search results (subtitle chip `💬 N`). `⌥↩` on a book drills into its highlights; `--highlights` searches highlights across your whole library; `⇧` / `Y` QuickLooks a typeset card of the highlight; `⌃↩` on a highlight runs full-text search in that book.
- **Tags / Collections** — Apple Books user Collections, Calibre tags, and Yomu tags are surfaced in the subtitle (`🏷️`) and are searchable via new `--tag <name>` / `--tagged` operators and two new `SEARCH_SCOPE` values (`Tags`, `All`).
- **Improved cover-image extraction** for EPUBs (parses OPF manifests, handles zip and directory bundles, tries multiple cover naming conventions).



<h1 id="motivation">Motivation ✅</h1>

- Quickly list, search, and open your Kindle, Apple Books, Yomu, and Calibre ebooks


<h1 id="setting-up">Setting up ⚙️</h1>

- Alfred 5 with Powerpack license
- Python3 (howto [here](https://www.freecodecamp.org/news/python-version-on-mac-update/))
- Kindle, Apple Books, Yomu, or Calibre installed
- Download `alfred-eBooks` [latest release](https://github.com/giovannicoppola/alfred-kindle/releases/latest)



## Default settings 
- In Alfred, open the 'Configure Workflow' menu in `alfred-eBooks` preferences
	- set the keyword for the workflow (default: `!k`)
	- set the keyword to force an update (default: `::books-refresh`)
	- set the book content icon, i.e. if a book has been downloaded locally (default: 📘)
	- set the 'ghost' book icon, i.e. if a book has not been downloaded or previously loaned (default: 👻)
	- show 'ghost' books (i.e. books not downloaded, or previously loaned)? (default: yes)
	- set target libraries (Kindle, Apple Books, Yomu, and/or Calibre)
	- set `Calibre library path` if your library is not at `~/Calibre Library`
	- set `Calibre metadata DB path` to override auto-detection (optional)

	_Note: `alfred-eBooks` will search for Kindle Classic and the (new) Kindle app. If both are installed, the latter with be used._
	- set search scope (default: 'Title')
		- `Title`: search titles only
		- `Author`: search authors only
		- `Both`: search across titles and authors
		- `Tags`: search tags / Apple Books Collections / Calibre tags / Yomu tags only
		- `All`: search titles, authors, and tags


<h1 id="usage">Basic Usage 📖</h1>

- launch with keyword (default: `!k`), or custom hotkey
- enter a string to search, according to the scope set in `Workflow Configuration`. A few search operators are available:
	- `--p` will filter for purchased books
	- `--l` will filter for loaned books
	- `--d` will filter for downloaded books
	- `--k` will filter for Kindle books
	- `--ib` will filter for Apple Books books
	- `--c` will filter for Calibre books
	- `--read` will filter for read books
	- `--tagged` will filter for books that have at least one tag
	- `#` lists all available tags; keep typing to filter (e.g. `#bio`). Press ↩ to select a tag and continue searching. Multiple tags can be combined (e.g. `#sci-fi #favorite`), and tags stack with other filters (e.g. `#sci-fi --highlights stoic`). Multi-word tags are parenthesized automatically: `#(Want to Read)`.
	- `--tag <name>` is the long-form equivalent of `#<name>` — narrows to books whose tags match `<name>` (substring, case-insensitive). Can be combined, e.g. `--tag sci-fi --tag favorite`. For multi-word tags, wrap the name in parentheses: `--tag (home improvement)`.
	- `--highlights` switches into cross-library highlight search. Bare `--highlights` shows a summary (per-source counts + top books by highlight count). `--highlights <words>` returns a flat list of highlights whose text / note matches. Combine with a source filter, e.g. `--ib --highlights solitude`
- tags / collections are surfaced in the subtitle (🏷️) and come from:
	- **Apple Books** user Collections (e.g. "Want to Read", "Finished", and any custom collections you've created)
	- **Calibre** tags (the `tags` column from `metadata.db`)
	- **Yomu** tags
- highlights are surfaced in the subtitle (💬 N) when a book has any. Sources:
	- **Apple Books**: full highlight text, user notes, and location (from `AEAnnotation/*.sqlite`)
	- **Calibre**: full highlight text + notes for books opened in Calibre's Viewer (from the `annotations` table in `metadata.db`)
	- **Yomu**: full highlight text + notes (from `ZANNOTATION`)
	- **Kindle**: counts + user-typed notes only — Amazon strips the highlighted passage text from local storage. Selecting a Kindle highlight opens `https://read.amazon.com/notebook?asin=<ASIN>` where the text lives.
- on a **book row** with highlights:
	- `⌥↩` re-enters the workflow in drill-down mode: one highlight per Alfred row, full passage text as the title, location / date / note in the subtitle. Start typing after the operator to substring-filter that book's highlights in place.
- on a **highlight row**:
	- `↩` opens the book (Apple Books deep-link, Calibre Viewer at CFI, Yomu by document id, Kindle cloud notebook)
	- `⌘↩` copies just that highlight's text
	- `⌃↩` runs full-text search in the book that owns the highlight (EPUB-backed sources)
	- `⇧` or `Y` triggers Alfred's QuickLook preview, which renders the highlight as a typeset card (Newsreader Medium, auto-fit height). Cards are cached on disk and re-rendered when the source text changes.
- `enter` ↩️ will open the selected result in its source app (Kindle, Apple Books, Yomu, or Calibre)
- `cmd+enter` on a book result runs full-text search in that book (when supported)
- on match rows:
	- `enter` ↩️ opens the markdown/context view
	- `shift+enter` ↩️ opens the book at the matched chapter/location (Calibre)
- data is automatically cached for best performance. You can force a database refresh using the keyword `::books-refresh`



<h1 id="known-issues">Limitations & known issues ⚠️</h1>

- **Opening a specific book in the new Kindle for Mac app (Lassen) is hacky and fragile.** Lassen exposes no way to deep-link to a book from outside: no supported URL scheme opens a book, there's no AppleScript dictionary, and Catalyst hides the view hierarchy from the Accessibility API so covers can't be targeted by AX role/label. ↩️ works around this by **driving the UI as if a human were doing it** — moving the mouse, clicking, typing — which is inherently brittle and will likely break on Kindle UI updates, layout changes, screen resolution differences, or anything that perturbs timing. The sequence: Kindle is foregrounded, then the AX tree is walked to detect whether we're on the library (any `AXTextField` is exposed) or in reader view (only opaque `AXGroup`s and window chrome); if we're in reader view, the script slides the cursor into the auto-hiding top toolbar and clicks the back-arrow at its left edge to return to the library; the search text field is then clicked at its AX-reported center to focus it (Cmd+F doesn't refocus once the library is in search-results sub-state, and Catalyst ignores AX SetFocused); the existing query is cleared with Cmd+A + Delete, the book title is typed, Return filters the library to that book, and a Quartz-posted double-click on the first grid cell opens it. This requires granting **Accessibility permission to Alfred** in *System Settings → Privacy & Security → Accessibility*. Caveats: the back-arrow is clicked at `(winX+30, winY+55)` and the book-cell double-click at `(30%, 22%)` of the window — both are layout-dependent heuristics; tweak them in `kindle-lassen-open.sh` if they miss on your setup. The fully-rendered library window must be reachable from the current Kindle state for the workaround to work.
- I could not figure out how the Kindle app can tell if a book was first loaned, then purchased. Currently, if that is the case (i.e. a book was first loaned, then purchased), the book will appear as loaned.
- Full-text book search only works on **DRM-free EPUBs** (also called "unencrypted" or "open" EPUBs). Amazon Kindle books are proprietary AZW3/KFX and always DRM-protected; Apple Books purchased from the iBooks Store are typically wrapped in FairPlay DRM. Those can still be listed, opened, and have their highlights surfaced — but `ebooklib` cannot parse the encrypted container, so search-inside-book and the EPUB report generator skip them. In practice the searchable pool is: Calibre library EPUBs, Yomu EPUBs, and any EPUBs you sideloaded into Apple Books or Calibre yourself. MOBI / AZW3 / PDF are unsupported regardless of DRM status.
- For Calibre match opens, EPUBs are reflowable, so jumping is chapter/locator based rather than fixed "page number" precise.
- not tested thoroughly for user-uploaded documents.



<h1 id="acknowledgments">Acknowledgments 😀</h1>

- Thanks to the [Alfred forum](https://www.alfredforum.com) community!
- Icon from [SF symbols](https://developer.apple.com/sf-symbols/)

<h1 id="changelog">Changelog 🧰</h1>

- 04-23-2026: version 0.3: typing guard, live progress bar, search caching, drill-down, graceful error handling
- 10-07-2024: version 0.2: from kindle to eBooks
- 02-28-2023: version 0.1


<h1 id="feedback">Feedback 🧐</h1>

Feedback welcome! If you notice a bug, or have ideas for new features, please feel free to get in touch either here, or on the [Alfred](https://www.alfredforum.com) forum. 
