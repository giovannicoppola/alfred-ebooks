"""EPUB Search Tool v1.0

A powerful tool for searching text within EPUB files and generating comprehensive
reports with highlighted results and progress visualization.

FEATURES:
  • Full-text search across single files or directories
  • Automatic proximity search for 2-word queries (e.g., "love death")
  • Real-time progress with visual bars: (15/47) |-----x------------|
  • Markdown reports with context around matches
  • Optional highlighted EPUB generation
  • Support for EPUB files and macOS Books app bundles
  • Alfred workflow integration with drill-down functionality

Usage:
  searchEPUB.py <search_text> [--folder=<path>] [--book=<file>] [--context=<n>] [--output=<file>] [--proximity=<n>] [--epub] [--markdown] [--group] [--alfred]
  searchEPUB.py -h | --help
  searchEPUB.py --version

Arguments:
  <search_text>         Text to search for (case-insensitive)
                       • 1 word: exact text matching (fast)
                       • 2 words: automatic proximity search (finds words within distance)
                       • 3+ words: exact phrase matching (fast)

Options:
  -h --help            Show this detailed help screen
  --version            Show version information
  --folder=<path>      Folder containing EPUB files 
                       [default: ~/Library/Containers/com.apple.BKAgentService/Data/Documents/iBooks/Books]
  --book=<file>        Search in a single EPUB file instead of folder
  --context=<n>        Number of context words around each match [default: 10]
  --proximity=<n>      Maximum word distance for 2-word proximity search [default: 100]
                       Examples: 25=same paragraph, 50=nearby, 100=same section, 200=same chapter
  --output=<file>      Output markdown file path (auto-generated with timestamp if not specified)
  --epub               Generate modified EPUB files with highlighted search results
  --markdown           Generate markdown file with search results [default: enabled]
  --group              Group results by book in markdown output [default: enabled]
  --alfred             Output results in Alfred JSON format for workflow integration

BASIC EXAMPLES:
  searchEPUB.py "Einstein"
    Search all books in default folder for "Einstein"

  searchEPUB.py "Darwin" --context=20
    Search with 20 words of context around each match

  searchEPUB.py "machine learning" --book="~/ai_textbook.epub"
    Search only in a specific EPUB file

PROXIMITY SEARCH EXAMPLES:
  searchEPUB.py "love death"
    Find "love" within 100 words of "death" (automatic 2-word proximity)

  searchEPUB.py "king battle" --proximity=50
    Find "king" within 50 words of "battle"

  searchEPUB.py "peace war" --proximity=25 --alfred
    Proximity search with Alfred JSON output

ADVANCED EXAMPLES:
  searchEPUB.py "neural networks" --epub --markdown --context=15
    Generate both highlighted EPUB and markdown report (exact phrase search)

  searchEPUB.py "Shakespeare" --folder="~/Literature" --output="shakespeare_analysis.md"
    Search custom folder with specific output filename

  searchEPUB.py "quantum" --context=5
    Quick search with minimal context (console output only)

  searchEPUB.py "artificial intelligence" --proximity=75 --context=20
    Find AI-related concepts with custom proximity and context

ALFRED WORKFLOW EXAMPLES:
  searchEPUB.py "Einstein" --alfred --context=5
    Output JSON for Alfred workflow integration (exact match)

  searchEPUB.py "Darwin evolution" --alfred --proximity=50
    Proximity search with Alfred JSON output (Darwin within 50 words of evolution)

  searchEPUB.py "machine learning" --book="specific.epub" --alfred
    Search single book with Alfred JSON output (exact phrase)

  searchEPUB.py "love death" --alfred
    Auto-proximity search in Alfred (love within 100 words of death)

SEARCH MODE BEHAVIOR:
  • "shakespeare" → Exact text search (fast)
  • "love death" → Proximity search (finds "love...death" within 100 words)  
  • "to be or not" → Exact phrase search (fast)
  • Use --proximity=N to control word distance for 2-word searches

OUTPUT FORMATS:
  • Markdown: Comprehensive report with matches grouped by book
  • Modified EPUB: Original files with highlighted search terms
  • Alfred JSON: Structured format for Alfred workflow results
  • Console: Real-time progress and summary statistics

PROGRESS DISPLAY:
  (15/47) |-----x------------| Searching in: book_title.epub
    Found 23 matches in 'Book Title'

For detailed documentation, see README.md
"""

import glob
import json
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import uuid

import ebooklib
from bs4 import BeautifulSoup
from docopt import docopt
from ebooklib import epub

# Yomu keeps each book as an unpacked EPUB bundle inside its sandbox.
# We resolve `yomu-open|…` tokens against this directory. Importing from
# config keeps the path override (`YOMU_EPUB_CACHE_DIR` env var, sandbox
# ID override) in one place; falling back keeps searchEPUB.py runnable
# on its own for ad-hoc CLI use without the Alfred workflow.
try:
    from config import YOMU_EPUB_CACHE_DIR
except Exception:
    YOMU_EPUB_CACHE_DIR = os.path.expanduser(
        "~/Library/Containers/net.cecinestpasparis.yomu"
        "/Data/Library/Caches/EBook/EPub"
    )

# Default settings
DEFAULT_EPUB_FOLDER = "~/Library/Containers/com.apple.BKAgentService/Data/Documents/iBooks/Books"
DEFAULT_EPUB_FOLDER = "~/Library/Mobile Documents/iCloud~com~apple~iBooks/Documents/"
DEFAULT_CONTEXT_WORDS = 10


def simple_tokenize(text):
    """Simple tokenizer that splits text into words, preserving positions."""
    import re
    words = []
    positions = []
    
    # Find all word matches with their positions
    for match in re.finditer(r'\b\w+\b', text.lower()):
        words.append(match.group())
        positions.append(match.start())
    
    return words, positions


def find_proximity_matches(text, word1, word2, max_distance=100):
    """
    Find matches where word1 and word2 appear within max_distance words of each other.
    
    Returns:
        List of tuples: (match_start_pos, match_end_pos, context_snippet)
    """
    tokens, token_positions = simple_tokenize(text)
    
    # Find all positions of both words
    word1_indices = [i for i, token in enumerate(tokens) if token == word1.lower()]
    word2_indices = [i for i, token in enumerate(tokens) if token == word2.lower()]
    
    matches = []
    
    for pos1 in word1_indices:
        for pos2 in word2_indices:
            distance = abs(pos1 - pos2)
            if distance <= max_distance and distance > 0:  # Don't match the same word
                # Get the span of the match in original text
                start_token_idx = min(pos1, pos2)
                end_token_idx = max(pos1, pos2)
                
                # Convert token positions back to character positions
                start_char_pos = token_positions[start_token_idx]
                end_char_pos = token_positions[end_token_idx] + len(tokens[end_token_idx])
                
                # Create context snippet
                context_start = max(0, start_token_idx - 10)
                context_end = min(len(tokens), end_token_idx + 10)
                context_tokens = tokens[context_start:context_end]
                context_snippet = ' '.join(context_tokens)
                
                matches.append((start_char_pos, end_char_pos, context_snippet, distance))
    
    return matches


def is_proximity_search(search_text):
    """Check if search text contains exactly 2 words (triggers proximity search)."""
    words = search_text.strip().split()
    return len(words) == 2


def search_multiple_epubs(
    folder_path, search_text, context_words=10, create_modified_epubs=True, quiet=False, proximity_distance=100
):
    """
    Search multiple EPUB files in a folder for specific text.

    Parameters:
    - folder_path: Path to folder containing EPUB files
    - search_text: Text to search for
    - context_words: Number of surrounding words to include in results
    - create_modified_epubs: Whether to create modified EPUBs with search results

    Returns:
    - List of search results with book title, chapter, context and markdown representation
    """
    # Expand tilde in folder path
    folder_path = os.path.expanduser(folder_path)
    
    # Find all EPUB files in the folder (both files and directories with .epub extension)
    epub_files = []
    
    # Look for regular .epub files
    epub_files.extend(glob.glob(os.path.join(folder_path, "*.epub")))
    
    # Filter to separate files and directories
    epub_file_list = []
    for item in epub_files:
        if os.path.isfile(item):
            epub_file_list.append(item)
        elif os.path.isdir(item):
            # This is an EPUB bundle (directory), which is common on macOS Books app
            epub_file_list.append(item)
    
    if not epub_file_list:
        if not quiet:
            print(f"No EPUB files found in {folder_path}")
            print(f"Checked for both .epub files and .epub directories")
            # List what's actually in the directory for debugging
            try:
                items = os.listdir(folder_path)
                epub_items = [item for item in items if item.endswith('.epub')]
                if epub_items:
                    print(f"Found {len(epub_items)} items with .epub extension:")
                    for item in epub_items[:5]:  # Show first 5
                        item_path = os.path.join(folder_path, item)
                        if os.path.isdir(item_path):
                            print(f"  {item} (directory)")
                        else:
                            print(f"  {item} (file)")
                    if len(epub_items) > 5:
                        print(f"  ... and {len(epub_items) - 5} more")
            except Exception as e:
                print(f"Could not list directory contents: {e}")
        return []
    
    epub_files = epub_file_list

    if not quiet:
        print(f"Found {len(epub_files)} EPUB files to search")

    all_results = []
    processed_books = 0
    total_books = len(epub_files)

    # Process each EPUB file
    for epub_file in epub_files:
        try:
            processed_books += 1
            book_filename = os.path.basename(epub_file)
            
            # Create progress bar
            progress_bar_width = 20  # Total width of the progress bar
            progress_position = int((processed_books / total_books) * progress_bar_width)
            
            # Build the progress bar string
            bar = "|"
            for i in range(progress_bar_width):
                if i == progress_position - 1:  # Current position (x)
                    bar += "x"
                elif i < progress_position:     # Completed portion (-)
                    bar += "-"
                else:                          # Remaining portion (-)
                    bar += "-"
            bar += "|"
            
            if not quiet:
                print(f"\n({processed_books}/{total_books}) {bar} Searching in: {book_filename}")

            # Read the EPUB
            book = epub.read_epub(epub_file)

            # Get book title
            book_title = book.get_metadata("DC", "title")
            if book_title and len(book_title) > 0 and len(book_title[0]) > 0:
                book_title = book_title[0][0]
            else:
                book_title = os.path.splitext(book_filename)[0]

            # Track results for this book
            book_results = []
            
            # Build a mapping of file names to chapter titles from TOC
            toc_mapping = {}
            try:
                for item in book.toc:
                    if hasattr(item, 'href') and hasattr(item, 'title'):
                        # Clean up the href to match file names
                        file_name = item.href.split('#')[0]  # Remove fragment
                        toc_mapping[file_name] = item.title
                    elif isinstance(item, tuple) and len(item) >= 2:
                        # Handle different TOC formats
                        if hasattr(item[1], 'href'):
                            file_name = item[1].href.split('#')[0]
                            toc_mapping[file_name] = item[0]
            except:
                # TOC extraction failed, continue without it
                pass

            # Process each HTML item in the book
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    content = item.get_content().decode("utf-8")
                    soup = BeautifulSoup(content, "html.parser")

                    # Get chapter title - try TOC first, then HTML title, then filename
                    chapter_title = None
                    file_name = item.get_name()
                    
                    # Try to get from TOC mapping
                    if file_name in toc_mapping:
                        chapter_title = toc_mapping[file_name]
                    
                    # If no TOC entry, try HTML title tag
                    if not chapter_title:
                        title_tag = soup.find("title")
                        if title_tag and title_tag.get_text().strip():
                            chapter_title = title_tag.get_text().strip()
                    
                    # Fallback to filename
                    if not chapter_title:
                        chapter_title = file_name

                    # Plain text for searching, with block-level breaks
                    # preserved so the excerpt carries paragraph /
                    # heading boundaries instead of welding them into
                    # one stream.
                    text_content = _html_to_block_text(soup)

                    # Check if this is a 2-word proximity search
                    if is_proximity_search(search_text):
                        words_to_search = search_text.strip().split()
                        word1, word2 = words_to_search[0], words_to_search[1]
                        
                        # Use proximity matching
                        proximity_matches = find_proximity_matches(text_content, word1, word2, max_distance=proximity_distance)
                        
                        # Convert proximity matches to regular match format
                        matches = []
                        for start_pos, end_pos, context_snippet, distance in proximity_matches:
                            # Create a mock match object for compatibility
                            class MockMatch:
                                def __init__(self, start, end, text):
                                    self._start = start
                                    self._end = end  
                                    self._text = text
                                def start(self): return self._start
                                def end(self): return self._end
                                def group(self): return self._text
                            
                            match_text = f"{word1} ... {word2} ({distance} {'word' if distance == 1 else 'words'} apart)"
                            matches.append(MockMatch(start_pos, end_pos, match_text))
                    else:
                        # Regular exact text search
                        matches = list(
                            re.finditer(re.escape(search_text), text_content, re.IGNORECASE)
                        )

                    if matches:
                        for m_slice_start, m_slice_end, spans in _merge_overlapping_matches(matches, text_content, context_words):
                            match_id = f"match_{uuid.uuid4().hex[:8]}"

                            raw_context = text_content[m_slice_start:m_slice_end]
                            lstripped = raw_context.lstrip()
                            lead_trim = len(raw_context) - len(lstripped)
                            raw_context = lstripped.rstrip()

                            markdown_context = _bold_spans(raw_context, m_slice_start + lead_trim, spans)
                            markdown_string = f"> {markdown_context}\n\n— *{book_title}, {chapter_title}*"

                            match_label = spans[0][2]
                            if len(spans) > 1:
                                match_label += f" (+{len(spans) - 1} more)"

                            result = {
                                "book_title": book_title,
                                "book_filename": book_filename,
                                "chapter": chapter_title,
                                "context": raw_context,
                                "match": match_label,
                                "file": item.get_name(),
                                "id": match_id,
                                "markdown": markdown_string,
                            }

                            book_results.append(result)
                            all_results.append(result)

            # If we found results and want to create modified EPUBs, create one for this book
            if book_results and create_modified_epubs:
                output_path = os.path.join(
                    folder_path,
                    f"{os.path.splitext(book_filename)[0]}_search_{search_text.replace(' ', '_')}.epub",
                )

                # Create a new chapter for search results
                search_results_html = create_search_results_chapter(
                    book, book_title, search_text, book_results
                )
                book.add_item(search_results_html)

                # Add to spine at the beginning
                book.spine.insert(0, search_results_html)

                # Update TOC to include search results
                toc = [
                    epub.Link(
                        "search_results.xhtml",
                        f"Search Results for '{search_text}'",
                        "search_results",
                    )
                ]

                # Add original TOC after search results
                if hasattr(book, "toc"):
                    toc.extend(book.toc)

                book.toc = toc

                # Write the modified EPUB
                epub.write_epub(output_path, book)
                if not quiet:
                    print(
                        f"  Created search results EPUB at: {os.path.basename(output_path)}"
                    )

            if not quiet:
                if book_results:
                    print(f"  Found {len(book_results)} matches in '{book_title}'")
                else:
                    print(f"  No matches found in '{book_title}'")

        except Exception as e:
            if not quiet:
                print(f"Error processing {os.path.basename(epub_file)}: {str(e)}")

    if not quiet:
        print(f"\nSearch complete. Processed {processed_books} books.")
        print(f"Total matches found: {len(all_results):,}")

    return all_results


def create_search_results_chapter(book, book_title, search_text, results):
    """Create a search results chapter for an EPUB book"""
    search_results = epub.EpubHtml(
        title=f"Search Results for '{search_text}'",
        file_name="search_results.xhtml",
        lang="en",
    )

    css = """
    .search-result {
        margin: 1em 0;
        padding: 0.5em;
        border-bottom: 1px solid #ccc;
    }
    .match-text {
        font-weight: bold;
        background-color: #ffff00;
    }
    .result-link {
        color: #0000EE;
        text-decoration: underline;
    }
    .context {
        font-style: italic;
        color: #333;
    }
    """

    # Add CSS
    style = epub.EpubItem(
        uid="search_style",
        file_name="style/search.css",
        media_type="text/css",
        content=css,
    )
    book.add_item(style)

    results_content = f"""
    <html>
    <head>
        <title>Search Results for '{search_text}'</title>
        <link rel="stylesheet" type="text/css" href="style/search.css" />
    </head>
    <body>
        <h1>Search Results for '{search_text}'</h1>
        <p>Book: {book_title}</p>
    """

    for i, result in enumerate(results):
        item_href = result["file"]
        match_id = result["id"]
        chapter_title = result["chapter"]
        context = result["context"]

        # Format the context with highlighted search text
        highlighted_context = context.replace(
            search_text, f'<span class="match-text">{search_text}</span>'
        )

        results_content += f"""
        <div class="search-result">
            <p><a href="{item_href}#{match_id}" class="result-link">Match {i+1} in {chapter_title}</a></p>
            <p class="context">...{highlighted_context}...</p>
        </div>
        """

    results_content += """
    </body>
    </html>
    """
    search_results.content = results_content

    return search_results


def export_alfred_books_overview(results, search_text, progress_info=None):
    """Export book overview for Alfred - one row per book with match counts"""
    import hashlib
    alfred_json = {"items": [], "skipknowledge": True}
    alfred_items = alfred_json["items"]

    # Add rerun for progress updates if search is in progress
    if progress_info and not progress_info.get('is_complete', False):
        alfred_json["rerun"] = 0.5
    
    # Show combined progress and summary if search is in progress
    if progress_info and not progress_info.get('is_complete', False):
        current_book = progress_info.get('current_book', 'Unknown')
        processed = progress_info.get('processed_books', 0)
        total = progress_info.get('total_books', 1)
        
        # Create progress bar
        progress_width = 20
        progress_position = int((processed / total) * progress_width) if total > 0 else 0
        progress_bar = '|'
        for i in range(progress_width):
            if i == progress_position - 1:
                progress_bar += 'x'
            elif i < progress_position:
                progress_bar += '-'
            else:
                progress_bar += '-'
        progress_bar += '|'
        
        # Group results by book to get counts
        books = {}
        total_matches = len(results)
        for result in results:
            book_title = result['book_title']
            if book_title not in books:
                books[book_title] = []
            books[book_title].append(result)
        
        # Combined progress and results summary
        match_text = f"{total_matches:,} matches in {len(books)} books so far" if total_matches > 0 else "No matches yet"
        
        alfred_items.append({
            "uid": "progress",
            "title": f"🔍 Searching ({processed}/{total}) • {match_text}",
            "subtitle": f"{progress_bar} Currently searching: {current_book} — 💤 you can close Alfred and come back in a few minutes",
            "icon": {"path": "icon.png"},
            "valid": False
        })
        
        # Fall through to show results below, don't return early
    
    # Show "no results yet" only if search is complete and no results found
    if not results and progress_info and progress_info.get('is_complete', False):
        alfred_items.append({
            "uid": "no-results",
            "title": "🔍 No matches found",
            "subtitle": f"No results for '{search_text}' in your book library",
            "icon": {"path": "icon.png"},
            "valid": False
        })
        return json.dumps(alfred_json, indent=2, ensure_ascii=False)
    
    # If no results yet but search is in progress, just show progress bar
    if not results:
        return json.dumps(alfred_json, indent=2, ensure_ascii=False)
    
    # Group results by book
    books = {}
    total_matches = len(results)
    for result in results:
        book_title = result['book_title']
        if book_title not in books:
            books[book_title] = []
        books[book_title].append(result)
    
    # Sort books by match count (most matches first)
    sorted_books = sorted(books.items(), key=lambda x: len(x[1]), reverse=True)
    total_books = len(sorted_books)

    # Summary row first
    if progress_info and progress_info.get('is_complete', False):
        alfred_items.append({
            "uid": "aaaa-summary",
            "title": f"🔍 Search Results for '{search_text}'",
            "subtitle": f"Found {total_matches:,} total matches across {total_books} book{'s' if total_books != 1 else ''}",
            "icon": {"path": "icon.png"},
            "valid": False,
        })

    for book_index, (book_title, book_results) in enumerate(sorted_books, 1):
        match_count = len(book_results)
        sample_context = re.sub(
            r"\s+", " ", book_results[0].get('context', '').replace('**', '')
        ).strip()
        if len(sample_context) > 60:
            sample_context = sample_context[:57] + "..."

        alfred_items.append({
            "uid": f"zzzz-book-{book_index:04d}",
            "title": f"📚 {book_title}",
            "subtitle": f"{book_index}/{total_books} • {match_count:,} match{'es' if match_count != 1 else ''} • {sample_context}",
            "icon": {"path": "icon.png"},
            "valid": True,
            "arg": " ",
            "variables": {
                "action": "drill_down_book",
                "book_title": book_title,
                "search_term": search_text,
                "book_filename": book_results[0].get('book_filename', ''),
                "match_count": str(match_count),
                "sample_context": sample_context
            }
        })
    
    return json.dumps(alfred_json, indent=2, ensure_ascii=False)


def export_alfred_json(results, search_text, progress_info=None, context_words=3, book_open_arg=""):
    """
    Export search results in Alfred JSON format.
    
    Parameters:
    - results: List of search results from search_multiple_epubs
    - search_text: The original search term
    - progress_info: Dict with progress information for real-time updates
                    {'current': int, 'total': int, 'current_book': str, 'is_complete': bool}
    - context_words: Number of context words used in the search
    
    Returns:
    - JSON string formatted for Alfred workflow
    """
    alfred_items = []
    
    # Add progress indicator as first item if search is in progress
    if progress_info and not progress_info.get('is_complete', True):
        current = progress_info.get('current', 0)
        total = progress_info.get('total', 0)
        current_book = progress_info.get('current_book', 'Unknown')
        
        # Create visual progress bar
        if total > 0:
            progress_ratio = current / total
            bar_length = 20
            filled_length = int(bar_length * progress_ratio)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            progress_text = f"({current}/{total}) {bar}"
        else:
            progress_text = f"({current}/?) ⏳"
        
        alfred_items.append({
            "uid": "progress",
            "title": f"🔍 Searching... {progress_text}",
            "subtitle": f"Currently searching: {current_book}",
            "icon": {"path": "icon.png"},
            "valid": False
        })
    
    if not results:
        # No results found
        alfred_items.append({
            "uid": "no-results",
            "title": f"No matches found for '{search_text}'",
            "subtitle": "Try a different search term or check your EPUB files",
            "icon": {"path": "icon.png"},
            "valid": False
        })
    else:
        # Group results by book for cleaner display
        books = {}
        for result in results:
            book_title = result['book_title']
            if book_title not in books:
                books[book_title] = []
            books[book_title].append(result)
        
        # Create Alfred items
        for book_title, book_results in books.items():
            match_count = len(book_results)
            
            # Main book entry showing total matches
            alfred_items.append({
                "uid": f"zzzz-book-{hash(book_title)}",
                "title": f"📚 {book_title}",
                "subtitle": f"Found {match_count:,} match{'es' if match_count != 1 else ''} for '{search_text}'",
                "icon": {"path": "icon.png"},
                "valid": False,
                "autocomplete": f"{book_title} ",
            })
            
            # Individual match entries (limit to prevent overwhelming Alfred)
            for i, result in enumerate(book_results[:10]):  # Show max 10 matches per book
                chapter = result.get('chapter', 'Unknown Chapter')
                # Subtitle version: strip bold markers AND collapse
                # every whitespace run to a single space so paragraph
                # breaks in the excerpt don't truncate the subtitle at
                # the first \n. The untouched multi-line `context`
                # still flows downstream via the `context` / `markdown`
                # workflow variables for the text/markdown view.
                context = re.sub(
                    r"\s+", " ", result.get('context', '').replace('**', '')
                ).strip()
                
                # Use progressive numbering if chapter info is not informative
                # Check for various uninformative patterns
                is_uninformative = (
                    not chapter or 
                    chapter == 'Unknown Chapter' or
                    len(chapter.strip()) < 3 or
                    # HTML/XML files
                    chapter.endswith(('.xhtml', '.html', '.htm', '.xml')) or
                    # Numbered files like f_0001, chapter1, etc.
                    chapter.startswith('f_') or
                    # URLs or complex paths
                    '@' in chapter or
                    '/' in chapter and len(chapter) > 20 or
                    '\\' in chapter or
                    # Looks like a UUID or hash
                    len(chapter) > 20 and any(c in chapter for c in '0123456789abcdef-') or
                    # Generic chapter names
                    chapter.lower() in ['chapter', 'section', 'page', 'untitled']
                )
                
                if is_uninformative:
                    display_location = f"Match #{i+1}"
                else:
                    # Clean and truncate meaningful chapter titles
                    clean_chapter = chapter.strip()
                    if len(clean_chapter) > 40:
                        clean_chapter = clean_chapter[:37] + "..."
                    display_location = clean_chapter
                
                # Truncate long context for subtitle
                if len(context) > 160:
                    context = context[:157] + "..."
                
                match_arg = json.dumps({
                    "book": book_title,
                    "chapter": chapter,
                    "match": result['match'],
                    "context": result.get('context', ''),
                    "search_term": search_text
                })
                open_location = result.get('file', '')
                match_mods = {}
                if book_open_arg and open_location:
                    match_mods["shift"] = {
                        "valid": True,
                        "subtitle": "Open this match location in the book",
                        "arg": f"{book_open_arg}|{open_location}",
                        "variables": {
                            "action": "open_match",
                            "open_location": open_location,
                        },
                    }

                # `fragment_id` is the shared footer-label variable used
                # by both the highlights drill-down and this in-book
                # search path, so the downstream markdown/text-view node
                # can render a single-line footer like "— {fragment_id}".
                # We prefer a meaningful chapter title when available and
                # fall back to the raw XHTML file name (the actual
                # fragment locator inside the EPUB).
                fragment_id = chapter if not is_uninformative else result.get('file', '') or chapter

                alfred_items.append({
                    "uid": f"zzzz-match-{hash(book_title)}-{i}",
                    "title": f"   └─ {result['match']} • {display_location}",
                    "subtitle": context,
                    "icon": {"path": "icon.png"},
                    "valid": True,
                    "arg": match_arg,
                    "mods": match_mods,
                    "variables": {
                        "action": "view_match",
                        "book_title": book_title,
                        "chapter": chapter,
                        "fragment_id": fragment_id,
                        "match_text": result['match'],
                        "context": result.get('context', ''),
                        "search_term": search_text,
                        "markdown": result.get('markdown', ''),
                        "context_words": str(context_words),
                        "open_location": open_location
                    }
                })
            
            # If more than 10 matches, add a summary item
            if match_count > 10:
                alfred_items.append({
                    "uid": f"zzzz-more-{hash(book_title)}",
                    "title": f"   └─ ... and {match_count - 10:,} more matches",
                    "subtitle": "Use --markdown flag to see all results in detail",
                    "icon": {"path": "icon.png"},
                    "valid": False
                })
    
    # Add summary item at the top only if multiple books have results
    total_matches = len(results)
    book_count = len({result['book_title'] for result in results})
    
    if book_count > 1:
        summary_item = {
            "uid": "aaaa-summary",  # UID starts with "aaaa" to ensure it sorts first alphabetically
            "title": f"🔍 Search Results for '{search_text}'",
            "subtitle": f"Found {total_matches:,} total matches across {book_count} books",
            "icon": {"path": "icon.png"},
            "valid": False
        }
        alfred_items.insert(0, summary_item)
    
    alfred_json = {
        "items": alfred_items,
        "skipknowledge": True,
    }

    return json.dumps(alfred_json, indent=2, ensure_ascii=False)


def export_markdown_results(results, output_file=None, group_by_book=True):
    """
    Export search results to a markdown file.

    Parameters:
    - results: List of search results from search_multiple_epubs
    - output_file: Path to output markdown file (if None, returns as string)
    - group_by_book: Whether to group results by book title

    Returns:
    - String with markdown content if output_file is None, otherwise None
    """
    if not results:
        return "No search results to export."

    # Get search term from first result
    search_term = results[0]["match"] if results else "unknown"

    markdown_content = f"# Search Results for '{search_term}'\n\n"
    markdown_content += f"Found {len(results)} matches across {len(set(r['book_title'] for r in results))} books.\n\n"

    if group_by_book:
        # Group results by book title
        books = {}
        for result in results:
            book_title = result["book_title"]
            if book_title not in books:
                books[book_title] = []
            books[book_title].append(result)

        # Generate markdown for each book
        for book_title, book_results in books.items():
            markdown_content += f"## {book_title}\n\n"
            markdown_content += f"Found {len(book_results)} matches.\n\n"

            for i, result in enumerate(book_results):
                markdown_content += f"### Match {i+1}: {result['chapter']}\n\n"
                markdown_content += f"{result['markdown']}\n\n"
                markdown_content += "---\n\n"
    else:
        # List all results without grouping
        for i, result in enumerate(results):
            markdown_content += (
                f"## Match {i+1}: {result['book_title']} - {result['chapter']}\n\n"
            )
            markdown_content += f"{result['markdown']}\n\n"
            markdown_content += "---\n\n"

    if output_file:
        output_file = os.path.expanduser(output_file)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        print(f"Markdown results exported to {output_file}")
        return None
    else:
        return markdown_content


def search_single_epub(epub_path, search_text, context_words=10, create_modified_epubs=True, quiet=False, proximity_distance=100):
    """Search a single EPUB file for specific text."""
    try:
        epub_path = os.path.expanduser(epub_path)
        if not os.path.exists(epub_path):
            if not quiet:
                print(f"Error: EPUB file not found: {epub_path}")
            return []
        
        if not quiet:
            print(f"Searching in single EPUB: {os.path.basename(epub_path)}")
        
        # Read the EPUB
        book = epub.read_epub(epub_path)
        
        # Get book title
        book_title = book.get_metadata("DC", "title")
        if book_title and len(book_title) > 0 and len(book_title[0]) > 0:
            book_title = book_title[0][0]
        else:
            book_title = os.path.splitext(os.path.basename(epub_path))[0]
        
        # Track results for this book
        book_results = []
        
        # Process each HTML item in the book
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                content = item.get_content().decode("utf-8")
                soup = BeautifulSoup(content, "html.parser")
                
                # Get chapter title if available
                chapter_title = soup.find("title")
                chapter_title = (
                    chapter_title.get_text() if chapter_title else item.get_name()
                )
                
                # Plain text for searching, with block-level breaks
                # preserved so the excerpt carries paragraph/heading
                # boundaries instead of welding them into one stream.
                text_content = _html_to_block_text(soup)
                
                # Check if this is a 2-word proximity search
                if is_proximity_search(search_text):
                    words_to_search = search_text.strip().split()
                    word1, word2 = words_to_search[0], words_to_search[1]
                    
                    # Use proximity matching
                    proximity_matches = find_proximity_matches(text_content, word1, word2, max_distance=proximity_distance)
                    
                    # Convert proximity matches to regular match format
                    matches = []
                    for start_pos, end_pos, context_snippet, distance in proximity_matches:
                        # Create a mock match object for compatibility
                        class MockMatch:
                            def __init__(self, start, end, text):
                                self._start = start
                                self._end = end  
                                self._text = text
                            def start(self): return self._start
                            def end(self): return self._end
                            def group(self): return self._text
                        
                        match_text = f"{word1} ... {word2} ({distance} {'word' if distance == 1 else 'words'} apart)"
                        matches.append(MockMatch(start_pos, end_pos, match_text))
                else:
                    # Regular exact text search
                    matches = list(
                        re.finditer(re.escape(search_text), text_content, re.IGNORECASE)
                    )
                
                # Merge matches whose context windows overlap so
                # nearby occurrences become a single Alfred row.
                for slice_start, slice_end, spans in _merge_overlapping_matches(matches, text_content, context_words):
                    raw_context = text_content[slice_start:slice_end]
                    lstripped = raw_context.lstrip()
                    lead_trim = len(raw_context) - len(lstripped)
                    raw_context = lstripped.rstrip()

                    context_text = _bold_spans(raw_context, slice_start + lead_trim, spans)
                    markdown_match = f"{context_text}\n"
                    match_label = spans[0][2]
                    if len(spans) > 1:
                        match_label += f" (+{len(spans) - 1} more)"

                    book_results.append({
                        "book_title": book_title,
                        "chapter": chapter_title,
                        "match": match_label,
                        "context": context_text,
                        "markdown": markdown_match,
                        "file": item.get_name(),
                    })
        
        # Create modified EPUB if requested
        if create_modified_epubs and book_results:
            output_path = f"{os.path.splitext(epub_path)[0]}_search_{search_text.replace(' ', '_')}.epub"
            
            # Create a new chapter for search results
            search_results_html = create_search_results_chapter(
                book, book_title, search_text, book_results
            )
            book.add_item(search_results_html)
            
            # Add to spine at the beginning
            book.spine.insert(1, search_results_html)
            
            # Write the modified EPUB
            epub.write_epub(output_path, book)
            if not quiet:
                print(f"  Modified EPUB created: {os.path.basename(output_path)}")
        
        if not quiet:
            print(f"  Found {len(book_results)} matches in '{book_title}'")
        return book_results
        
    except Exception as e:
        if not quiet:
            print(f"Error processing {os.path.basename(epub_path)}: {str(e)}")
        return []


def search_with_alfred_progress(folder_path, search_text, context_words=10, create_modified_epubs=True, proximity_distance=100):
    """
    Search multiple EPUB files with stateful Alfred JSON progress updates.
    
    This function uses a temp file to track progress and outputs only ONE JSON 
    response per execution, relying on Alfred's rerun to call again.
    """
    _cache_days = _env_positive_int('SEARCH_CACHE_DAYS') or 11
    _CACHE_MAX_AGE = _cache_days * 86400

    # Expand tilde in folder path
    folder_path = os.path.expanduser(folder_path)

    # Return cached results if fresh enough
    cache_file = _search_cache_path(search_text, folder_path)
    if os.path.exists(cache_file):
        age = time.time() - os.path.getmtime(cache_file)
        if age < _CACHE_MAX_AGE:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
            results = cached.get('results', [])
            total_books = len({r['book_title'] for r in results}) if results else 0
            progress_info = {
                'processed_books': total_books,
                'total_books': total_books,
                'current_book': 'Complete',
                'is_complete': True,
            }
            json_output = export_alfred_books_overview(results, search_text, progress_info)
            sys.stdout.write(json_output + '\n')
            sys.stdout.flush()
            return results

    # Create unique state file based on search parameters
    state_key = f"{folder_path}_{search_text}_{context_words}"
    state_hash = hashlib.md5(state_key.encode()).hexdigest()[:8]
    state_file = os.path.join(tempfile.gettempdir(), f"alfred_epub_search_{state_hash}.json")

    # Find all EPUB files
    epub_files = []
    if os.path.exists(folder_path):
        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            if item.lower().endswith('.epub'):
                epub_files.append(item_path)
    
    if not epub_files:
        # Clean up any existing state file
        if os.path.exists(state_file):
            os.remove(state_file)
        # Output no files found JSON
        progress_info = {'is_complete': True, 'processed_books': 0, 'total_books': 0}
        json_output = export_alfred_books_overview([], search_text, progress_info)
        sys.stdout.write(json_output + '\n')
        sys.stdout.flush()
        return []
    
    total_files = len(epub_files)
    
    # Load or initialize state
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
        except:
            state = {'processed': 0, 'results': [], 'complete': False}
    else:
        state = {'processed': 0, 'results': [], 'complete': False}
    
    # If search is complete, show final results
    if state['complete'] or state['processed'] >= total_files:
        # Persist results for drill-down before cleaning up temp state
        cache_file = _search_cache_path(search_text, folder_path)
        with open(cache_file, 'w') as f:
            json.dump({
                'search_text': search_text,
                'folder_path': folder_path,
                'results': state['results'],
            }, f)

        if os.path.exists(state_file):
            os.remove(state_file)

        progress_info = {
            'processed_books': total_files,
            'total_books': total_files,
            'current_book': 'Complete',
            'is_complete': True
        }
        json_output = export_alfred_books_overview(state['results'], search_text, progress_info)
        sys.stdout.write(json_output + '\n')
        sys.stdout.flush()
        return state['results']
    
    # Process next book
    current_index = state['processed']
    current_book_title = 'Complete'
    if current_index < total_files:
        epub_path = epub_files[current_index]
        current_book_title = get_book_title_from_epub(epub_path)
        
        # Search this book
        try:
            book_results = search_single_epub(epub_path, search_text, context_words, create_modified_epubs, quiet=True, proximity_distance=proximity_distance)
            if book_results:
                state['results'].extend(book_results)
        except Exception as e:
            # Continue on error but don't add results
            pass
        
        # Update state
        state['processed'] = current_index + 1
        state['complete'] = (state['processed'] >= total_files)
        
        # Save state
        with open(state_file, 'w') as f:
            json.dump(state, f)
    
    # Output current progress
    progress_info = {
        'processed_books': state['processed'],
        'total_books': total_files,
        'current_book': current_book_title,
        'is_complete': state['complete']
    }
    
    json_output = export_alfred_books_overview(state['results'], search_text, progress_info)
    sys.stdout.write(json_output + '\n')
    sys.stdout.flush()
    
    return state['results']


def get_book_title_from_epub(epub_path):
    """Extract the actual book title from EPUB metadata, fallback to filename"""
    try:
        import ebooklib
        from ebooklib import epub
        
        book = epub.read_epub(epub_path)
        book_title = book.get_metadata("DC", "title")
        if book_title and len(book_title) > 0 and len(book_title[0]) > 0:
            return book_title[0][0]
        else:
            # Fallback to filename without extension
            return os.path.splitext(os.path.basename(epub_path))[0]
    except:
        # Fallback to filename without extension
        return os.path.splitext(os.path.basename(epub_path))[0]

def get_book_title_from_path(epub_path):
    """Extract a readable book title from the EPUB file path"""
    return os.path.splitext(os.path.basename(epub_path))[0]


# Block-level HTML elements that should end with a paragraph break
# when we flatten an EPUB chapter to plain text for search-result
# context. Kept module-level so both the single-book and multi-book
# search paths use the exact same boundary definition.
_BLOCK_LEVEL_TAGS = (
    "p", "div", "section", "article",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "blockquote", "pre", "tr",
)


def _html_to_block_text(soup):
    """
    Flatten an HTML soup to plain text while preserving block-level
    structure. Two reasons we can't just call `soup.get_text()`:
      1. With no separator it welds every text node together with zero
         whitespace, so a chapter like `<h2>Chapter VI</h2><h3>Byzantine
         Civilization</h3>…<p>BYZANTINE economy…</p>` collapses to
         "Chapter VIByzantine Civilization…BYZANTINE economy…".
      2. With `separator=…` it inserts the separator between *every*
         text-node boundary, including the ones inside inline runs like
         `<p>This is <b>bold</b> text.</p>`, so paragraphs fracture
         mid-sentence.
    The workaround: append `\n\n` inside each block-level element (so
    it follows that element's content in document order) and convert
    `<br>` to `\n`. Result: real paragraph breaks between block
    siblings, no spurious breaks inside inline runs.
    """
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for block in soup.find_all(_BLOCK_LEVEL_TAGS):
        block.append("\n\n")
    text = soup.get_text()
    # Collapse runs of 3+ newlines to exactly 2 — nested block elements
    # (e.g. a <div> wrapping an <h2> wrapping inline text) each
    # contribute a `\n\n`, which stacks into ragged blank-line
    # sequences. Normalising keeps the standard markdown
    # paragraph-break spacing without losing the breaks themselves.
    # Also trim trailing whitespace on each line so stray spaces from
    # inline whitespace in the source HTML don't show up as hard-to-
    # see trailing spaces in the downstream text view.
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text


def _context_slice(text, match_start, match_end, context_words):
    """
    Return `(slice_start, slice_end)` such that `text[slice_start:
    slice_end]` includes `context_words` whole words before the match
    and `context_words` whole words after, while preserving every
    character (whitespace, newlines, punctuation) of `text` inside
    that span. Word anchors use the same `\w+` tokenizer the previous
    word-list rebuild used, so the word-count semantics are unchanged —
    only the way we render the surrounding context does.
    """
    before = text[:match_start]
    word_starts = [m.start() for m in re.finditer(r"\w+", before)]
    if len(word_starts) >= context_words:
        slice_start = word_starts[-context_words]
    elif word_starts:
        slice_start = word_starts[0]
    else:
        slice_start = match_start

    after = text[match_end:]
    word_ends = [m.end() for m in re.finditer(r"\w+", after)]
    if len(word_ends) >= context_words:
        slice_end = match_end + word_ends[context_words - 1]
    elif word_ends:
        slice_end = match_end + word_ends[-1]
    else:
        slice_end = match_end

    return slice_start, slice_end


def _merge_overlapping_matches(matches, text, context_words):
    """
    Merge matches whose context windows overlap into single results.

    Each incoming match is a regex-style object with `.start()`, `.end()`,
    `.group()`.  Returns a list of `(slice_start, slice_end, spans)` tuples
    where `spans` is a list of `(match_start, match_end, group_text)` for
    every original match inside the merged window.
    """
    if not matches:
        return []

    entries = []
    for m in matches:
        s_start, s_end = _context_slice(text, m.start(), m.end(), context_words)
        entries.append((s_start, s_end, m.start(), m.end(), m.group()))

    entries.sort(key=lambda e: e[0])

    merged = []
    cur_s, cur_e = entries[0][0], entries[0][1]
    cur_spans = [(entries[0][2], entries[0][3], entries[0][4])]

    for s_start, s_end, m_start, m_end, m_group in entries[1:]:
        if s_start <= cur_e:
            cur_e = max(cur_e, s_end)
            cur_spans.append((m_start, m_end, m_group))
        else:
            merged.append((cur_s, cur_e, cur_spans))
            cur_s, cur_e = s_start, s_end
            cur_spans = [(m_start, m_end, m_group)]
    merged.append((cur_s, cur_e, cur_spans))
    return merged


def _bold_spans(text, slice_start, spans):
    """
    Insert **bold** markers around every match span inside `text`.
    `spans` is a list of `(abs_start, abs_end, _)` in document coordinates;
    `slice_start` converts them to offsets within `text`.
    """
    sorted_spans = sorted(spans, key=lambda s: s[0], reverse=True)
    result = text
    for abs_start, abs_end, _ in sorted_spans:
        offset = abs_start - slice_start
        end_offset = abs_end - slice_start
        if 0 <= offset <= end_offset <= len(result):
            result = result[:offset] + "**" + result[offset:end_offset] + "**" + result[end_offset:]
    return result


def _env_positive_int(*names):
    """
    Return the first parseable positive int found under any of the
    given env var names, or None. Used to let Alfred workflow-config
    entries (UPPER_SNAKE) override docopt defaults, while still
    honouring legacy lowercase per-invocation variable names.
    """
    for name in names:
        raw = (os.environ.get(name) or "").strip()
        if raw.isdigit():
            value = int(raw)
            if value > 0:
                return value
    return None


def _search_cache_path(search_text, folder_path):
    """Return a persistent cache file path for a folder search."""
    try:
        from config import CACHE_FOLDER
    except Exception:
        CACHE_FOLDER = tempfile.gettempdir()
    cache_dir = os.path.join(CACHE_FOLDER, "epub_search")
    os.makedirs(cache_dir, exist_ok=True)
    key = f"{os.path.expanduser(folder_path)}_{search_text}"
    h = hashlib.md5(key.encode()).hexdigest()[:12]
    return os.path.join(cache_dir, f"search_{h}.json")


def _is_unpacked_epub_dir(path):
    """
    True if `path` is an unpacked EPUB bundle directory (i.e. META-INF
    /container.xml exists underneath). This is the same signal ebooklib
    uses for its `Directory` reader branch, so anything passing this
    check can be handed straight to `epub.read_epub()` — no zipping
    step required. Covers both iBooks bundles (whose dir name ends in
    `.epub`) and Yomu's EPUB cache (bare UUID directories).
    """
    return (
        bool(path)
        and os.path.isdir(path)
        and os.path.isfile(os.path.join(path, "META-INF", "container.xml"))
    )


def parse_book_input(book_input):
    """
    Parse workflow-specific book arguments.

    Supports:
      - regular filesystem paths
      - calibre-open|/abs/path/to/book.epub
      - calibre-open|/abs/path/to/book.epub|optional-location
      - yomu-open|<meta_ident>|<identifier>|<file_ident>
        Yomu stores each book as an unpacked EPUB bundle at
        `YOMU_EPUB_CACHE_DIR/<identifier>/`, which ebooklib.read_epub
        opens directly via its directory-reader branch — so we just
        resolve the token to that path and reuse the single-EPUB
        search pipeline.
    """
    if not book_input:
        return {"book_path": "", "open_arg": ""}

    if book_input.startswith("calibre-open|"):
        payload = book_input[len("calibre-open|") :]
        book_path = payload.split("|", 1)[0]
        return {"book_path": book_path, "open_arg": f"calibre-open|{book_path}"}

    if book_input.startswith("yomu-open|"):
        parts = book_input.split("|")
        identifier = parts[2].strip() if len(parts) > 2 else ""
        bundle_dir = (
            os.path.join(YOMU_EPUB_CACHE_DIR, identifier) if identifier else ""
        )
        return {"book_path": bundle_dir, "open_arg": book_input}

    return {"book_path": book_input, "open_arg": ""}


def main():
    """Main function to handle command line arguments"""
    args = docopt(__doc__, version='EPUB Search Tool 1.0')
    
    search_text = args['<search_text>']

    # ---- Drill-down: user actioned a book row from the folder overview.
    # Read cached results, filter to that book, and show per-match rows.
    if os.environ.get('action') == 'drill_down_book' and args.get('--alfred'):
        drill_book = os.environ.get('book_title', '')
        drill_search = os.environ.get('search_term', '')
        folder_path = os.path.expanduser(args['--folder'])

        cache_file = _search_cache_path(drill_search, folder_path)
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cached = json.load(f)
            book_results = [
                r for r in cached.get('results', [])
                if r.get('book_title') == drill_book
            ]
            book_filename = os.environ.get('book_filename', '')
            book_open_arg = ""
            if book_filename:
                parsed = parse_book_input(
                    os.path.join(folder_path, book_filename)
                )
                book_open_arg = parsed["open_arg"]
            context_words = (
                _env_positive_int('SEARCH_CONTEXT_WORDS', 'context_words')
                or int(args['--context'])
            )
            json_output = export_alfred_json(
                book_results, drill_search,
                context_words=context_words,
                book_open_arg=book_open_arg,
            )
            print(json_output)
            return 0

        error_json = {"items": [{
            "uid": "cache-miss",
            "title": "Search results expired",
            "subtitle": "Run the folder search again to refresh",
            "icon": {"path": "icon.png"},
            "valid": False,
        }]}
        print(json.dumps(error_json, indent=2))
        return 1

    # Check for persistent Alfred variables from previous workflow step
    if os.environ.get('book_title') and os.environ.get('search_term'):
        book_title = os.environ.get('book_title')
        original_search = os.environ.get('search_term')
        
        # Set up for single book search using persisted variables
        args['<search_text>'] = original_search
        search_text = original_search
        
        # Find the book file by title
        folder_path = os.path.expanduser(args['--folder'])
        target_book_path = None
        
        if os.path.exists(folder_path):
            for item in os.listdir(folder_path):
                item_path = os.path.join(folder_path, item)
                if item.lower().endswith('.epub'):
                    try:
                        actual_title = get_book_title_from_epub(item_path)
                        if actual_title == book_title:
                            target_book_path = item_path
                            break
                    except:
                        continue
        
        if target_book_path:
            args['--book'] = target_book_path
        else:
            # Fallback: show error in Alfred format
            if args['--alfred']:
                error_json = {
                    "items": [{
                        "uid": "error",
                        "title": "❌ Book not found",
                        "subtitle": f"Could not locate '{book_title}' in the library",
                        "icon": {"path": "icon.png"},
                        "valid": False
                    }]
                }
                print(json.dumps(error_json, indent=2))
                return 1
    
    # Parse arguments
    # Workflow-configurable search tuning (set from Alfred's workflow
    # configuration → "Search context words" / "Search proximity words";
    # see the `userconfigurationconfig` entries in info.plist). The env
    # names use the `SEARCH_*` prefix to match the existing workflow
    # convention (SEARCH_SCOPE, USE_KINDLE, …). We also still honour the
    # legacy lowercase `context_words` name some per-invocation Alfred
    # nodes may already set. Env wins over the docopt default because
    # docopt can't tell "user typed --context=10" apart from "no flag",
    # so we can't invert the precedence without losing user overrides.
    context_words = _env_positive_int(
        'SEARCH_CONTEXT_WORDS', 'context_words'
    )
    if context_words is None:
        context_words = int(args['--context'])

    proximity_distance = _env_positive_int('SEARCH_PROXIMITY_WORDS')
    if proximity_distance is None:
        proximity_distance = int(args['--proximity']) if args['--proximity'] else 100
    
    create_epub = bool(args['--epub'])
    create_markdown = args['--markdown'] if args['--markdown'] is not None else True  # Default to True
    group_results = args['--group'] if args['--group'] is not None else True      # Default to True
    output_file = args['--output']
    alfred_format = bool(args['--alfred'])
    
    if alfred_format:
        print(f"[DEBUG] Alfred mode enabled. Search term: '{search_text}'", file=sys.stderr)
    

    
    # Determine search mode: single book or folder
    book_open_arg = ""

    if args['--book'] and args['--book'].strip():
        # Search single EPUB file
        parsed_book = parse_book_input(args['--book'])
        epub_path = os.path.expanduser(parsed_book["book_path"])
        book_open_arg = parsed_book["open_arg"]
        if alfred_format:
            # Accept three shapes: a real `.epub` zip file, a directory
            # whose name ends in `.epub` (iBooks bundles), or any
            # directory holding `META-INF/container.xml` (Yomu's
            # unpacked cache dirs, which are bare UUIDs without a
            # `.epub` suffix). ebooklib.read_epub handles all three
            # transparently via its Directory-reader branch.
            lower = epub_path.lower()
            is_epub_file = lower.endswith(".epub") and os.path.isfile(epub_path)
            is_epub_bundle = os.path.isdir(epub_path) and (
                lower.endswith(".epub") or _is_unpacked_epub_dir(epub_path)
            )
            if not (is_epub_file or is_epub_bundle):
                raw_book_arg = (args['--book'] or '').strip()
                is_yomu_token = raw_book_arg.startswith("yomu-open|")
                if is_yomu_token:
                    # The token parsed fine but the unpacked bundle
                    # isn't on disk. Yomu populates its EPUB cache
                    # lazily, so the right action is "open the book in
                    # Yomu once", not "convert to EPUB in Calibre".
                    warning_title = "⚠️ Yomu hasn't cached this book yet"
                    warning_subtitle = (
                        "Open the book in Yomu once (the reader unpacks "
                        "its EPUB on first open), then try again."
                    )
                else:
                    _, ext = os.path.splitext(lower)
                    warning_title = "⚠️ Search supports EPUB files only"
                    warning_subtitle = (
                        f"This book is '{ext or 'unknown'}'. "
                        "Convert/add an EPUB format in Calibre to search inside it."
                    )
                unsupported_json = {
                    "items": [
                        {
                            "uid": "unsupported-format",
                            "title": warning_title,
                            "subtitle": warning_subtitle,
                            "icon": {"path": "icons/Warning.png"},
                            "valid": False,
                        }
                    ]
                }
                print(json.dumps(unsupported_json, indent=2, ensure_ascii=False))
                return 0
        if alfred_format:
            print(f"[DEBUG] Starting single book search for '{search_text}'...", file=sys.stderr)
            results = search_single_epub(epub_path, search_text, context_words, create_epub, quiet=True, proximity_distance=proximity_distance)
            print(f"[DEBUG] Search completed. Found {len(results) if results else 0} matches.", file=sys.stderr)
            json_output = export_alfred_json(results, search_text, context_words=context_words, book_open_arg=book_open_arg)
            print(json_output)
            return 0
        else:
            results = search_single_epub(epub_path, search_text, context_words, create_epub, quiet=alfred_format, proximity_distance=proximity_distance)
        
        # Set default output path for single book
        if not output_file and create_markdown:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            safe_search_text = re.sub(r"[^\w\s-]", "", search_text).replace(" ", "_")
            book_name = os.path.splitext(os.path.basename(epub_path))[0]
            output_file = f"search_{safe_search_text}_{book_name}_{timestamp}.md"
    else:
        # Search folder of EPUB files
        folder_path = args['--folder']
        if alfred_format:
            print(f"[DEBUG] Starting folder search with Alfred progress for '{search_text}'...", file=sys.stderr)
            results = search_with_alfred_progress(folder_path, search_text, context_words, create_epub, proximity_distance)
            print(f"[DEBUG] Alfred progress search completed. Found {len(results) if results else 0} matches.", file=sys.stderr)
            return 0
        else:
            results = search_multiple_epubs(folder_path, search_text, context_words, create_epub, quiet=alfred_format, proximity_distance=proximity_distance)
        
        # Set default output path for folder search
        if not output_file and create_markdown:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            safe_search_text = re.sub(r"[^\w\s-]", "", search_text).replace(" ", "_")
            output_file = os.path.join(
                os.path.expanduser(folder_path), f"search_{safe_search_text}_{timestamp}.md"
            )
    
    # Export results based on format requested
    if alfred_format:
        # For folder search (when --book is empty), show books overview
        if not args['--book'] or not args['--book'].strip():
            # Create completed progress info for summary display
            progress_info = {'is_complete': True, 'processed_books': 0, 'total_books': 0}
            json_output = export_alfred_books_overview(results, search_text, progress_info)
        else:
            # For single book search, show individual matches
            json_output = export_alfred_json(results, search_text, context_words=context_words, book_open_arg=book_open_arg)
        
        sys.stdout.write(json_output + '\n')
        sys.stdout.flush()
        # Also output to stderr for debugging
        print(f"[DEBUG] Alfred JSON output:", file=sys.stderr)
        print(json_output, file=sys.stderr)
    elif results and create_markdown:
        export_markdown_results(results, output_file, group_results)
    elif results and not create_markdown:
        print(f"\nSearch complete. Found {len(results)} total matches.")
        print("Markdown output disabled. Use --markdown to generate markdown file.")
    elif not results:
        print("\nNo matches found.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
