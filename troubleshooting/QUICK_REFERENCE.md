# EPUB Search Tool - Quick Reference

## Basic Commands
```bash
# Show help
python searchEPUB.py --help

# Basic search
python searchEPUB.py "search term"

# Search specific book
python searchEPUB.py "text" --book="path/to/book.epub"
```

## Common Options
```bash
--context=N          # Set context words (default: 10)
--folder="path"      # Search different folder
--output="file.md"   # Custom output filename
--epub               # Generate highlighted EPUB
--markdown           # Generate markdown (default: on)
```

## Quick Examples
```bash
# Academic research
python searchEPUB.py "Darwin" --context=20

# Literature analysis
python searchEPUB.py "love" --folder="~/Books/Romance"

# Technical search
python searchEPUB.py "API" --book="manual.epub" --context=15

# Full output
python searchEPUB.py "Einstein" --epub --markdown --context=25
```

## Default Locations
- **macOS Books**: `~/Library/Containers/com.apple.BKAgentService/Data/Documents/iBooks/Books`
- **Custom folder**: Use `--folder="path"`
- **Output files**: Auto-generated with timestamp in search folder

## Progress Display
```
(15/47) |-----x------------| Searching in: book.epub
  Found 23 matches in 'Book Title'
```

## File Support
- Standard EPUB files: `book.epub`
- EPUB bundles (macOS): `book.epub/`
- Both EPUB 2.0 and 3.0 formats