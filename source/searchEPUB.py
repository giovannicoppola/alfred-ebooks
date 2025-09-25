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
import os
import re
import sys
import time
import uuid

import ebooklib
from bs4 import BeautifulSoup
from docopt import docopt
from ebooklib import epub

# Default settings
DEFAULT_EPUB_FOLDER = "~/Library/Containers/com.apple.BKAgentService/Data/Documents/iBooks/Books"
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

                    # Get plain text for searching
                    text_content = soup.get_text()

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
                            
                            match_text = f"{word1} ... {word2} ({distance} words apart)"
                            matches.append(MockMatch(start_pos, end_pos, match_text))
                    else:
                        # Regular exact text search
                        matches = list(
                            re.finditer(re.escape(search_text), text_content, re.IGNORECASE)
                        )

                    # Split text into words for context extraction  
                    words = re.findall(r"\b\w+\b", text_content)

                    if matches:
                        # For each match, extract context and create markdown
                        for match in matches:
                            # Create a unique ID for this match
                            match_id = f"match_{uuid.uuid4().hex[:8]}"

                            # Find the word position of this match
                            match_pos = len(
                                re.findall(r"\b\w+\b", text_content[: match.start()])
                            )

                            # Get surrounding words
                            start_word = max(0, match_pos - context_words)
                            end_word = min(
                                len(words),
                                match_pos + context_words + len(search_text.split()),
                            )

                            # Get the context as a string
                            if start_word < match_pos and end_word > match_pos:
                                context_before = " ".join(words[start_word:match_pos])
                                match_words = " ".join(
                                    words[
                                        match_pos : match_pos + len(search_text.split())
                                    ]
                                )
                                context_after = " ".join(
                                    words[
                                        match_pos + len(search_text.split()) : end_word
                                    ]
                                )
                                context = (
                                    f"{context_before} {match_words} {context_after}"
                                )

                                # Create markdown version with bold search text
                                markdown_context = f"{context_before} **{match_words}** {context_after}"
                            else:
                                # Fallback if word-based context fails
                                start = max(0, match.start() - 100)
                                end = min(len(text_content), match.end() + 100)
                                context = (
                                    text_content[start : match.start()]
                                    + text_content[match.start() : match.end()]
                                    + text_content[match.end() : end]
                                )

                                # Create markdown version with bold search text
                                markdown_context = (
                                    text_content[start : match.start()]
                                    + f"**{text_content[match.start():match.end()]}**"
                                    + text_content[match.end() : end]
                                )

                            # Clean up the context (remove extra whitespace, newlines)
                            context = re.sub(r"\s+", " ", context).strip()
                            markdown_context = re.sub(
                                r"\s+", " ", markdown_context
                            ).strip()

                            # Generate clean markdown string with book title
                            markdown_string = f"> {markdown_context}\n\n— *{book_title}, {chapter_title}*"

                            # Store result
                            result = {
                                "book_title": book_title,
                                "book_filename": book_filename,
                                "chapter": chapter_title,
                                "context": context,
                                "match": search_text,
                                "file": item.get_name(),
                                "id": match_id,
                                "markdown": markdown_string,
                            }

                            book_results.append(result)
                            all_results.append(result)

                            # If we're creating modified EPUBs, add highlight to the content
                            if create_modified_epubs:
                                modified_content = (
                                    content[: match.start()]
                                    + f'<span id="{match_id}" style="background-color: #ffff00;">'
                                    + content[match.start() : match.end()]
                                    + "</span>"
                                    + content[match.end() :]
                                )
                                item.set_content(modified_content.encode("utf-8"))

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
        print(f"Total matches found: {len(all_results)}")

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
    alfred_json = {"items": []}
    alfred_items = alfred_json["items"]
    
    # Add rerun for progress updates if search is in progress
    if progress_info and not progress_info.get('is_complete', False):
        alfred_json["rerun"] = 0.5  # Rerun every 0.5 seconds during search
    
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
        match_text = f"{total_matches} matches in {len(books)} books so far" if total_matches > 0 else "No matches yet"
        
        alfred_items.append({
            "uid": "progress",
            "title": f"🔍 Searching ({processed}/{total}) • {match_text}",
            "subtitle": f"{progress_bar} Currently searching: {current_book}",
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
    
    # Summary item always at the top when search is complete
    summary_item = None
    if progress_info and progress_info.get('is_complete', False):
        summary_item = {
            "uid": "aaaa-summary",  # UID starts with "aaaa" to ensure it sorts first alphabetically
            "title": f"🔍 Search Results for '{search_text}'",
            "subtitle": f"Found {total_matches} total matches across {len(books)} books",
            "icon": {"path": "icon.png"},
            "valid": False
        }
    
    # One item per book with progressive numbering
    for book_index, (book_title, book_results) in enumerate(books.items(), 1):
        match_count = len(book_results)
        total_books = len(books)
        # Get a sample context from first match
        sample_context = book_results[0].get('context', '').replace('**', '').strip()
        if len(sample_context) > 60:
            sample_context = sample_context[:57] + "..."
        
        # Create stable UID based on book title for consistent selection (starts with 'zzzz' to ensure summary sorts first)
        stable_uid = f"zzzz-book-{hashlib.md5(book_title.encode()).hexdigest()[:8]}"
        
        alfred_items.append({
            "uid": stable_uid,
            "title": f"📚 {book_title}",
            "subtitle": f"{book_index}/{total_books} • {match_count} match{'es' if match_count != 1 else ''} • {sample_context}",
            "icon": {"path": "icon.png"},
            "valid": True,
            "arg": book_title,  # Simple arg for basic Alfred handling
            "variables": {
                "action": "drill_down_book",
                "book_title": book_title,
                "search_term": search_text,
                "book_filename": book_results[0].get('book_filename', ''),
                "match_count": str(match_count),
                "sample_context": sample_context
            }
        })
    
    # Ensure summary item is always first when search is complete
    if summary_item:
        alfred_items.insert(0, summary_item)
    
    return json.dumps(alfred_json, indent=2, ensure_ascii=False)


def export_alfred_json(results, search_text, progress_info=None, context_words=3):
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
                "subtitle": f"Found {match_count} match{'es' if match_count != 1 else ''} for '{search_text}'",
                "icon": {"path": "icon.png"},
                "valid": False,
                "autocomplete": f"{book_title} ",
            })
            
            # Individual match entries (limit to prevent overwhelming Alfred)
            for i, result in enumerate(book_results[:10]):  # Show max 10 matches per book
                chapter = result.get('chapter', 'Unknown Chapter')
                context = result.get('context', '').replace('**', '').strip()
                
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
                if len(context) > 80:
                    context = context[:77] + "..."
                
                alfred_items.append({
                    "uid": f"zzzz-match-{hash(book_title)}-{i}",
                    "title": f"   └─ {result['match']} • {display_location}",
                    "subtitle": context,
                    "icon": {"path": "icon.png"},
                    "valid": True,
                    "arg": json.dumps({
                        "book": book_title,
                        "chapter": chapter,
                        "match": result['match'],
                        "context": result.get('context', ''),
                        "search_term": search_text
                    }),
                    "variables": {
                        "action": "view_match",
                        "book_title": book_title,
                        "chapter": chapter,
                        "match_text": result['match'],
                        "context": result.get('context', ''),
                        "search_term": search_text,
                        "markdown": result.get('markdown', ''),
                        "context_words": str(context_words)
                    }
                })
            
            # If more than 10 matches, add a summary item
            if match_count > 10:
                alfred_items.append({
                    "uid": f"zzzz-more-{hash(book_title)}",
                    "title": f"   └─ ... and {match_count - 10} more matches",
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
            "subtitle": f"Found {total_matches} total matches across {book_count} books",
            "icon": {"path": "icon.png"},
            "valid": False
        }
        alfred_items.insert(0, summary_item)
    
    alfred_json = {
        "items": alfred_items
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
                
                # Get plain text for searching
                text_content = soup.get_text()
                
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
                        
                        match_text = f"{word1} ... {word2} ({distance} words apart)"
                        matches.append(MockMatch(start_pos, end_pos, match_text))
                else:
                    # Regular exact text search
                    matches = list(
                        re.finditer(re.escape(search_text), text_content, re.IGNORECASE)
                    )
                
                # Split text into words for context extraction
                words = re.findall(r"\b\w+\b", text_content)
                
                # Process each match
                for match in matches:
                    # Find the word positions around the match
                    match_start = match.start()
                    match_end = match.end()
                    
                    # Find word boundaries around the match
                    words_before_match = re.findall(
                        r"\b\w+\b", text_content[:match_start]
                    )
                    words_after_match = re.findall(
                        r"\b\w+\b", text_content[match_end:]
                    )
                    
                    # Get context words
                    context_before = words_before_match[-context_words:] if words_before_match else []
                    context_after = words_after_match[:context_words] if words_after_match else []
                    
                    # Create context string
                    context_text = (
                        " ".join(context_before)
                        + " **"
                        + match.group()
                        + "** "
                        + " ".join(context_after)
                    )
                    
                    # Create markdown representation
                    markdown_match = f"**{match.group()}** found in *{chapter_title}*:\n\n{context_text}\n"
                    
                    book_results.append({
                        "book_title": book_title,
                        "chapter": chapter_title,
                        "match": match.group(),
                        "context": context_text,
                        "markdown": markdown_match,
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
    import sys
    import os
    import json
    import tempfile
    import hashlib
    
    # Create unique state file based on search parameters
    state_key = f"{folder_path}_{search_text}_{context_words}"
    state_hash = hashlib.md5(state_key.encode()).hexdigest()[:8]
    state_file = os.path.join(tempfile.gettempdir(), f"alfred_epub_search_{state_hash}.json")
    
    # Expand tilde in folder path
    folder_path = os.path.expanduser(folder_path)
    
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
        # Clean up state file
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


def main():
    """Main function to handle command line arguments"""
    args = docopt(__doc__, version='EPUB Search Tool 1.0')
    
    search_text = args['<search_text>']
    
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
    # Get context words from environment variable or command line argument
    env_context = os.environ.get('context_words', '')
    if env_context and env_context.isdigit():
        context_words = int(env_context)
    else:
        context_words = int(args['--context'])
    
    # Get proximity distance for 2-word searches
    proximity_distance = int(args['--proximity']) if args['--proximity'] else 100
    
    create_epub = bool(args['--epub'])
    create_markdown = args['--markdown'] if args['--markdown'] is not None else True  # Default to True
    group_results = args['--group'] if args['--group'] is not None else True      # Default to True
    output_file = args['--output']
    alfred_format = bool(args['--alfred'])
    
    if alfred_format:
        import sys
        print(f"[DEBUG] Alfred mode enabled. Search term: '{search_text}'", file=sys.stderr)
    

    
    # Determine search mode: single book or folder
    if args['--book'] and args['--book'].strip():
        # Search single EPUB file
        epub_path = os.path.expanduser(args['--book'])
        if alfred_format:
            # For single book, search and output Alfred JSON directly
            import sys
            print(f"[DEBUG] Starting single book search for '{search_text}'...", file=sys.stderr)
            results = search_single_epub(epub_path, search_text, context_words, create_epub, quiet=True, proximity_distance=proximity_distance)
            print(f"[DEBUG] Search completed. Found {len(results) if results else 0} matches.", file=sys.stderr)
            json_output = export_alfred_json(results, search_text, context_words=context_words)
            print(json_output)
            # Also output to stderr for debugging
            import sys
            print(f"[DEBUG] Alfred JSON output:", file=sys.stderr)
            print(json_output, file=sys.stderr)
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
            import sys
            print(f"[DEBUG] Starting folder search with Alfred progress for '{search_text}'...", file=sys.stderr)
            # Use Alfred progress function that outputs JSON during search
            results = search_with_alfred_progress(folder_path, search_text, context_words, create_epub, proximity_distance)
            print(f"[DEBUG] Alfred progress search completed. Found {len(results) if results else 0} matches.", file=sys.stderr)
            return 0  # Exit early since progress function handles output
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
            json_output = export_alfred_json(results, search_text, context_words=context_words)
        
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
