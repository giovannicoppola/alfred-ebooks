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

Highlights of the latest dev-branch work (full details in [whatsnew.md](whatsnew.md)):

- **Open a specific book in the new Kindle for Mac app (Lassen)** — previously the workflow could only foreground the app; now ↩️ on a Kindle book opens that exact book via UI automation. *Hacky and fragile* (driven by mouse moves, clicks, and keystrokes — see the [Limitations](#known-issues) section), but it works today.
- **Full-text EPUB search engine** with a 1,340-line standalone search engine, proximity search for two-word queries, an Alfred-native progressive UI, and Markdown / annotated-EPUB report generation.
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
- `enter` ↩️ will open the selected result in its source app (Kindle, Apple Books, Yomu, or Calibre)
- `cmd+enter` on a book result runs full-text search in that book (when supported)
- on match rows:
	- `enter` ↩️ opens the markdown/context view
	- `shift+enter` ↩️ opens the book at the matched chapter/location (Calibre)
- data is automatically cached for best performance. You can force a database refresh using the keyword `::books-refresh`



<h1 id="known-issues">Limitations & known issues ⚠️</h1>

- **Opening a specific book in the new Kindle for Mac app (Lassen) is hacky and fragile.** Lassen exposes no way to deep-link to a book from outside: no supported URL scheme opens a book, there's no AppleScript dictionary, and Catalyst hides the view hierarchy from the Accessibility API so covers can't be targeted by AX role/label. ↩️ works around this by **driving the UI as if a human were doing it** — moving the mouse, clicking, typing — which is inherently brittle and will likely break on Kindle UI updates, layout changes, screen resolution differences, or anything that perturbs timing. The sequence: Kindle is foregrounded, then the AX tree is walked to detect whether we're on the library (any `AXTextField` is exposed) or in reader view (only opaque `AXGroup`s and window chrome); if we're in reader view, the script slides the cursor into the auto-hiding top toolbar and clicks the back-arrow at its left edge to return to the library; the search text field is then clicked at its AX-reported center to focus it (Cmd+F doesn't refocus once the library is in search-results sub-state, and Catalyst ignores AX SetFocused); the existing query is cleared with Cmd+A + Delete, the book title is typed, Return filters the library to that book, and a Quartz-posted double-click on the first grid cell opens it. This requires granting **Accessibility permission to Alfred** in *System Settings → Privacy & Security → Accessibility*. Caveats: the back-arrow is clicked at `(winX+30, winY+55)` and the book-cell double-click at `(30%, 22%)` of the window — both are layout-dependent heuristics; tweak them in `kindle-lassen-open.sh` if they miss on your setup. The fully-rendered library window must be reachable from the current Kindle state for the workaround to work.
- I could not figure out how the Kindle app can tell if a book was first loaned, then purchased. Currently, if that is the case (i.e. a book was first loaned, then purchased), the book will appear as loaned.
- Full-text book search currently supports EPUB content. Non-EPUB formats (for example MOBI/AZW3/PDF) can be listed/opened, but search-inside-book is EPUB-only.
- For Calibre match opens, EPUBs are reflowable, so jumping is chapter/locator based rather than fixed "page number" precise.
- not tested thoroughly for user-uploaded documents.



<h1 id="acknowledgments">Acknowledgments 😀</h1>

- Thanks to the [Alfred forum](https://www.alfredforum.com) community!
- Icon from [SF symbols](https://developer.apple.com/sf-symbols/)

<h1 id="changelog">Changelog 🧰</h1>

- 10-07-2024: version 0.2: from kindle to eBooks
- 02-28-2023: version 0.1


<h1 id="feedback">Feedback 🧐</h1>

Feedback welcome! If you notice a bug, or have ideas for new features, please feel free to get in touch either here, or on the [Alfred](https://www.alfredforum.com) forum. 
