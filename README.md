# alfred-eBooks📚


### List, search, and open your eBooks with [Alfred 5](https://www.alfredapp.com/) 



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

### Version 0.3 (full details in [whatsnew.md](whatsnew.md)):

- **Added support for Yomu, Calibre**
- **Book- and Library-wide text search** — for searchable EPUBs 
- **Library-wide search result caching** — full-text search results are persisted on disk and reused for the configurable cache duration (default: 11 days).
- **Tags / Collections** — Apple Books user Collections, Calibre tags, and Yomu tags are surfaced in the subtitle (`🏷️`) and are searchable via new `--tag <name>` or `--tagged` operators.
- **Cross-library highlights & notes** — every highlight (and user note) from Apple Books, Calibre, Yomu, and Kindle is surfaced in search results (subtitle chip `💬 N`). `--highlights` searches books with highlights across your whole library.
- **Highlight QuickLook typeset cards**
- **Improved cover-image extraction** for EPUBs.



<h1 id="motivation">Motivation ✅</h1>

-Quickly list, search, and open your Kindle/Apple Books/Yomu/Calibre libraries


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
		- `Title + Author`: search across titles and authors
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
	- `--y` will filter for Yomu books
	- `--read` will filter for read books
	- `--tagged` will filter for books that have at least one tag
	- `#` lists all available tags; keep typing to filter (e.g. `#bio`). Press ↩ to select a tag and continue searching. Multiple tags can be combined (e.g. `#sci-fi #favorite`), and tags stack with other filters (e.g. `#sci-fi --highlights stoic`). Multi-word tags are parenthesized automatically: `#(Want to Read)`.
	- `--tag <name>` is the long-form equivalent of `#<name>` — narrows to books whose tags match `<name>` (substring, case-insensitive). Can be combined, e.g. `--tag sci-fi --tag favorite`. 
	- `--highlights` switches into cross-library highlight search. Bare `--highlights` shows a summary (per-source counts + top books by highlight count). `--highlights <words>` returns a flat list of highlights whose text / note matches. Combine with a source filter, e.g. `--ib --highlights solitude`
- tags / collections are surfaced in the subtitle (🏷️) and come from:
	- **Apple Books** user Collections (e.g. "Want to Read", "Finished", and any custom collections you've created)
	- **Calibre** tags 
	- **Yomu** tags
- highlights are surfaced in the subtitle (💬 N) when a book has any. Sources:
	- **Apple Books**: full highlight text, user notes, and location 
	- **Calibre**: full highlight text + notes for books opened in Calibre's Viewer 
	- **Yomu**: full highlight text + notes 
	- **Kindle**: counts + user-typed notes only — Amazon strips the highlighted passage text from local storage. Selecting a Kindle highlight opens `https://read.amazon.com/notebook?asin=<ASIN>` where the text lives.
- on a **book row** with highlights:
	- `⌥↩` re-enters the workflow in drill-down mode: one highlight per Alfred row, full passage text as the title, location / date / note in the subtitle. 
- on a **highlight row**:
	- `↩` opens the book (Apple Books deep-link, Calibre Viewer at CFI, Yomu by document id, Kindle cloud notebook)
	- `⌘↩` copies just that highlight's text
	- `⌃↩` runs full-text search in the book that owns the highlight (EPUB-backed sources)
	- `⇧` or `Y` triggers Alfred's QuickLook preview, which renders the highlight as a typeset card . Cards are cached on disk and re-rendered when the source text changes.
- `enter` ↩️ will open the selected result in its source app (Kindle, Apple Books, Yomu, or Calibre)
- `cmd+enter` on a book result runs full-text search in that book (when supported)
- on match rows:
	- `enter` ↩️ opens the markdown/context view
	- `shift+enter` ↩️ opens the book at the matched chapter/location (Calibre)
- data is automatically cached for best performance. You can force a database refresh using the keyword `::books-refresh`

## Library-wide full-text search

Use the `!!ksearch` keyword to search the full text of all DRM-free EPUBs across your libraries (Apple Books, Calibre, Yomu). Type your query and press ↩ to confirm — a background worker scans every book while a live progress bar tracks matches and books searched. You can close Alfred and come back later; a macOS notification fires when the scan finishes.

- **Single-book search**: `⌘↩` on any book row (or `⌃↩` on a highlight row) searches inside that specific book.
- **Proximity search**: two-word queries automatically find passages where both words appear near each other (default: within 100 words).
- **Result caching**: searches are cached on disk (default: 11 days). Repeat searches return instantly from the `!!ksearch` overview.
- **Drill-down**: library-wide results show a book overview sorted by match count; press ↩ on a book to drill into its individual matches.
- **Match modifiers**: `⌘↩` copies the match context, `⇧↩` opens the book (at the chapter location for Calibre).
- Only **DRM-free EPUBs** are searchable. Kindle books (AZW3/KFX), FairPlay-protected Apple Books purchases, and PDF/MOBI are not supported.



<h1 id="known-issues">Limitations & known issues ⚠️</h1>

- **Opening a specific book in the new Kindle for Mac app (Lassen) is hacky and fragile.** Lassen exposes no way to deep-link to a book from outside: no supported URL scheme opens a book, there's no AppleScript dictionary, and Catalyst hides the view hierarchy from the Accessibility API so covers can't be targeted by AX role/label. ↩️ works around this by **driving the UI as if a human were doing it** — moving the mouse, clicking, typing — which is inherently brittle and will likely break on Kindle UI updates, layout changes, screen resolution differences, or anything that perturbs timing. 
- I could not figure out how the Kindle app can tell if a book was first loaned, then purchased. Currently, if that is the case (i.e. a book was first loaned, then purchased), the book will appear as loaned.
- Full-text book search only works on **DRM-free EPUBs** (also called "unencrypted" or "open" EPUBs). Amazon Kindle books are proprietary AZW3/KFX and always DRM-protected; Apple Books purchased from the iBooks Store are typically wrapped in FairPlay DRM. Those can still be listed, opened, and have their highlights surfaced — but `ebooklib` cannot parse the encrypted container, so search-inside-book and the EPUB report generator skip them. In practice the searchable pool is: Calibre library EPUBs, Yomu EPUBs, and any EPUBs you sideloaded into Apple Books or Calibre yourself. MOBI / AZW3 / PDF are unsupported regardless of DRM status.
- For Calibre match opens, EPUBs are reflowable, so jumping is chapter/locator based rather than fixed "page number" precise.
- not tested thoroughly for user-uploaded documents.



<h1 id="acknowledgments">Acknowledgments 😀</h1>

- Thanks to the [Alfred forum](https://www.alfredforum.com) community!
- Icon from [SF symbols](https://developer.apple.com/sf-symbols/)
- Updated with substantial help from Claude Code and Cursor

<h1 id="changelog">Changelog 🧰</h1>

- 04-27-2026: version 0.3: book search, library search, highlights, additional readers supported
- 10-07-2024: version 0.2: from kindle to eBooks
- 02-28-2023: version 0.1


<h1 id="feedback">Feedback 🧐</h1>

Feedback welcome! If you notice a bug, or have ideas for new features, please feel free to get in touch either here, or on the [Alfred](https://www.alfredforum.com) forum. 
