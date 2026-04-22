#!/usr/bin/env python3
#Sunny ☀️   🌡️+44°F (feels +39°F, 41%) 🌬️↘2mph 🌗 Tue Feb 14 06:18:23 2023
#W7Q1 – 45 ➡️ 319 – 279 ❇️ 85

import os
import re
import json
from config import (
	log,
	KINDLE_APP,
	XML_CACHE,
	KINDLE_PATH,
	BOOK_CONTENT_SYMBOL,
	GHOST_RESULTS,
	SEARCH_SCOPE,
	IBOOKS_PATH,
	IBOOKS_ANNOTATION_DB,
	KINDLE_ANNOT_STORAGE,
	KINDLE_KSDK_ANNOT_DB,
	GHOST_SYMBOL,
	TIMESTAMP_KINDLE,
	TIMESTAMP_IBOOKS,
	KINDLE_PICKLE,
	IBOOKS_PICKLE,
	KINDLE_HL_PICKLE,
	IBOOKS_HL_PICKLE,
	YOMU_HL_PICKLE,
	CALIBRE_HL_PICKLE,
	YOMU_DATA_DB,
	YOMU_EPUB_CACHE_DIR,
	TIMESTAMP_YOMU,
	YOMU_PICKLE,
	CALIBRE_METADATA_DB,
	TIMESTAMP_CALIBRE,
	CALIBRE_PICKLE,
	USE_KINDLE,
	USE_IBOOKS,
	USE_YOMU,
	USE_CALIBRE,
)
from time import time


import sys
import json
import pickle
from kindle_fun import (
	get_kindle,
	get_ibooks,
	get_yomu,
	get_calibre,
	checkTimeStamp,
	getDownloadedASINs,
	get_kindleClassic,
	get_ibooks_highlights,
	get_kindle_highlights,
	get_yomu_highlights,
	get_calibre_highlights,
)
from highlight_images import ensure_highlight_image, _normalize_body


MYINPUT = sys.argv[1].casefold()

# Matches a "bare" --tag token at the end of the query, i.e. the user typed
# `--tag` (optionally with trailing whitespace) but has not started typing a
# tag name yet. Used to swap "no results" for a list of available tags.
_BARE_TAG_RE = re.compile(r'(?:^|\s)--tag\s*$')

# Matches a `--tag` filter with a value, accepting either form:
#   --tag sci-fi              (single-word tag, unchanged)
#   --tag (home improvement)  (multi-word tag, parenthesized)
# The separator after `--tag` can be whitespace, ':' or '=' (the last two
# are preserved as legacy shorthand, e.g. `--tag:fiction`). The multi-word
# form comes from the autocomplete dropdown wrapping tags that contain a
# space, following the same pattern used in the AlfreDo workflow —
# otherwise Alfred's space-tokenized query breaks the tag name apart.
_TAG_FILTER_RE = re.compile(r'--tag[:=\s]+(?:\(([^)]+)\)|(\S+))')

# Matches the --highlights operator anywhere in the query. The tail (anything
# after the token) is taken as a free-text search against highlight passages
# and notes. An empty tail triggers a prompt + summary response.
_HIGHLIGHTS_RE = re.compile(r'(?:^|\s)--highlights?\b(.*)$', re.IGNORECASE)

# `drill_source` and `drill_book_id` are set by the main script filter's
# alt-mod as Alfred `variables` on the selected book. They arrive here via
# a Call External Trigger -> Script Filter chain (trigger id "highlightsDrill",
# both passinputasargument + passvariables enabled), so by the time this
# script runs for drill-down they're plain environment variables. When both
# are present we switch into single-book drill-down mode; `MYINPUT` is then
# interpreted as a sub-filter over that book's highlights.
_DRILL_SOURCE = (os.getenv('drill_source') or '').strip()
_DRILL_BOOK_ID = (os.getenv('drill_book_id') or '').strip()


def _load_all_highlights():
	"""Load every per-source highlights pickle and return a flat list."""
	out = []
	for path, enabled in (
		(IBOOKS_HL_PICKLE, USE_IBOOKS),
		(CALIBRE_HL_PICKLE, USE_CALIBRE),
		(YOMU_HL_PICKLE, USE_YOMU),
		(KINDLE_HL_PICKLE, USE_KINDLE),
	):
		if not enabled:
			continue
		if not os.path.exists(path):
			continue
		try:
			with open(path, 'rb') as fh:
				out.extend(pickle.load(fh))
		except Exception as e:
			log(f"failed to load highlights from {path}: {e}")
	return out


def _index_highlights_by_book(highlights):
	"""Return dict keyed by (source, book_id) -> count of highlights."""
	counts = {}
	for h in highlights:
		key = (h.source, h.book_id)
		counts[key] = counts.get(key, 0) + 1
	return counts


def _apply_non_tag_filters(books, search_string):
	"""
	Apply every filter that search_books() understands *except* --tag and the
	free-text query itself. Used to scope tag autocomplete suggestions: if the
	user typed `--p --tag`, we should only suggest tags that appear on
	purchased books.
	"""
	if '--p' in search_string:
		books = [b for b in books if b.loaned != 1]
	if '--l' in search_string:
		books = [b for b in books if b.loaned == 1]
	if '--d' in search_string:
		books = [b for b in books if b.downloaded == 1]
	if '--k' in search_string:
		books = [b for b in books if b.source == 'Kindle']
	if '--ib' in search_string:
		books = [b for b in books if b.source == 'iBooks']
	if '--c' in search_string:
		books = [b for b in books if b.source == 'Calibre']
	if '--read' in search_string:
		books = [b for b in books if b.read_pct == '100.0%']
	if GHOST_RESULTS == '0':
		books = [b for b in books if b.loaned == 0]
	return books


def build_tag_suggestions_response(books, search_string):
	"""
	Build an Alfred JSON response that lists available tags as autocomplete
	items. Triggered when the query ends with a bare `--tag` token.
	"""
	scoped = _apply_non_tag_filters(books, search_string)

	tag_counts = {}
	for book in scoped:
		for tag in book.tag_list:
			tag_counts[tag] = tag_counts.get(tag, 0) + 1

	# Keep everything the user has already typed, minus the trailing bare
	# --tag token. We re-append `--tag <name>` ourselves for autocomplete.
	prefix = _BARE_TAG_RE.sub('', search_string).strip()
	prefix_autocomplete = (prefix + ' ') if prefix else ''

	items = []

	if not tag_counts:
		items.append({
			"title": "No tags found in your library",
			"subtitle": (
				"Tags come from Apple Books Collections, Calibre tags, "
				"and Yomu tags. Add some in those apps, then refresh."
			),
			"valid": False,
			"icon": {"path": "icons/Warning.png"},
		})
		return {"items": items}

	items.append({
		"title": "Type a tag name to narrow results",
		"subtitle": (
			f"{len(tag_counts)} tag{'s' if len(tag_counts) != 1 else ''} available"
			" — ⇥ tab to autocomplete"
		),
		"valid": False,
		"icon": {"path": "icon.png"},
	})

	# Sort by book count desc, then name.
	for tag_name, count in sorted(
		tag_counts.items(), key=lambda kv: (-kv[1], kv[0].lower())
	):
		# Multi-word tags (e.g. "Home Improvement", "Want to Read") have
		# to travel through Alfred's query string as a single token, so
		# we wrap them in parentheses. The `--tag` parser below unwraps
		# them. Same convention as the AlfreDo workflow.
		tag_token = f"({tag_name})" if " " in tag_name else tag_name
		items.append({
			"title": f"🏷️ {tag_name}",
			"subtitle": f"{count} book{'s' if count != 1 else ''} tagged '{tag_name}'",
			"autocomplete": f"{prefix_autocomplete}--tag {tag_token} ",
			"arg": f"--tag {tag_token}",
			"valid": False,
			"icon": {"path": "icon.png"},
		})

	return {"items": items}


def _join_fragment_parts(*parts):
	"""
	Join fragment-id components (location anchor, timestamp, …) into a
	single compact string for the `fragment_id` workflow variable, used
	both by the highlights drill-down and by in-book search results.

	Empty / None parts are dropped; remaining parts are joined with
	`  ·  ` so the downstream markdown / text-view footer stays
	readable when any individual component is missing.
	"""
	cleaned = [str(p).strip() for p in parts if p is not None and str(p).strip()]
	return "  ·  ".join(cleaned)


# Max length of a highlight title as shown in Alfred's main row. The full
# passage is always available in the QuickLook card (⇧ / Y) and in the
# downstream text view, so the Alfred row only needs a short, scannable
# preview — anything longer gets truncated with an ellipsis.
_HIGHLIGHT_TITLE_MAX = 100


def _flatten_for_title(text):
	"""
	Collapse all whitespace (incl. embedded `\\n` / `\\t` / repeated
	spaces) to single spaces and trim to `_HIGHLIGHT_TITLE_MAX` chars
	with a trailing ellipsis. Alfred renders item titles on a single
	line and cuts at the first `\\n`, so raw highlight text — which
	often carries the source's on-screen line breaks — appears
	unexpectedly short without this.
	"""
	if not text:
		return ""
	flat = " ".join(str(text).split())
	if len(flat) > _HIGHLIGHT_TITLE_MAX:
		flat = flat[:_HIGHLIGHT_TITLE_MAX - 1].rstrip() + "…"
	return flat


def build_book_highlights_response(all_highlights, books, source, book_id, tail):
	"""
	Response for the per-book highlights drill-down screen.

	`source` and `book_id` identify the book (they come from Alfred variables
	set on the main script filter's alt-mod, routed through an external
	trigger). `tail` is whatever the user has typed into the drill-down query
	box and is used as a case-insensitive substring filter over passage + note.

	Shows each highlight as its own Alfred row, with the full passage text as
	the item's title. The row's `quicklookurl` exposes a typeset highlight
	card so ⇧ / Y previews the passage in Alfred's QuickLook overlay.
	"""
	op_source = (source or "").strip().lower()
	op_book_id = (book_id or "").strip()
	tail = (tail or "").strip()

	if not op_source or not op_book_id:
		return {"items": [{
			"title": "Highlights drill-down called with no book",
			"subtitle": "(missing drill_source / drill_book_id)",
			"valid": False,
			"icon": {"path": "icons/Warning.png"},
		}]}

	# Find the Book and all of its highlights (case-insensitive ID match).
	source_canonical = {
		"kindle": "Kindle",
		"ibooks": "iBooks",
		"calibre": "Calibre",
		"yomu": "Yomu",
	}.get(op_source, source.strip())

	target_book = None
	for b in books:
		if b.source == source_canonical and b.bookID.casefold() == op_book_id.casefold():
			target_book = b
			break

	book_highlights = [
		h for h in all_highlights
		if h.source == source_canonical
		and h.book_id.casefold() == op_book_id.casefold()
	]

	# Optional free-text filter after the operator.
	if tail:
		needle = tail.lower()
		book_highlights = [
			h for h in book_highlights
			if needle in (h.text or "").lower() or needle in (h.note or "").lower()
		]

	items = []

	# Header row with book metadata + counts.
	if target_book is not None:
		header_title = f"💬 {len(book_highlights)} – {target_book.title}"
		header_subtitle_bits = []
		if target_book.author:
			header_subtitle_bits.append(target_book.author)
		header_subtitle_bits.append(f"📚 {target_book.source}")
		if tail:
			header_subtitle_bits.append(f"filter: '{tail}'")
		header_subtitle_bits.append("↩ open book")

		header_arg = _book_open_arg(target_book)

		items.append({
			"title": header_title,
			"subtitle": " – ".join(header_subtitle_bits),
			"valid": bool(header_arg),
			"arg": header_arg,
			"icon": {"path": target_book.icon_path or "icon.png"},
			"variables": {
				"action": "open_book",
			},
		})

	if not book_highlights:
		items.append({
			"title": (
				f"No highlights match '{tail}'"
				if tail
				else "No highlights for this book"
			),
			"subtitle": (
				"(Kindle highlight passages aren't stored locally — try ⌘↩ on the header to open the cloud notebook.)"
				if source_canonical == "Kindle" and not tail
				else "Try a different word."
			),
			"valid": False,
			"icon": {"path": "icons/Warning.png"},
		})
		return {"items": items}

	# Sort by location if numeric-ish, else by created date.
	def _sort_key(h):
		loc = h.location or ""
		try:
			# Kindle locations look like "12345-12350"; sort by start.
			return (0, int(loc.split("-", 1)[0]))
		except Exception:
			return (1, h.created or "", loc)

	book_highlights.sort(key=_sort_key)

	total = len(book_highlights)
	icon_path = (target_book.icon_path if target_book else "") or "icon.png"
	book_title = target_book.title if target_book else op_book_id
	for idx, h in enumerate(book_highlights, start=1):
		# Flatten embedded newlines (Alfred cuts titles at the first
		# `\n`) and cap at a short preview length. The full passage is
		# always visible in the QuickLook card (⇧ / Y) and in the
		# downstream text view.
		title_line = _flatten_for_title(h.display_text)

		# Subtitle starts with the book title so the user can always see
		# which book they're inside (handy if they leave the drill-down
		# open and come back). Style / note snippet / date follow. The
		# raw highlight location (epubcfi / Kindle position) is NOT
		# shown here — it's noisy in the UI but useful for the markdown
		# footer downstream, so we ship it out as the `highlight_id`
		# workflow variable instead.
		subtitle_bits = [f"{idx}/{total:,}", f"📖 {book_title}"]
		if h.style and h.style != "highlight":
			subtitle_bits.append(h.style.upper())
		if h.note and h.text:
			snippet = h.note[:60] + ("…" if len(h.note) > 60 else "")
			subtitle_bits.append(f"📝 {snippet}")
		if h.created:
			subtitle_bits.append(h.created)

		# ↩ on a highlight row now flags `action = show_highlight` in the
		# Alfred variable stream so downstream graph nodes (e.g. a Large
		# Type / text-window output connected after the drill-down script
		# filter) can route on it. The `arg` carries the clean passage
		# text (no location/date header) so that output node displays it
		# verbatim. Notes are appended if no passage text exists (e.g.
		# Kindle highlights where only the user note is stored locally).
		# Opening the book stays available via ⌘↩ (see `mods.cmd` below).
		#
		# The passage is run through `_normalize_body()` so hard line
		# breaks baked into the source annotation (iBooks/Calibre copy
		# over the on-screen wrapping) don't show up as ragged breaks
		# in the downstream text view. Genuine paragraph breaks are
		# preserved.
		if h.text:
			show_body = _normalize_body(h.text)
			if h.note:
				show_body = f"{show_body}\n\n— note: {_normalize_body(h.note)}"
		elif h.note:
			show_body = _normalize_body(h.note)
		else:
			show_body = title_line

		# Pre-render a QuickLook JPG for this highlight, matching the
		# pattern used by the alfred-readwise workflow. Generation is
		# lazy + cached: the file is created only the first time this
		# row is shown, then reused forever (keyed by the stable
		# `quicklook_file_id` hash). If Pillow is missing or rendering
		# fails we quietly skip `quicklookurl` and Alfred shows its
		# default "no preview" state on Space.
		quicklook_path = ensure_highlight_image(h, target_book)

		item = {
			"title": title_line,
			"subtitle": " – ".join(subtitle_bits),
			"valid": True,
			"icon": {"path": icon_path},
			"arg": show_body,
			"variables": {
				"action": "show_highlight",
				# Exposed so the downstream markdown / text-view node
				# can render the location (epubcfi, Kindle position,
				# Yomu anchor, etc.) + timestamp as a footer. We
				# reuse the name `fragment_id` so the in-book search
				# results (searchEPUB.py) can feed the same variable
				# into the same downstream template. The two halves
				# are joined with `  ·  ` when both exist; either can
				# be empty (some Kindle rows have no location; some
				# highlights lack a created date).
				"fragment_id": _join_fragment_parts(h.location, h.created),
			},
		}
		if quicklook_path:
			item["quicklookurl"] = quicklook_path

		# ⌃↩  — mirror the contract that regular book rows use so the
		# main script filter's graph connection
		#   ⌃ (modifiers: 262144) → Argument (curr_book = {query}) →
		#   Script Filter `24764E8D` (searchEPUB.py --book=$curr_book)
		# receives a sane `curr_book`. `searchEPUB.py` only understands
		# real `.epub` paths (plus the `calibre-open|…` tokenized form);
		# for Kindle URLs, iBooks deep-links, Yomu tokens, or cloud-only
		# copies we keep the mod visible but invalid with a clear reason
		# instead of letting downstream surface its generic format
		# warning. NOTE: the mod key MUST be "ctrl" — the main graph
		# uses modifier 262144 (control), not command (1048576).
		search_book_arg, search_reason = _resolve_searchable_epub(target_book)

		if search_book_arg:
			item["mods"] = {
				"ctrl": {
					"valid": True,
					"subtitle": (
						f"⌃↩ Search this book ({target_book.source})"
						if target_book
						else "⌃↩ Search this book"
					),
					"arg": search_book_arg,
				},
			}
		else:
			item["mods"] = {
				"ctrl": {
					"valid": False,
					"subtitle": f"⌃↩ Search this book — {search_reason}",
					"arg": "",
				},
			}

		# ⇧↩  — open the book (same deep-link as the header row's ↩).
		# This is routed through the default Conditional via the
		# `action=open_book` variable, so it piggybacks on the existing
		# enter-path dispatcher and needs no new graph connection.
		open_arg = h.arg
		if not open_arg and target_book is not None:
			open_arg = _book_open_arg(target_book)
		if open_arg:
			item["mods"]["shift"] = {
				"valid": True,
				"subtitle": (
					f"⇧↩ Open the book ({target_book.source})"
					if target_book
					else "⇧↩ Open the book"
				),
				"arg": open_arg,
				"variables": {
					"action": "open_book",
				},
			}
		items.append(item)

	return {"items": items}


def _book_open_arg(book):
	"""Compute the dispatcher-handler `arg` that opens a given Book."""
	if book is None:
		return ""
	if book.source == "Kindle" and KINDLE_APP == "new" and book.bookID:
		return f"kindle-lassen-open|{book.bookID}|{book.title}"
	if book.source == "iBooks" and book.bookID:
		return f"ibooks://assetid/{book.bookID}"
	return book.path or ""


def _resolve_searchable_epub(book):
	"""
	Check whether `book.path` points at something `searchEPUB.py --book`
	can actually process (a real local `.epub` file, optionally wrapped in
	the `calibre-open|…` token it understands).

	Returns `(arg, reason)`:
	  - `arg`    the value to hand to the "search this book" pipeline, or
	             `""` when the book isn't searchable.
	  - `reason` short human-readable explanation when `arg == ""`. Empty
	             string on success.

	We gate ⌘↩ on highlight rows with this so that Kindle URLs, iBooks
	deep-links, or books with only a cloud copy don't fall through to
	`searchEPUB.py` and surface its generic format warning. Yomu books
	*are* searchable: their unpacked EPUB bundle lives on disk under
	`YOMU_EPUB_CACHE_DIR`, and searchEPUB.py knows how to resolve the
	`yomu-open|…` token to that bundle.
	"""
	if book is None:
		return "", "book not found in the library cache"

	raw = (book.path or "").strip()
	if not raw:
		return "", "no local file path recorded for this book"

	if raw.startswith("yomu-open|"):
		# yomu-open|<meta_ident>|<identifier>|<file_ident>  — the
		# third segment is the cache folder name. Yomu populates the
		# bundle lazily the first time the user opens the book, so if
		# the folder is missing we tell the user *why*, not a generic
		# format error.
		parts = raw.split("|")
		identifier = parts[2].strip() if len(parts) > 2 else ""
		if not identifier:
			return "", "Yomu book is missing its identifier"
		bundle_dir = os.path.join(YOMU_EPUB_CACHE_DIR, identifier)
		if not os.path.isdir(bundle_dir):
			return "", "open the book in Yomu once so it caches the EPUB"
		if not os.path.isfile(os.path.join(bundle_dir, "META-INF", "container.xml")):
			return "", "Yomu's EPUB cache for this book is incomplete"
		return raw, ""

	candidate = raw
	if candidate.startswith("calibre-open|"):
		# `calibre-open|/abs/path.epub[|location]`
		candidate = candidate[len("calibre-open|"):].split("|", 1)[0]
	elif "://" in candidate or candidate.startswith(("http:", "https:", "ibooks:", "kindle-lassen-open|")):
		# URL-style paths (Kindle cloud, iBooks deep-link, Kindle
		# Lassen token) are not files on disk.
		return "", f"{book.source or 'this'} books aren't searchable locally"

	expanded = os.path.expanduser(candidate)
	if not expanded.lower().endswith(".epub"):
		return "", "only .epub files can be searched"
	# EPUBs may live on disk either as a single .epub zip (Calibre) or
	# as an unpacked bundle directory with an .epub suffix (iBooks stores
	# them this way). `ebooklib.epub.read_epub()` handles both.
	if not os.path.exists(expanded):
		return "", "the .epub file isn't on disk (download/sync it first)"

	return raw, ""


def build_highlights_response(highlights, books, search_string):
	"""
	Build an Alfred JSON response for `--highlights <query>` mode.

	- Bare `--highlights` (no tail) -> a summary item + per-source counts,
	  nudging the user to type search text.
	- With a tail query -> flat list of matching highlights across all sources,
	  each showing book title + highlighted passage as subtitle.
	- Respects per-source filters (--k / --ib / --c / --y) if present so you
	  can narrow, e.g. "--ib --highlights stoic" -> Apple-Books-only results.
	"""
	# Apply source filters (same tokens as regular book search). We do *not*
	# apply --p / --l / --d / --read here; those are library-level concepts.
	allowed_sources = None
	selectors = []
	if '--k' in search_string:
		selectors.append('Kindle')
	if '--ib' in search_string:
		selectors.append('iBooks')
	if '--c' in search_string:
		selectors.append('Calibre')
	if '--y' in search_string:
		selectors.append('Yomu')
	if selectors:
		allowed_sources = set(selectors)
		highlights = [h for h in highlights if h.source in allowed_sources]

	# Look up book titles / authors / icons so a highlight row can render
	# meaningful context. Keyed by (source, book_id) same as hl_counts.
	book_lookup = {(b.source, b.bookID): b for b in books}

	# Extract the free-text tail that follows `--highlights`.
	m = _HIGHLIGHTS_RE.search(search_string)
	tail = (m.group(1) if m else "").strip()
	# Strip out remaining operator tokens from the tail so they don't leak
	# into the substring match.
	for tok in ('--k', '--ib', '--c', '--y', '--tagged'):
		tail = tail.replace(tok, '')
	tail = tail.strip()

	items = []

	# Bare --highlights -> summary.
	if not tail:
		if not highlights:
			items.append({
				"title": "No highlights yet",
				"subtitle": (
					"Apple Books / Calibre / Yomu store the text locally; "
					"Kindle stores counts + notes only."
				),
				"valid": False,
				"icon": {"path": "icons/Warning.png"},
			})
			return {"items": items}

		per_source = {}
		for h in highlights:
			per_source[h.source] = per_source.get(h.source, 0) + 1

		items.append({
			"title": "Type words to search across your highlights",
			"subtitle": (
				f"{len(highlights):,} highlight"
				f"{'s' if len(highlights) != 1 else ''} across "
				+ ", ".join(
					f"{n:,} in {src}" for src, n in sorted(per_source.items())
				)
				+ " — ⇥ tab to autocomplete"
			),
			"autocomplete": _HIGHLIGHTS_RE.sub("", search_string).rstrip() + " --highlights ",
			"valid": False,
			"icon": {"path": "icon.png"},
		})
		# Also list books with the most highlights so they can dive in.
		candidate_books = books
		if allowed_sources is not None:
			candidate_books = [b for b in books if b.source in allowed_sources]
		top_books = sorted(
			(b for b in candidate_books if b.highlights_count),
			key=lambda b: -b.highlights_count,
		)[:15]
		for b in top_books:
			items.append({
				"title": f"💬 {b.highlights_count} – {b.title}",
				"subtitle": f"{b.author} (📚 {b.source})",
				"valid": False,
				"icon": {"path": b.icon_path or "icon.png"},
				"autocomplete": (
					_HIGHLIGHTS_RE.sub("", search_string).rstrip()
					+ f" --highlights "
				),
			})
		return {"items": items}

	# Filtered list: substring match against text + note, case-insensitive.
	needle = tail.lower()
	matches = []
	for h in highlights:
		haystack = f"{h.text}\n{h.note}".lower()
		if needle in haystack:
			matches.append(h)

	if not matches:
		items.append({
			"title": f"No highlights match '{tail}'",
			"subtitle": "Try a shorter / different word, or check source filters.",
			"valid": False,
			"icon": {"path": "icons/Warning.png"},
		})
		return {"items": items}

	# Sort: Kindle last (no text), then alpha by book title.
	def _sort_key(h):
		b = book_lookup.get((h.source, h.book_id))
		title = (b.title if b else "").lower()
		return (h.source == "Kindle", title, h.created)

	matches.sort(key=_sort_key)

	for idx, h in enumerate(matches, start=1):
		b = book_lookup.get((h.source, h.book_id))
		book_title = b.title if b else h.book_id
		author = b.author if b else ""
		icon_path = (b.icon_path if b else "") or "icon.png"

		# Flatten embedded newlines (Alfred cuts titles at the first
		# `\n`) and cap to a short preview; the full passage is in the
		# QuickLook card / downstream text view.
		title_line = _flatten_for_title(h.display_text)

		subtitle_bits = [f"{idx}/{len(matches):,}", f"📖 {book_title}"]
		if author:
			subtitle_bits.append(author)
		if h.note and h.text:
			snippet = h.note[:60] + ("…" if len(h.note) > 60 else "")
			subtitle_bits.append(f"📝 {snippet}")
		if h.created:
			subtitle_bits.append(h.created)
		subtitle_bits.append(f"📚 {h.source}")

		# arg is what the open handler receives. If the Highlight has one,
		# use it; otherwise fall back to opening the book itself.
		arg = h.arg
		if not arg and b is not None:
			if b.source == "Kindle" and KINDLE_APP == "new" and b.bookID:
				arg = f"kindle-lassen-open|{b.bookID}|{b.title}"
			else:
				arg = b.path or ""

		# QuickLook preview: same cached renderer as the drill-down,
		# so navigating through cross-library results with Space gives
		# the user a styled preview of each match.
		quicklook_path = ensure_highlight_image(h, b)

		item = {
			"title": title_line,
			"subtitle": " – ".join(subtitle_bits),
			"valid": True,
			"icon": {"path": icon_path},
			"arg": arg,
		}
		if quicklook_path:
			item["quicklookurl"] = quicklook_path
		# cmd+enter copies the highlight text to the clipboard (Alfred shows
		# the subtitle text of the mod block). Handy for quoting passages.
		# Normalize first so hard wraps from the source annotation don't
		# survive the paste into a notes app.
		if h.text or h.note:
			copy_body = _normalize_body(h.text or h.note)
			item["mods"] = {
				"cmd": {
					"valid": True,
					"subtitle": f"Copy highlight: {copy_body[:80]}",
					"arg": copy_body,
				}
			}
		items.append(item)

	return {"items": items}


def search_books(books, search_string):
	if '--p' in search_string:
		search_string = search_string.replace('--p', '')
		books = [book for book in books if book.loaned != 1]
	
	if '--l' in search_string:
		search_string = search_string.replace('--l', '')
		books = [book for book in books if book.loaned == 1]
	
	if '--d' in search_string:
		search_string = search_string.replace('--d', '')
		books = [book for book in books if book.downloaded == 1]
	

	if '--k' in search_string:
		search_string = search_string.replace('--k', '')
		books = [book for book in books if book.source == 'Kindle']
	
	if '--ib' in search_string:
		search_string = search_string.replace('--ib', '')
		books = [book for book in books if book.source == 'iBooks']

	if '--c' in search_string:
		search_string = search_string.replace('--c', '')
		books = [book for book in books if book.source == 'Calibre']
	
	if '--read' in search_string:
		search_string = search_string.replace('--read', '')
		books = [book for book in books if book.read_pct == '100.0%']

	# Narrow by tag name, e.g. `--tag sci-fi`, `--tag:Durant`, or — for
	# multi-word tags coming from the autocomplete dropdown —
	# `--tag (home improvement)`. Matches are substring, case-insensitive,
	# against any individual tag on the book. We strip each matched token
	# out of `search_string` as we go so the remaining words fall through
	# to the free-text title/author search.
	tag_filters = []
	def _consume_tag(match):
		tag_filters.append((match.group(1) or match.group(2) or "").strip())
		return ''
	search_string = _TAG_FILTER_RE.sub(_consume_tag, search_string)
	tag_filters = [t for t in tag_filters if t]
	if tag_filters:
		needles = [t.lower() for t in tag_filters]
		books = [
			book
			for book in books
			if all(
				any(n in t.lower() for t in book.tag_list)
				for n in needles
			)
		]

	# Books with any tag at all — useful to see what got classified.
	if '--tagged' in search_string:
		search_string = search_string.replace('--tagged', '')
		books = [book for book in books if book.tag_list]

	if GHOST_RESULTS == '0':
		books = [book for book in books if book.loaned == 0]

	search_fragments = search_string.split()
	if not search_fragments:
		search_fragments = [""]

	results = []
	if not search_string.strip():
		return books

	def _matches(book_obj, fragment):
		frag = fragment.lower()
		title = (book_obj.title or "").lower()
		author = (book_obj.author or "").lower()
		tags = (book_obj.tags or "").lower()
		if SEARCH_SCOPE == "Title":
			return frag in title
		if SEARCH_SCOPE == "Author":
			return frag in author
		if SEARCH_SCOPE == "Both":
			return frag in title or frag in author
		if SEARCH_SCOPE == "Tags":
			return frag in tags
		if SEARCH_SCOPE == "All":
			return frag in title or frag in author or frag in tags
		# Back-compat: the old "Yomu" scope searched title+author+Yomu-only tags.
		# It now behaves like "All" but is kept so existing workflow config
		# values keep working.
		if SEARCH_SCOPE == "Yomu":
			return frag in title or frag in author or frag in tags
		return frag in title

	for book in books:
		if SEARCH_SCOPE in ("Both", "All", "Yomu", "Tags"):
			if all(_matches(book, fragment) for fragment in search_fragments):
				results.append(book)
		else:
			if any(_matches(book, fragment) for fragment in search_fragments):
				results.append(book)

	return results

def serveBooks(books, result):
	myCounter = 0
	
	for myBook in books:
		loanedString = ""
		downloadedString = ""
	
		myCounter += 1
		if myBook.loaned == 1:
			loanedString = GHOST_SYMBOL
		if myBook.downloaded == 1:
			downloadedString = BOOK_CONTENT_SYMBOL

		# I currently can't figure out how to classify the books that were first loaned, then purchased. In case they were downloaded I can just remove the ghost symbol
		if loanedString == GHOST_SYMBOL and downloadedString == BOOK_CONTENT_SYMBOL:
			loanedString = ""
		booksN = len(books)
		
		if myBook.read_pct == "100.0%":
			readPct = "✅️"
		elif myBook.read_pct != "0%":
			readPct = myBook.read_pct
		else:
			readPct = ""

		tagsPart = ""
		tagsRaw = (getattr(myBook, "tags", "") or "").strip()
		if tagsRaw:
			tagsPart = f"🏷️ {tagsRaw}"
			# Alfred subtitles get cramped quickly with long tag lists.
			if len(tagsPart) > 90:
				tagsPart = tagsPart[:87] + "..."

		highlightsPart = ""
		hlCount = getattr(myBook, "highlights_count", 0) or 0
		if hlCount:
			highlightsPart = f"💬 {hlCount}"
		open_arg = myBook.path
		if myBook.source == "Kindle" and KINDLE_APP == "new" and myBook.bookID:
			# The new Kindle Mac app has no deep-link to a specific book; the
			# shell script drives the library "Search Kindle" field via UI
			# automation, so we pass the title along with the ASIN.
			open_arg = f"kindle-lassen-open|{myBook.bookID}|{myBook.title}"

		item = {
			"title": f"{myBook.title} {loanedString} {downloadedString}",
			'subtitle': (
				f"{myCounter}/{booksN:,} – {myBook.author}"
				+ (f" {readPct}" if readPct else "")
				+ (f" {highlightsPart}" if highlightsPart else "")
				+ (f" {tagsPart}" if tagsPart else "")
				+ f" (📚 {myBook.source})"
			).rstrip(),
			'valid': True,
			"icon": {
				"path": myBook.icon_path

			},
			"mods": {
				"cmd": {
					"valid": True,
					"subtitle": myBook.icon_path
				}
			},
			'arg': open_arg
		}

		# alt+↩ routes (via the alt-keyed connection on the main script
		# filter → Call External Trigger → `highlightsDrill` script filter)
		# into drill-down mode: one highlight per Alfred row, full text
		# visible. The book identity travels as Alfred workflow `variables`
		# on this mod — never through the query string — so the drill-down
		# search box opens empty and the downstream script reads
		# drill_source / drill_book_id from env. We ALWAYS attach the mod,
		# even for books with zero highlights, because without it Alfred
		# falls back to the row's default `arg` (e.g. `yomu-open|…`) and
		# that token ends up pre-filled in the drill-down search box.
		book_hls = getattr(myBook, "_highlights", []) or []

		if myBook.bookID:
			if book_hls:
				alt_subtitle = (
					f"⌥↩ List {len(book_hls)} highlight"
					f"{'s' if len(book_hls) != 1 else ''} one-per-row"
				)
			else:
				alt_subtitle = "⌥↩ No highlights captured for this book yet"
			item["mods"]["alt"] = {
				# Kept valid even when empty so the user gets clear
				# feedback ("No highlights…") instead of Alfred silently
				# falling back to the default arg and stuffing an
				# open-token into the drill-down search box.
				"valid": True,
				"subtitle": alt_subtitle,
				"arg": "",
				"variables": {
					"drill_source": myBook.source,
					"drill_book_id": myBook.bookID,
				},
			}

		result["items"].append(item)
	


	if not books:
		result["items"].append({
			"title": f"No results!",
			'subtitle': f"query again",
			'valid': True,
			"icon": {
				"path": f'icons/Warning.png'
			},
			'arg': "resultString"
		})
	
	return result




def main():
	main_start_time = time()
	
	myBooks = []
	# Tracks which sources had their books pickle rebuilt this turn; used to
	# chain a highlights rebuild to the same trigger (source-DB mtime change).
	rebuilt_sources = set()

	if USE_KINDLE:
		if KINDLE_APP == "classic":

			myContentBooks = getDownloadedASINs(KINDLE_PATH) # output is a list of downloaded book ASINs
			#log(myContentBooks)
			get_kindleClassic(XML_CACHE, myContentBooks)
			with open(KINDLE_PICKLE, 'rb') as file:
				myBooks = myBooks + pickle.load(file)


		elif KINDLE_APP == "new":


			
			if not os.path.exists(KINDLE_PICKLE):
				log ("building new kindle database")
				get_kindle(KINDLE_PATH)
				rebuilt_sources.add("Kindle")
				
			elif checkTimeStamp(KINDLE_PATH,TIMESTAMP_KINDLE):
				log ("outdated, building new kindle database")
				get_kindle(KINDLE_PATH)
				rebuilt_sources.add("Kindle")
				
			else:
				log ("using existing Kindle database")
				# Load the list of books from the file
			
			with open(KINDLE_PICKLE, 'rb') as file:
				myBooks = myBooks + pickle.load(file)

			# Refresh Kindle highlights if books were rebuilt or the pickle is
			# missing (e.g. first run after upgrade).
			if "Kindle" in rebuilt_sources or not os.path.exists(KINDLE_HL_PICKLE):
				get_kindle_highlights(KINDLE_ANNOT_STORAGE, KINDLE_KSDK_ANNOT_DB)


	if USE_IBOOKS:
		if not os.path.exists(IBOOKS_PICKLE):
				log ("building new iBooks database")
				get_ibooks(IBOOKS_PATH)
				rebuilt_sources.add("iBooks")
				
		elif checkTimeStamp(IBOOKS_PATH,TIMESTAMP_IBOOKS):
			log ("outdated, building new iBooks database")
			get_ibooks(IBOOKS_PATH)
			rebuilt_sources.add("iBooks")
			
		else:
			log ("using existing iBooks database")
			# Load the list of books from the file
		
		with open(IBOOKS_PICKLE, 'rb') as file:
			myBooks = myBooks + pickle.load(file)

		if "iBooks" in rebuilt_sources or not os.path.exists(IBOOKS_HL_PICKLE):
			get_ibooks_highlights(IBOOKS_ANNOTATION_DB)

	if USE_YOMU:
		# For Yomu we use a local CoreData SQLite file as the authoritative source.
		# Rebuild the cache if the DB mtime changes.
		if not os.path.exists(YOMU_PICKLE):
			log("building new Yomu database")
			get_yomu(YOMU_DATA_DB)
			rebuilt_sources.add("Yomu")

		elif os.path.exists(YOMU_DATA_DB) and checkTimeStamp(YOMU_DATA_DB, TIMESTAMP_YOMU):
			log("outdated, building new Yomu database")
			get_yomu(YOMU_DATA_DB)
			rebuilt_sources.add("Yomu")

		if os.path.exists(YOMU_PICKLE):
			with open(YOMU_PICKLE, 'rb') as file:
				myBooks = myBooks + pickle.load(file)

		if "Yomu" in rebuilt_sources or not os.path.exists(YOMU_HL_PICKLE):
			get_yomu_highlights(YOMU_DATA_DB)

	if USE_CALIBRE:
		if not os.path.exists(CALIBRE_PICKLE):
			log("building new Calibre database")
			get_calibre(CALIBRE_METADATA_DB)
			rebuilt_sources.add("Calibre")

		elif os.path.exists(CALIBRE_METADATA_DB) and checkTimeStamp(CALIBRE_METADATA_DB, TIMESTAMP_CALIBRE):
			log("outdated, building new Calibre database")
			get_calibre(CALIBRE_METADATA_DB)
			rebuilt_sources.add("Calibre")

		if os.path.exists(CALIBRE_PICKLE):
			with open(CALIBRE_PICKLE, 'rb') as file:
				myBooks = myBooks + pickle.load(file)

		if "Calibre" in rebuilt_sources or not os.path.exists(CALIBRE_HL_PICKLE):
			get_calibre_highlights(CALIBRE_METADATA_DB)

	# Load highlights and project per-book counts back onto the Book objects
	# so the UI can show a 💬 N chip without a second lookup. We also stash
	# the per-book highlight list on each Book (as a transient attribute)
	# for any downstream consumer that needs it on the book row.
	all_highlights = _load_all_highlights()
	hl_by_book = {}
	for h in all_highlights:
		hl_by_book.setdefault((h.source, h.book_id), []).append(h)
	for book in myBooks:
		book_hls = hl_by_book.get((book.source, book.bookID), [])
		book.highlights_count = len(book_hls)
		book._highlights = book_hls  # transient; not pickled

	# Drill-down mode: Alfred reached this script via the `highlightsDrill`
	# external trigger, carrying `drill_source` + `drill_book_id` as
	# variables-turned-env-vars. Anything the user types into the drill-down
	# query box arrives as MYINPUT and is used as a sub-filter on the book's
	# highlights.
	if _DRILL_SOURCE and _DRILL_BOOK_ID:
		result = build_book_highlights_response(
			all_highlights, myBooks, _DRILL_SOURCE, _DRILL_BOOK_ID, MYINPUT
		)
		print(json.dumps(result))
		main_timeElapsed = time() - main_start_time
		log(f"\nscript duration: {round(main_timeElapsed, 3)} seconds")
		return

	# --highlights <query>: switch modes to a flat, cross-library highlight
	# search. Handled before --tag because they're orthogonal intents and
	# sharing a query box would be confusing.
	if _HIGHLIGHTS_RE.search(MYINPUT):
		result = build_highlights_response(all_highlights, myBooks, MYINPUT)
		print(json.dumps(result))
		main_timeElapsed = time() - main_start_time
		log(f"\nscript duration: {round(main_timeElapsed, 3)} seconds")
		return

	# If the user typed `--tag` without a tag name yet, short-circuit and
	# suggest available tag names instead of falling through to "No results".
	if _BARE_TAG_RE.search(MYINPUT):
		result = build_tag_suggestions_response(myBooks, MYINPUT)
		print(json.dumps(result))
		main_timeElapsed = time() - main_start_time
		log(f"\nscript duration: {round(main_timeElapsed, 3)} seconds")
		return

	# Search the books
	myBooks = search_books(myBooks, MYINPUT)

	result = {"items": []}
	result = serveBooks(myBooks, result)
	print (json.dumps(result))


	main_timeElapsed = time() - main_start_time
	log(f"\nscript duration: {round (main_timeElapsed,3)} seconds")

if __name__ == '__main__':
	main ()



