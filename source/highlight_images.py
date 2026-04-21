#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render highlights to JPG previews for Alfred QuickLook.

Adapted from the readwise workflow's `createImage`:
   /Users/giovanni/github/alfred-readwise/source/readwise_fun.py

The public API is `ensure_highlight_image(highlight, book)`, which
returns a filesystem path to a cached JPG. The file is lazily
generated (only on first request) and then reused indefinitely; the
filename is keyed off `Highlight.quicklook_file_id`, a SHA-1 of the
highlight's full signature, so two distinct highlights can never
collide and the same highlight is rendered exactly once.

Pillow is a hard dependency — it's present on stock Alfred setups
via the system Python; if it's missing we fail soft (log + return
"") so the drill-down still works without previews.
"""

import os
import re
import textwrap

from config import HIGHLIGHTS_IMG_FOLDER, HIGHLIGHT_RENDER_VERSION, log


# Matches two or more newlines (optionally surrounded by any other
# whitespace) — the signal we use to distinguish an actual paragraph
# break from the spurious hard-wrap newlines that ebook annotations
# frequently carry over from the original layout (iBooks likes to bake
# in `\n\t\t\t\t`, Kindle sometimes does `\r\n`, etc.).
_PARAGRAPH_BREAK_RE = re.compile(r"\s*\n\s*\n\s*")
# Any run of whitespace (spaces, tabs, single newlines). Used to fold
# intra-paragraph whitespace into a single space so the renderer can
# reflow the text to fit the image width instead of honouring the
# source's arbitrary line breaks.
_INLINE_WS_RE = re.compile(r"\s+")


def _normalize_body(text):
	"""
	Collapse intra-paragraph whitespace so the renderer can soft-wrap a
	passage naturally, while still preserving genuine paragraph breaks.

	Concretely:
	  - "foo\n\t\tbar"      -> "foo bar"          (hard wrap in source)
	  - "foo\n\nbar"        -> "foo\n\nbar"       (real paragraph break)
	  - "foo   \n   \nbar"  -> "foo\n\nbar"       (tolerates whitespace)

	This exists because iBooks/Calibre annotations often copy over the
	on-screen line breaks from the reader, which then look ugly when
	re-rendered at a different width.
	"""
	if not text:
		return ""
	paragraphs = _PARAGRAPH_BREAK_RE.split(text)
	cleaned = [_INLINE_WS_RE.sub(" ", p).strip() for p in paragraphs]
	return "\n\n".join(p for p in cleaned if p)


try:
	from PIL import Image, ImageDraw, ImageFont  # type: ignore
	_PIL_AVAILABLE = True
except Exception as _pil_exc:  # pragma: no cover — best-effort import
	_PIL_AVAILABLE = False
	log(f"[highlight_images] Pillow not available ({_pil_exc}); "
	    "QuickLook previews will be disabled.")


# ---------------------------------------------------------------------------
# Layout constants. Width is fixed (it's the text-wrap budget); height
# is computed from the actual content so a one-line Kindle note doesn't
# get drawn on the same giant card as a 30-line passage. This both
# kills the "why so much whitespace?" feeling and roughly halves the
# on-disk cache size, since short highlights vastly outnumber long ones.
# ---------------------------------------------------------------------------
_IMG_W = 1200
_IMG_H_MIN = 420              # minimum card height (esp. for short notes)
_IMG_H_MAX = 1600             # safety clamp for truly enormous passages
_DPI = 96
_PADDING = 40
_BG = (252, 250, 245)          # warm off-white, book-paper vibe
_FG = (20, 20, 20)             # body text — near-black for on-screen legibility
_MUTED = (110, 108, 102)       # author/title footer, timestamps
_ACCENT = (181, 153, 70)       # left-edge marker
_BORDER = (200, 195, 185)
_BORDER_W = 4

# Style caption shown above the passage (e.g. "NOTE · 2024-10-08").
_CAPTION_GAP = 14
_BODY_GAP = 18
_NOTE_GAP = 28

# Font candidates: try several common macOS fonts in order, fall back
# to Pillow's built-in bitmap font if none load. We prefer Newsreader
# Medium (Google Fonts, editorial serif designed for on-screen reading)
# because at ~30 pt the Regular weight reads a little spindly against
# a warm background; Medium has more presence without feeling bold.
# Regular and other weights remain in the chain so we still work if
# only a partial family is installed.
_USER_FONTS = os.path.expanduser("~/Library/Fonts")
_SERIF_CANDIDATES = [
	f"{_USER_FONTS}/Newsreader-Medium.ttf",
	f"{_USER_FONTS}/Newsreader-Regular.ttf",
	f"{_USER_FONTS}/Newsreader-VariableFont_opsz,wght.ttf",
	"/Library/Fonts/Newsreader-Medium.ttf",
	"/Library/Fonts/Newsreader-Regular.ttf",
	"/System/Library/Fonts/NewYork.ttf",
	"/System/Library/Fonts/Supplemental/Georgia.ttf",
	"/Library/Fonts/Georgia.ttf",
	"/System/Library/Fonts/Supplemental/Charter.ttc",
	"/System/Library/Fonts/Palatino.ttc",
	"Georgia.ttf",
]
_SANS_CANDIDATES = [
	"/System/Library/Fonts/Helvetica.ttc",
	"/System/Library/Fonts/HelveticaNeue.ttc",
	"/System/Library/Fonts/SFNSDisplay.ttf",
	"Helvetica.ttf",
]


# ---------------------------------------------------------------------------
# Font loading (cached to avoid re-opening TTF files per highlight).
# ---------------------------------------------------------------------------
_FONT_CACHE = {}


def _load_font(candidates, size):
	key = (tuple(candidates), size)
	if key in _FONT_CACHE:
		return _FONT_CACHE[key]
	for path in candidates:
		try:
			f = ImageFont.truetype(path, size)
			_FONT_CACHE[key] = f
			return f
		except Exception:
			continue
	f = ImageFont.load_default()
	_FONT_CACHE[key] = f
	return f


# ---------------------------------------------------------------------------
# Text layout helpers.
# ---------------------------------------------------------------------------
def _wrap_for_font(draw, text, font, max_width):
	"""
	Word-wrap `text` so each rendered line fits within `max_width` pixels.
	Preserves any embedded \n. Uses the Pillow-reported glyph width rather
	than character count so the result is visually correct for
	proportional fonts (Georgia's M is wider than its l).
	"""
	out = []
	for paragraph in text.splitlines() or [""]:
		words = paragraph.split(" ")
		line = ""
		for w in words:
			candidate = f"{line} {w}".strip()
			if draw.textlength(candidate, font=font) <= max_width:
				line = candidate
			else:
				if line:
					out.append(line)
				line = w
		out.append(line)
	return out


def _line_height(font):
	ascent, descent = font.getmetrics()
	return ascent + descent


# ---------------------------------------------------------------------------
# Orphan cleanup.
# ---------------------------------------------------------------------------
def prune_stale_highlight_images():
	"""
	Delete cached JPGs rendered by an older `HIGHLIGHT_RENDER_VERSION`.

	We version the filenames (`v2-<hash>.jpg`) so bumping the renderer
	automatically orphans the previous generation of bitmaps; this
	helper sweeps them away. Safe to call eagerly – it's a single
	`os.listdir` + prefix check. Returns the number of files removed.
	"""
	prefix = f"{HIGHLIGHT_RENDER_VERSION}-"
	removed = 0
	try:
		entries = os.listdir(HIGHLIGHTS_IMG_FOLDER)
	except OSError:
		return 0
	for name in entries:
		if not name.endswith(".jpg"):
			continue
		if name.startswith(prefix):
			continue
		try:
			os.remove(os.path.join(HIGHLIGHTS_IMG_FOLDER, name))
			removed += 1
		except OSError:
			pass
	if removed:
		log(f"[highlight_images] pruned {removed} stale bitmap(s) "
		    f"from earlier render versions.")
	return removed


# Best-effort cleanup the first time the module is imported. We do it
# here rather than on every `ensure_highlight_image` call so it's O(1)
# per process instead of O(N-rows).
prune_stale_highlight_images()


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------
def ensure_highlight_image(highlight, book=None):
	"""
	Return an absolute path to a cached JPG rendering of `highlight`.

	Generates the file lazily on first call. If Pillow isn't available
	or rendering fails for any reason we return an empty string so the
	caller can silently omit `quicklookurl` from the Alfred item.

	`book` is the matching `Book` object (or None) — used to enrich the
	footer with title + author.
	"""
	if not _PIL_AVAILABLE:
		return ""

	out_path = os.path.join(
		HIGHLIGHTS_IMG_FOLDER,
		f"{highlight.quicklook_file_id}.jpg",
	)
	if os.path.exists(out_path):
		return out_path

	try:
		_render_highlight(highlight, book, out_path)
	except Exception as exc:
		log(f"[highlight_images] render failed for "
		    f"{highlight.source}/{highlight.book_id}: {exc}")
		# Clean up partial write if any.
		if os.path.exists(out_path):
			try:
				os.remove(out_path)
			except OSError:
				pass
		return ""
	return out_path


# ---------------------------------------------------------------------------
# Renderer.
# ---------------------------------------------------------------------------
def _render_highlight(h, book, out_path):
	body_font = _load_font(_SERIF_CANDIDATES, 30)
	caption_font = _load_font(_SANS_CANDIDATES, 18)
	footer_font = _load_font(_SANS_CANDIDATES, 20)
	note_font = _load_font(_SANS_CANDIDATES, 22)

	body_lh = _line_height(body_font) + 10
	note_lh = _line_height(note_font) + 8
	footer_lh = _line_height(footer_font)
	caption_lh = _line_height(caption_font)

	max_width = _IMG_W - (2 * _PADDING) - 8  # minus accent stripe

	# ---- measure-pass: lay everything out on a 1x1 scratch canvas so
	#      we know the final height before allocating the real image.
	#      Pillow's `textlength` doesn't need a sized canvas; we just
	#      need *a* Draw object to call the metrics on.
	scratch = Image.new("RGB", (1, 1), _BG)
	sdraw = ImageDraw.Draw(scratch)

	caption_bits = []
	if h.style and h.style != "highlight":
		caption_bits.append(h.style.upper())
	if h.created:
		caption_bits.append(h.created)
	caption_text = "   ·   ".join(caption_bits) if caption_bits else ""

	body_text = _normalize_body(h.text or h.note or h.display_text)
	body_lines = _wrap_for_font(sdraw, body_text, body_font, max_width)

	# Cap absurdly long highlights (> ~40 lines of body text). This
	# keeps rendering snappy and file sizes sane for pathological
	# inputs (someone highlights a whole chapter).
	body_max_lines = (_IMG_H_MAX - _IMG_H_MIN) // body_lh + 10
	truncated = False
	if len(body_lines) > body_max_lines:
		body_lines = body_lines[:body_max_lines]
		truncated = True

	note_lines = []
	if h.note and h.text:
		note_lines = _wrap_for_font(
			sdraw, _normalize_body(f"— note: {h.note}"), note_font, max_width,
		)[:6]

	footer_bits = []
	if book is not None:
		if getattr(book, "title", ""):
			footer_bits.append(book.title)
		if getattr(book, "author", ""):
			footer_bits.append(book.author)
	if h.source:
		footer_bits.append(h.source)
	footer_text = "   ·   ".join(footer_bits)

	# ---- compute final canvas height from what we actually measured.
	h_total = _PADDING
	if caption_text:
		h_total += caption_lh + _CAPTION_GAP
	h_total += body_lh * len(body_lines)
	if note_lines:
		h_total += _NOTE_GAP + (note_lh * len(note_lines))
	if footer_text:
		h_total += _BODY_GAP + footer_lh
	h_total += _PADDING

	img_h = max(_IMG_H_MIN, min(_IMG_H_MAX, h_total))

	# ---- draw-pass: real canvas at the computed height.
	image = Image.new("RGB", (_IMG_W, img_h), _BG)
	draw = ImageDraw.Draw(image)

	# Accent stripe down the left edge.
	draw.rectangle([(0, 0), (8, img_h)], fill=_ACCENT)

	y = _PADDING
	if caption_text:
		draw.text((_PADDING, y), caption_text, font=caption_font, fill=_MUTED)
		y += caption_lh + _CAPTION_GAP

	# If the precomputed height got clamped to _IMG_H_MAX, re-trim the
	# body lines to what actually fits so we don't overflow the footer.
	reserved_for_tail = 0
	if note_lines:
		reserved_for_tail += _NOTE_GAP + note_lh * len(note_lines)
	if footer_text:
		reserved_for_tail += _BODY_GAP + footer_lh
	reserved_for_tail += _PADDING
	body_budget = img_h - y - reserved_for_tail
	max_body_lines = max(1, body_budget // body_lh)
	if len(body_lines) > max_body_lines:
		body_lines = body_lines[:max_body_lines]
		truncated = True

	if truncated and body_lines:
		while body_lines and draw.textlength(
			body_lines[-1] + " …", font=body_font
		) > max_width:
			body_lines[-1] = body_lines[-1][:-1]
		body_lines[-1] = body_lines[-1].rstrip() + " …"

	for line in body_lines:
		draw.text((_PADDING + 8, y), line, font=body_font, fill=_FG)
		y += body_lh

	if note_lines:
		y += _NOTE_GAP
		for line in note_lines:
			draw.text((_PADDING + 8, y), line, font=note_font, fill=_MUTED)
			y += note_lh

	if footer_text:
		fy = img_h - _PADDING - footer_lh
		while draw.textlength(footer_text, font=footer_font) > max_width and len(footer_text) > 40:
			footer_text = footer_text[:-1]
		draw.text((_PADDING + 8, fy), footer_text, font=footer_font, fill=_MUTED)

	# Frame.
	draw.rectangle(
		[(0, 0), (_IMG_W - 1, img_h - 1)],
		outline=_BORDER, width=_BORDER_W,
	)

	image.info["dpi"] = _DPI
	# Atomic write: render to a temp sibling and rename, so a killed
	# generation doesn't leave a half-written JPG that we'd then
	# happily serve as a QuickLook preview. quality=85 is the sweet
	# spot for text on flat backgrounds (no visible ringing, ~25%
	# smaller than the old q=92).
	tmp_path = out_path + ".tmp"
	image.save(tmp_path, "JPEG", dpi=(_DPI, _DPI), quality=85, optimize=True)
	os.replace(tmp_path, out_path)
