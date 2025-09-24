# Changelog

All notable changes to the EPUB Search Tool project.

## [1.0.0] - 2025-09-24

### Added
- **Docopt integration** for clean command-line interface
- **Progress visualization** with counters and progress bars
  - Numeric progress: `(19/47)`
  - Visual progress bar: `|-------x----|`
- **Single book search mode** with `--book` option
- **Flexible output control**:
  - `--epub` flag for modified EPUB generation
  - `--markdown` flag for markdown reports (default: enabled)
  - `--group` flag for grouping results by book
- **Enhanced EPUB support** for macOS Books app bundles
- **Auto-generated output filenames** with timestamps
- **Comprehensive documentation** (README.md, QUICK_REFERENCE.md)

### Enhanced
- **Path expansion** for tilde (`~`) in file paths
- **Error handling** with detailed error messages
- **Search progress feedback** during processing
- **Context word control** with `--context` option
- **Help system** with detailed examples and explanations

### Fixed
- **EPUB bundle detection** - now works with macOS Books app directory structure
- **File path handling** - proper expansion of user home directory
- **Progress counting** - accurate book processing counters

### Technical Improvements
- Migrated from `argparse` to `docopt` for better UX
- Added visual progress bars with 20-character width
- Improved error reporting and debugging information
- Enhanced search result formatting and context extraction

### Dependencies
- Added `docopt>=0.6.2` for command-line parsing
- Maintained compatibility with existing dependencies:
  - `ebooklib>=0.18`
  - `beautifulsoup4>=4.11.0`

### Known Issues
- EPUB generation (`--epub` flag) has a minor issue with file processing
- Workaround: Use markdown-only output until EPUB generation is fixed

---

## Development Notes

### Future Enhancements
- [ ] Fix EPUB generation functionality
- [ ] Add fuzzy search capabilities
- [ ] Implement regex search patterns
- [ ] Add CSV/JSON output formats
- [ ] Include image and metadata search
- [ ] Add batch search with multiple terms

### Performance Optimizations
- [ ] Parallel processing for multiple files
- [ ] Caching for repeated searches
- [ ] Memory optimization for large EPUB files
- [ ] Progress persistence for interrupted searches