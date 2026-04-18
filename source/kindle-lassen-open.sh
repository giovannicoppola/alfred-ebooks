#!/bin/bash
# Open a specific book in the new Kindle for Mac app (Lassen) from Alfred.
#
# Lassen exposes no deep-link / URL / file-open mechanism for "open this
# specific book": kindle://, read.amazon.com/application/*, /gp/r.html, and
# `open -a` on local BookManifest.kfx / .azw8 all just foreground the app.
# There's no AppleScript dictionary, and Catalyst hides the view hierarchy
# from the Accessibility API, so covers can't be targeted by AX role/label.
# What does work is a UI-automation sequence:
#   1. Foreground Kindle
#   2. Detect state by walking the window's AX tree for any AXTextField:
#      library views (regular grid, search-results sub-state, etc.) expose
#      at least one text field; reader view's AX tree contains only opaque
#      AXGroups + window-chrome buttons. This is flicker-free, unlike
#      probing with Cmd+F which would briefly pop the in-book search in
#      reader view.
#   3. If we're in reader view, summon the auto-hiding top toolbar by
#      sliding the cursor into it and click the back-arrow at its left
#      edge to return to the library; then re-poll the AX tree until a
#      text field appears.
#   4. Click the search text field at its AX-reported center to focus it.
#      We avoid Cmd+F because it's a no-op once the library is in
#      search-results sub-state, and Catalyst ignores AX SetFocused.
#   5. Cmd+A + Delete clears any previous query, then type the book title
#      and Return filters the library to that book.
#   6. Quartz-posted double-click on the first grid cell opens the book.
# AppleScript's `click at` and `click menu item` are silently dropped by
# Kindle's Catalyst UI when the caller's TCC attribution is weak; Quartz
# CGEventPost events posted to the HID tap behave like real hardware input
# and survive. The cursor slide that summons the toolbar must be a stream
# of small CGEventMouseMoved events — Catalyst's hover detection ignores
# teleported cursor positions. No keyboard shortcut (Esc, Cmd+W, Cmd+0/1/L,
# Cmd+Opt+Left, Cmd+[) returns from reader to library; only the back-arrow
# click does.
#
# Requires Alfred to have Accessibility permission
# (System Settings > Privacy & Security > Accessibility).
#
# Alfred arg format: kindle-lassen-open|<ASIN>|<TITLE>
# TITLE may contain pipes; everything after the first two pipes is kept.
#
# Caveats:
# - The book-open click coordinate is a heuristic (30% x 22% of the
#   window). If your library layout differs, adjust the ratios near the
#   end of this script.
# - The back-arrow click is at (winX+30, winY+55), which assumes the
#   default Kindle reader toolbar layout.
#
# Troubleshoot log: /tmp/alfred-kindle-lassen.log

set -u

input="${1:-}"
if [[ "$input" != kindle-lassen-open\|* ]]; then
  echo "alfred-kindle: expected kindle-lassen-open|<ASIN>|<TITLE>, got: ${input}" >&2
  exit 1
fi

rest="${input#kindle-lassen-open|}"
asin="${rest%%|*}"
if [[ "$rest" == *"|"* ]]; then
  title="${rest#*|}"
else
  title=""
fi

if [[ -z "$asin" ]]; then
  echo "alfred-kindle: empty ASIN" >&2
  exit 1
fi

kindle_app=""
for cand in "/Applications/Amazon Kindle.app" "/Applications/Kindle.app"; do
  if [[ -d "$cand" ]]; then
    kindle_app=$cand
    break
  fi
done
if [[ -z "$kindle_app" ]]; then
  open "https://www.amazon.com/dp/${asin}"
  exit 0
fi

if [[ -z "$title" ]]; then
  open -a "$kindle_app"
  exit 0
fi

# Use the full title (capped at 60 chars) so colon/dash subtitles, which
# are often what disambiguates similarly-named books, are preserved.
query="${title:0:60}"

LOG=/tmp/alfred-kindle-lassen.log
OSASCRIPT=$(command -v osascript || echo /usr/bin/osascript)

# Pre-launch via LaunchServices. `tell application ... to activate` inside
# osascript is too weak to steal focus from an Alfred subprocess; the
# AppleScript below force-foregrounds Kindle via System Events.
open -a "$kindle_app"

"$OSASCRIPT" - "$query" <<'OSA' >>"$LOG" 2>&1
global foundTextField, textFieldRef

-- Recursive AX walk that early-exits on the first AXTextField. Used to
-- distinguish library state (any text field is exposed somewhere in the
-- AX tree) from reader state (Catalyst hides everything inside the
-- reader, leaving only opaque AXGroups + window-chrome buttons), and to
-- capture a reference to the field so we can focus it directly.
on hasTextField(elem, depth, maxDepth)
    if foundTextField then return
    if depth > maxDepth then return
    tell application "System Events"
        try
            if (role of elem) is "AXTextField" then
                set foundTextField to true
                set textFieldRef to elem
                return
            end if
        end try
        try
            repeat with k in (UI elements of elem)
                my hasTextField(k, depth + 1, maxDepth)
                if foundTextField then return
            end repeat
        end try
    end tell
end hasTextField

on run argv
    set theQuery to item 1 of argv
    set t to (do shell script "date '+%Y-%m-%d %H:%M:%S'")
    log "[" & t & "] lassen-open query=" & theQuery

    tell application "Amazon Kindle" to activate

    -- Wait for the Kindle process to exist and become frontmost (up to ~3 s).
    tell application "System Events"
        set tries to 0
        repeat while not (exists (process "Kindle")) and tries < 30
            delay 0.1
            set tries to tries + 1
        end repeat
        set tries to 0
        repeat until (name of first application process whose frontmost is true) is "Kindle" or tries > 20
            try
                set frontmost of process "Kindle" to true
            end try
            delay 0.1
            set tries to tries + 1
        end repeat
    end tell
    delay 0.3

    tell application "System Events"
        tell process "Kindle"
            set pos to position of window 1
            set sz to size of window 1
        end tell
    end tell
    set winX to item 1 of pos
    set winY to item 2 of pos
    set winW to item 1 of sz
    set winH to item 2 of sz

    -- Detect state by scanning the AX tree for any text field. This avoids
    -- the in-book-search flicker that probing with Cmd+F would cause when
    -- a book is open: in reader view Cmd+F opens the in-book search
    -- popover (which we'd then have to dismiss with Esc). Capture the
    -- field reference so we can focus it directly without Cmd+F (which
    -- doesn't always re-focus when the library is in search-results
    -- sub-state).
    set foundTextField to false
    set textFieldRef to missing value
    tell application "System Events"
        set rootWin to window 1 of process "Kindle"
    end tell
    my hasTextField(rootWin, 0, 14)
    set onLibrary to foundTextField

    if not onLibrary then
        log "  not on library; clicking back-arrow to exit reader view"
        -- Summon the auto-hiding top toolbar by sliding the cursor into it,
        -- then click the back-arrow at its very left edge. Catalyst's hover
        -- detection ignores teleported cursor positions, so the slide must
        -- be a stream of small CGEventMouseMoved events.
        do shell script "/usr/bin/python3 - " & winX & " " & winY & " " & winW & " " & winH & " <<'PY'
import sys, time, Quartz as Q
wx, wy, ww, wh = (float(a) for a in sys.argv[1:5])
def move(x, y):
    Q.CGEventPost(Q.kCGHIDEventTap,
        Q.CGEventCreateMouseEvent(None, Q.kCGEventMouseMoved, (x, y), Q.kCGMouseButtonLeft))
def click(x, y):
    move(x, y); time.sleep(0.05)
    Q.CGEventPost(Q.kCGHIDEventTap,
        Q.CGEventCreateMouseEvent(None, Q.kCGEventLeftMouseDown, (x, y), Q.kCGMouseButtonLeft))
    Q.CGEventPost(Q.kCGHIDEventTap,
        Q.CGEventCreateMouseEvent(None, Q.kCGEventLeftMouseUp,   (x, y), Q.kCGMouseButtonLeft))
target_x = wx + ww/2
start_y, end_y = wy - 50, wy + 60
steps = 20
for i in range(steps + 1):
    move(target_x, start_y + (end_y - start_y) * i / steps)
    time.sleep(0.015)
for dx in (0, -50, 50, 0):
    move(target_x + dx, end_y)
    time.sleep(0.08)
time.sleep(0.5)
click(wx + 30, wy + 55)
time.sleep(0.2)
move(wx + ww/2, wy + wh/2)
PY"
        -- Wait for the library to render. The back-arrow transition can
        -- take up to a couple of seconds; poll the AX tree for a text
        -- field rather than guessing a fixed delay.
        set tries to 0
        repeat until onLibrary or tries > 20
            delay 0.2
            set foundTextField to false
            set textFieldRef to missing value
            try
                my hasTextField(rootWin, 0, 14)
            end try
            set onLibrary to foundTextField
            set tries to tries + 1
        end repeat
        if not onLibrary then
            log "  WARN: library never rendered after back-arrow; aborting"
            return
        end if
    end if

    -- Focus the search text field by clicking on it. Cmd+F only works in
    -- the regular library state; once the library is in search-results
    -- sub-state (a previous query is still showing) Cmd+F is a no-op,
    -- and Catalyst ignores AX SetFocused. A coordinate click on the
    -- field's AX-reported center reliably grabs focus in both sub-states.
    if textFieldRef is missing value then
        log "  WARN: no text field reference captured"
        return
    end if
    set tfX to 0
    set tfY to 0
    try
        tell application "System Events"
            tell process "Kindle"
                set tfPos to position of textFieldRef
                set tfSz to size of textFieldRef
            end tell
        end tell
        set tfX to (item 1 of tfPos) + ((item 1 of tfSz) / 2)
        set tfY to (item 2 of tfPos) + ((item 2 of tfSz) / 2)
        log "  focusing search field at " & tfX & "," & tfY
    on error errMsg
        log "  WARN: failed to read text-field rect: " & errMsg
        return
    end try
    do shell script "/usr/bin/python3 - " & tfX & " " & tfY & " <<'PY'
import sys, time, Quartz as Q
x, y = float(sys.argv[1]), float(sys.argv[2])
Q.CGEventPost(Q.kCGHIDEventTap,
    Q.CGEventCreateMouseEvent(None, Q.kCGEventMouseMoved, (x, y), Q.kCGMouseButtonLeft))
time.sleep(0.05)
Q.CGEventPost(Q.kCGHIDEventTap,
    Q.CGEventCreateMouseEvent(None, Q.kCGEventLeftMouseDown, (x, y), Q.kCGMouseButtonLeft))
Q.CGEventPost(Q.kCGHIDEventTap,
    Q.CGEventCreateMouseEvent(None, Q.kCGEventLeftMouseUp,   (x, y), Q.kCGMouseButtonLeft))
PY"
    delay 0.3

    -- Clear any pre-existing text in the search field before typing.
    tell application "System Events"
        keystroke "a" using {command down}
        key code 51 -- delete
    end tell
    delay 0.1

    -- Type the title, then commit the search to filter the library.
    tell application "System Events"
        keystroke theQuery
    end tell
    delay 0.4
    tell application "System Events"
        key code 36 -- Return
    end tell
    delay 0.5

    -- Open the first filtered result with a Quartz-posted double-click on
    -- the first grid cell. The Catalyst UI swallows `click at` and any
    -- keyboard "open selected" input (Return beeps, Space/arrows do
    -- nothing), but Quartz HID events behave like real mouse input.
    set clickX to winX + (winW * 0.3)
    set clickY to winY + (winH * 0.22)

    try
        do shell script "/usr/bin/python3 - '" & clickX & "' '" & clickY & "' <<'PY'
import sys, time, Quartz as Q
x = float(sys.argv[1]); y = float(sys.argv[2])
p = (x, y)
for i in (1, 2):
    d = Q.CGEventCreateMouseEvent(None, Q.kCGEventLeftMouseDown, p, Q.kCGMouseButtonLeft)
    u = Q.CGEventCreateMouseEvent(None, Q.kCGEventLeftMouseUp,   p, Q.kCGMouseButtonLeft)
    Q.CGEventSetIntegerValueField(d, Q.kCGMouseEventClickState, i)
    Q.CGEventSetIntegerValueField(u, Q.kCGMouseEventClickState, i)
    Q.CGEventPost(Q.kCGHIDEventTap, d)
    Q.CGEventPost(Q.kCGHIDEventTap, u)
    time.sleep(0.05)
PY"
    on error errMsg number errNum
        log "double-click failed (err " & errNum & "): " & errMsg
    end try
end run
OSA

exit 0
