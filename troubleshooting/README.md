# EPUB Search Tool

A powerful Python tool for searching text within EPUB files and generating results in markdown format with optional highlighted EPUB outputs.

## Features

- 🔍 **Full-text search** across single EPUB files or entire directories
- 📊 **Progress visualization** with counters and progress bars
- 📝 **Markdown reports** with context around matches
- 📚 **Modified EPUB generation** with highlighted search results
- 🎯 **Flexible context control** around search matches
- 📁 **Batch processing** of multiple EPUB files
- 🎨 **Clean command-line interface** with docopt

## Installation

### Prerequisites

- Python 3.7 or higher
- Virtual environment (recommended)

### Setup

1. **Clone or download the project files**
2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # or
   venv\Scripts\activate     # On Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Dependencies

The tool requires these Python packages:
- `ebooklib>=0.18` - For reading and processing EPUB files
- `beautifulsoup4>=4.11.0` - For parsing HTML content
- `docopt>=0.6.2` - For command-line argument parsing

## Usage

### Basic Commands

```bash
# Show help
python searchEPUB.py --help

# Basic search in default folder
python searchEPUB.py "Einstein"

# Search single EPUB file
python searchEPUB.py "quantum physics" --book="path/to/book.epub"

# Search with custom context
python searchEPUB.py "Shakespeare" --context=15
```

### Command-Line Options

```
Usage:
  searchEPUB.py <search_text> [--folder=<path>] [--book=<file>] [--context=<n>] [--output=<file>] [--epub] [--markdown] [--group]
  searchEPUB.py -h | --help
  searchEPUB.py --version

Arguments:
  <search_text>         Text to search for in EPUB files

Options:
  -h --help            Show this screen
  --version            Show version
  --folder=<path>      Folder containing EPUB files [default: ~/Library/Containers/com.apple.BKAgentService/Data/Documents/iBooks/Books]
  --book=<file>        Search in a single EPUB file instead of folder
  --context=<n>        Number of context words around match [default: 10]
  --output=<file>      Output markdown file path (auto-generated if not specified)
  --epub               Generate modified EPUB files with search results
  --markdown           Generate markdown file with search results [default: True]
  --group              Group results by book in markdown output [default: True]
```

### Advanced Examples

```bash
# Generate both markdown and EPUB outputs
python searchEPUB.py "artificial intelligence" --epub --markdown --context=20

# Search specific folder with custom output
python searchEPUB.py "machine learning" --folder="~/Documents/Books" --output="ml_results.md"

# Search without markdown output (console only)
python searchEPUB.py "neural networks" --context=5

# Single book search with detailed context
python searchEPUB.py "quantum mechanics" --book="~/Books/physics.epub" --context=25
```

## Default Behavior

- **Default folder**: `~/Library/Containers/com.apple.BKAgentService/Data/Documents/iBooks/Books` (macOS Books app)
- **Default context**: 10 words before and after each match
- **Default output**: Auto-generated markdown file with timestamp
- **Progress display**: Shows counter and visual progress bar during search

## Output Formats

### Markdown Report

The tool generates comprehensive markdown reports containing:
- Search summary with total matches found
- Results grouped by book (when `--group` is enabled)
- Context around each match with **highlighted search terms**
- Chapter/section information for each match

Example output structure:
```markdown
# Search Results for "Einstein"

## Summary
- Total matches found: 42
- Books searched: 15
- Search completed: 2025-09-24 10:30:15

## Results by Book

### Book: "The Elegant Universe"
**Einstein** found in *Chapter 3: Relativity*:
> Albert **Einstein** revolutionized our understanding of space and time...
```

### Modified EPUB Files (Optional)

When `--epub` flag is used, the tool creates modified EPUB files with:
- Highlighted search terms in yellow background
- New summary chapter with all search results
- Original content preserved with visual markers

## Progress Visualization

The tool provides real-time feedback during searches:

```
Found 47 EPUB files to search

(1/47) |--------------------| Searching in: book1.epub
  Found 12 matches in 'Book Title 1'

(25/47) |----------x---------| Searching in: book25.epub
  Found 3 matches in 'Book Title 25'

(47/47) |-------------------x| Searching in: book47.epub
  No matches found in 'Book Title 47'

Search complete. Processed 47 books.
Total matches found: 156
```

## File Structure Support

The tool handles both:
- **Standard EPUB files**: `book.epub`
- **EPUB bundles**: `book.epub/` (common on macOS Books app)

## Configuration

### Default Settings

You can modify default settings by editing the constants in `searchEPUB.py`:

```python
DEFAULT_EPUB_FOLDER = "~/Library/Containers/com.apple.BKAgentService/Data/Documents/iBooks/Books"
DEFAULT_CONTEXT_WORDS = 10
```

### Custom Folders

For different EPUB collections:

```bash
# Academic books
python searchEPUB.py "research" --folder="~/Documents/Academic"

# Fiction collection  
python searchEPUB.py "character" --folder="~/Books/Fiction"
```

## Troubleshooting

### Common Issues

1. **"No EPUB files found"**
   - Check folder path exists and contains EPUB files
   - Verify permissions to read the directory
   - Try absolute paths instead of relative ones

2. **"Error processing book.epub"**
   - EPUB file may be corrupted or have missing components
   - Check if file is actually an EPUB (some files have wrong extensions)

3. **"Permission denied"**
   - Ensure read permissions for EPUB files and directories
   - On macOS, may need to grant terminal access to Documents

### Debugging

Enable verbose output by checking file permissions:
```bash
ls -la "~/Library/Containers/com.apple.BKAgentService/Data/Documents/iBooks/Books"
```

### Performance Tips

- Use `--context` with smaller values for faster searches
- Use `--book` for single file searches when you know the target
- Disable `--epub` generation for faster searches (markdown only)

## Technical Details

### Supported Formats

- **EPUB 2.0** and **EPUB 3.0** files
- **HTML-based content** within EPUB files
- **UTF-8 encoded text**

### Search Algorithm

- Case-insensitive text matching
- Word boundary respect for context extraction
- HTML tag stripping for clean text search
- Regex-based pattern matching

### Output Encoding

- **Markdown files**: UTF-8 encoding
- **Modified EPUBs**: Preserve original encoding
- **Console output**: System default encoding

## Examples by Use Case

### Academic Research
```bash
# Find all references to a researcher
python searchEPUB.py "Darwin" --folder="~/Research/Biology" --context=15

# Search for methodology references
python searchEPUB.py "statistical analysis" --epub --markdown
```

### Literature Analysis
```bash
# Character analysis across books
python searchEPUB.py "Hamlet" --folder="~/Books/Shakespeare" --group

# Theme exploration
python searchEPUB.py "love" --context=20 --output="love_themes.md"
```

### Technical Documentation
```bash
# API reference search
python searchEPUB.py "authentication" --book="api_docs.epub" --context=25

# Code example search
python searchEPUB.py "function" --folder="~/Docs/Programming"
```

## Version History

- **v1.0** - Initial release with docopt interface
- **Progress bars** and enhanced user experience
- **EPUB bundle support** for macOS Books app
- **Flexible output options** and context control

## License

This tool is provided as-is for educational and research purposes.

## Contributing

Feel free to submit issues, feature requests, or improvements to enhance the tool's functionality.