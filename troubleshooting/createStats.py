"""EPUB Library Statistics Generator v1.0

A comprehensive tool for analyzing EPUB libraries and generating detailed
statistics about books, authors, content, and collection metrics.

FEATURES:
  • Total books, authors, publishers, and subjects analysis
  • Word count, page estimates, and reading time calculations
  • Publication year distribution and collection timeline
  • Language detection and multilingual library analysis
  • File size analysis and storage statistics
  • Top authors, publishers, and subject categories
  • Export results to JSON, CSV, or formatted markdown report

Usage:
  createStats.py [--folder=<path>] [--output=<file>] [--format=<type>] [--detailed] [--quick] [--no-cache] [--force-refresh]
  createStats.py -h | --help
  createStats.py --version

Options:
  -h --help            Show this detailed help screen
  --version            Show version information
  --folder=<path>      Folder containing EPUB files 
                       [default: ~/Library/Containers/com.apple.BKAgentService/Data/Documents/iBooks/Books]
  --output=<file>      Output file path (auto-generated with timestamp if not specified)
  --format=<type>      Output format: markdown, json, csv [default: markdown]
  --detailed           Include detailed per-book analysis (slower but comprehensive)
  --quick             Quick analysis (metadata only, no content analysis)
  --no-cache           Disable caching system (analyze all books fresh)
  --force-refresh      Force re-analysis of all books (ignores cache)

EXAMPLES:
  createStats.py
    Generate basic library statistics (uses cache for speed)

  createStats.py --detailed --format=json
    Comprehensive analysis exported as JSON (incremental update)

  createStats.py --folder="~/MyBooks" --output="library_report.md"
    Analyze custom folder with specific output file

  createStats.py --quick --format=csv
    Fast metadata-only analysis as CSV

  createStats.py --force-refresh --detailed
    Re-analyze all books from scratch (ignores cache)

  createStats.py --no-cache
    Disable caching system completely

CACHING SYSTEM:
  • Automatically saves analysis results to .epub_library_cache.json
  • Subsequent runs only analyze new/changed books (much faster!)
  • Detects file changes using checksums
  • Use --force-refresh to rebuild cache from scratch
  • Use --no-cache to disable caching entirely

STATISTICS GENERATED:
  • Collection Overview: Total books, authors, file sizes
  • Content Analysis: Word counts, page estimates, reading times
  • Publication Timeline: Year distribution, oldest/newest books
  • Author Rankings: Most prolific authors, book counts
  • Publisher Analysis: Top publishers, publication patterns
  • Subject Categories: Genre distribution, topic analysis
  • Language Distribution: Multilingual collection analysis
  • File Analysis: Size distribution, format variations
  • Reading Metrics: Total reading time, average book length

"""

import os
import sys
import json
import csv
import hashlib
import re
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from docopt import docopt
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import tempfile


class EPUBLibraryAnalyzer:
    """Comprehensive EPUB library analysis and statistics generation."""
    
    def __init__(self, folder_path, detailed=False, quiet=False, cache_file=None):
        self.folder_path = os.path.expanduser(folder_path)
        self.detailed = detailed
        self.quiet = quiet
        self.cache_file = cache_file or os.path.join(self.folder_path, '.epub_library_cache.json')
        self.stats = {
            'overview': {},
            'authors': {},
            'publishers': {},
            'subjects': {},
            'languages': {},
            'years': {},
            'content': {},
            'files': {},
            'books': [],
            'metadata': {
                'last_updated': None,
                'analysis_mode': 'quick',
                'file_checksums': {}
            }
        }
        self.cached_books = {}  # Dictionary to store previously analyzed books by file path
        
    def log(self, message):
        """Print progress message if not in quiet mode."""
        if not self.quiet:
            print(message)
            
    def load_cache(self):
        """Load previously analyzed book data from cache file."""
        if not self.cache_file:
            return False  # Caching disabled
            
        if os.path.exists(self.cache_file):
            try:
                self.log(f"📂 Loading cache from {os.path.basename(self.cache_file)}...")
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                
                # Load cached books indexed by filepath
                if 'books' in cached_data:
                    for book in cached_data['books']:
                        if 'filepath' in book:
                            self.cached_books[book['filepath']] = book
                
                # Load metadata
                if 'metadata' in cached_data:
                    self.stats['metadata'] = cached_data['metadata']
                
                self.log(f"✅ Loaded {len(self.cached_books)} previously analyzed books from cache.")
                return True
                
            except Exception as e:
                self.log(f"⚠️  Error loading cache: {str(e)}. Starting fresh analysis.")
                
        return False
        
    def save_cache(self):
        """Save current analysis results to cache file."""
        if not self.cache_file:
            return  # Caching disabled
            
        try:
            # Update metadata
            self.stats['metadata'].update({
                'last_updated': datetime.now().isoformat(),
                'analysis_mode': 'detailed' if self.detailed else 'quick',
                'total_books': len(self.stats['books'])
            })
            
            # Save to cache file
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, indent=2, ensure_ascii=False, default=str)
            
            self.log(f"💾 Cache saved to {os.path.basename(self.cache_file)}")
            
        except Exception as e:
            self.log(f"⚠️  Error saving cache: {str(e)}")
            
    def get_file_checksum(self, filepath):
        """Get MD5 checksum of file or directory for change detection."""
        try:
            hash_md5 = hashlib.md5()
            
            if os.path.isdir(filepath):
                # For EPUB directories (Apple Books format)
                # Hash the modification times and sizes of key files
                total_size = self.get_total_size(filepath)
                hash_md5.update(str(total_size).encode())
                
                # Hash modification times of important files
                key_files = ['iTunesMetadata.plist', 'mimetype', 'META-INF/container.xml']
                for key_file in key_files:
                    key_path = os.path.join(filepath, key_file)
                    if os.path.exists(key_path):
                        mtime = os.path.getmtime(key_path)
                        hash_md5.update(str(mtime).encode())
                        
            elif os.path.isfile(filepath):
                # For regular EPUB files, hash the first and last 64KB plus file size
                file_size = os.path.getsize(filepath)
                
                with open(filepath, "rb") as f:
                    # Hash file size
                    hash_md5.update(str(file_size).encode())
                    
                    # Hash first 64KB
                    chunk = f.read(65536)
                    hash_md5.update(chunk)
                    
                    # Hash last 64KB if file is large enough
                    if file_size > 131072:  # 128KB
                        f.seek(-65536, 2)  # Seek to 64KB from end
                        chunk = f.read(65536)
                        hash_md5.update(chunk)
            else:
                return None
                    
            return hash_md5.hexdigest()[:16]  # Use first 16 chars
            
        except Exception:
            return None
            
    def is_book_changed(self, filepath):
        """Check if book file has changed since last analysis."""
        current_checksum = self.get_file_checksum(filepath)
        if not current_checksum:
            return True  # Assume changed if can't calculate checksum
            
        stored_checksum = self.stats['metadata']['file_checksums'].get(filepath)
        return current_checksum != stored_checksum
        
    def analyze_library(self):
        """Main analysis function that processes all EPUBs in the folder."""
        self.log("🔍 Starting EPUB library analysis...")
        
        # Load previous analysis if available
        cache_loaded = self.load_cache()
        
        # Find all EPUB files
        epub_files = self.find_epub_files()
        total_files = len(epub_files)
        
        if total_files == 0:
            self.log("❌ No EPUB files found in the specified folder.")
            return False
            
        self.log(f"📚 Found {total_files} EPUB files to analyze...")
        
        # Determine which files need processing
        files_to_process = []
        cached_count = 0
        
        for epub_path in epub_files:
            if (epub_path in self.cached_books and 
                not self.is_book_changed(epub_path) and
                self.stats['metadata'].get('analysis_mode') == ('detailed' if self.detailed else 'quick')):
                # Use cached data
                self.stats['books'].append(self.cached_books[epub_path])
                cached_count += 1
            else:
                # Needs fresh analysis
                files_to_process.append(epub_path)
        
        if cache_loaded:
            self.log(f"📋 Using cached data for {cached_count} books, analyzing {len(files_to_process)} new/changed books.")
        
        # Initialize counters
        processed = 0
        errors = 0
        
        # Process files that need analysis
        for i, epub_path in enumerate(files_to_process, 1):
            try:
                self.log(f"📖 Processing ({i}/{len(files_to_process)}): {os.path.basename(epub_path)}")
                book_stats = self.analyze_single_epub(epub_path)
                
                if book_stats:
                    self.stats['books'].append(book_stats)
                    # Update checksum for this file
                    checksum = self.get_file_checksum(epub_path)
                    if checksum:
                        self.stats['metadata']['file_checksums'][epub_path] = checksum
                    processed += 1
                    
            except Exception as e:
                errors += 1
                self.log(f"⚠️  Error processing {os.path.basename(epub_path)}: {str(e)}")
                continue
        
        # Clean up checksums for files that no longer exist
        existing_files = set(epub_files)
        self.stats['metadata']['file_checksums'] = {
            path: checksum for path, checksum in self.stats['metadata']['file_checksums'].items()
            if path in existing_files
        }
        
        self.log(f"✅ Analysis complete! Processed {processed} new books, used {cached_count} cached, {errors} errors.")
        
        # Generate aggregate statistics
        self.calculate_aggregate_stats()
        
        # Save updated cache
        self.save_cache()
        
        return True
        
    def find_epub_files(self):
        """Find all EPUB files in the specified folder."""
        epub_files = []
        
        if not os.path.exists(self.folder_path):
            return epub_files
            
        for item in os.listdir(self.folder_path):
            item_path = os.path.join(self.folder_path, item)
            if item.lower().endswith('.epub'):
                epub_files.append(item_path)
                
        return sorted(epub_files)
        
    def get_total_size(self, path):
        """Get total size of file or directory in bytes."""
        if os.path.isfile(path):
            return os.path.getsize(path)
        elif os.path.isdir(path):
            total_size = 0
            try:
                for dirpath, dirnames, filenames in os.walk(path):
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        try:
                            total_size += os.path.getsize(filepath)
                        except (OSError, FileNotFoundError):
                            # Skip files that can't be accessed
                            continue
            except (OSError, FileNotFoundError):
                return 0
            return total_size
        else:
            return 0

    def analyze_single_epub(self, epub_path):
        """Analyze a single EPUB file and extract statistics."""
        try:
            # Debug: Check if file exists and get basic info
            if not os.path.exists(epub_path):
                raise FileNotFoundError(f"EPUB file not found: {epub_path}")
                
            book = epub.read_epub(epub_path)
            
            # Initialize book statistics
            try:
                file_size_bytes = self.get_total_size(epub_path)
                file_size_mb = round(file_size_bytes / 1024 / 1024, 2)
            except (OSError, FileNotFoundError) as e:
                if not self.quiet:
                    print(f"⚠️  Warning: Could not get file size for {epub_path}: {e}")
                file_size_mb = 0.0
                
            book_stats = {
                'filename': os.path.basename(epub_path),
                'filepath': epub_path,
                'file_size_mb': file_size_mb,
                'title': '',
                'authors': [],
                'publisher': '',
                'publication_date': '',
                'year': None,
                'language': '',
                'subjects': [],
                'description': '',
                'word_count': 0,
                'estimated_pages': 0,
                'estimated_reading_time_minutes': 0,
                'chapter_count': 0
            }
            
            # Extract metadata
            self.extract_metadata(book, book_stats)
            
            # Extract content statistics if detailed analysis is requested
            if self.detailed:
                self.extract_content_stats(book, book_stats)
                
            return book_stats
            
        except Exception as e:
            raise Exception(f"Failed to analyze EPUB: {str(e)}")
            
    def extract_metadata(self, book, book_stats):
        """Extract metadata from EPUB."""
        # Title
        title_meta = book.get_metadata('DC', 'title')
        if title_meta and len(title_meta) > 0:
            book_stats['title'] = title_meta[0][0]
        else:
            book_stats['title'] = os.path.splitext(book_stats['filename'])[0]
            
        # Authors
        author_meta = book.get_metadata('DC', 'creator')
        if author_meta:
            book_stats['authors'] = [author[0] for author in author_meta]
            
        # Publisher
        publisher_meta = book.get_metadata('DC', 'publisher')
        if publisher_meta and len(publisher_meta) > 0:
            book_stats['publisher'] = publisher_meta[0][0]
            
        # Publication date
        date_meta = book.get_metadata('DC', 'date')
        if date_meta and len(date_meta) > 0:
            book_stats['publication_date'] = date_meta[0][0]
            # Extract year
            year_match = re.search(r'(\d{4})', book_stats['publication_date'])
            if year_match:
                book_stats['year'] = int(year_match.group(1))
                
        # Language
        lang_meta = book.get_metadata('DC', 'language')
        if lang_meta and len(lang_meta) > 0:
            book_stats['language'] = lang_meta[0][0]
            
        # Subjects
        subject_meta = book.get_metadata('DC', 'subject')
        if subject_meta:
            book_stats['subjects'] = [subject[0] for subject in subject_meta]
            
        # Description
        desc_meta = book.get_metadata('DC', 'description')
        if desc_meta and len(desc_meta) > 0:
            book_stats['description'] = desc_meta[0][0]
            
    def extract_content_stats(self, book, book_stats):
        """Extract content statistics from EPUB (word count, etc.)."""
        total_words = 0
        chapter_count = 0
        
        # Process each HTML item in the book
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                try:
                    content = item.get_content().decode('utf-8', errors='ignore')
                    soup = BeautifulSoup(content, 'html.parser')
                    text = soup.get_text()
                    
                    # Count words
                    words = re.findall(r'\b\w+\b', text)
                    total_words += len(words)
                    
                    # Count chapters (items with substantial content)
                    if len(words) > 100:  # Arbitrary threshold for chapter
                        chapter_count += 1
                        
                except Exception:
                    continue  # Skip problematic content
                    
        book_stats['word_count'] = total_words
        book_stats['chapter_count'] = chapter_count
        
        # Estimate pages (250-300 words per page average)
        book_stats['estimated_pages'] = max(1, round(total_words / 275))
        
        # Estimate reading time (200-250 words per minute average)
        book_stats['estimated_reading_time_minutes'] = max(1, round(total_words / 225))
        
    def calculate_aggregate_stats(self):
        """Calculate aggregate statistics from individual book data."""
        books = self.stats['books']
        total_books = len(books)
        
        if total_books == 0:
            return
            
        # Overview statistics
        self.stats['overview'] = {
            'total_books': total_books,
            'total_authors': len(set(author for book in books for author in book['authors'])),
            'total_publishers': len(set(book['publisher'] for book in books if book['publisher'])),
            'total_file_size_mb': sum(book['file_size_mb'] for book in books),
            'total_file_size_gb': round(sum(book['file_size_mb'] for book in books) / 1024, 2),
            'average_file_size_mb': round(sum(book['file_size_mb'] for book in books) / total_books, 2)
        }
        
        # Content statistics (if detailed analysis was performed)
        if self.detailed and any(book['word_count'] > 0 for book in books):
            total_words = sum(book['word_count'] for book in books)
            total_pages = sum(book['estimated_pages'] for book in books)
            total_reading_time = sum(book['estimated_reading_time_minutes'] for book in books)
            
            self.stats['content'] = {
                'total_words': total_words,
                'total_estimated_pages': total_pages,
                'total_reading_time_hours': round(total_reading_time / 60, 1),
                'total_reading_time_days': round(total_reading_time / (60 * 8), 1),  # 8 hours reading per day
                'average_words_per_book': round(total_words / total_books),
                'average_pages_per_book': round(total_pages / total_books),
                'average_reading_time_hours': round((total_reading_time / total_books) / 60, 1)
            }
        
        # Author statistics
        author_counts = Counter(author for book in books for author in book['authors'])
        self.stats['authors'] = {
            'most_prolific': dict(author_counts.most_common(10)),
            'single_book_authors': sum(1 for count in author_counts.values() if count == 1),
            'multi_book_authors': sum(1 for count in author_counts.values() if count > 1)
        }
        
        # Publisher statistics
        publisher_counts = Counter(book['publisher'] for book in books if book['publisher'])
        self.stats['publishers'] = {
            'top_publishers': dict(publisher_counts.most_common(10)),
            'total_publishers': len(publisher_counts)
        }
        
        # Subject/Genre statistics
        subject_counts = Counter(subject for book in books for subject in book['subjects'])
        self.stats['subjects'] = {
            'top_subjects': dict(subject_counts.most_common(15)),
            'total_unique_subjects': len(subject_counts)
        }
        
        # Language statistics
        language_counts = Counter(book['language'] for book in books if book['language'])
        self.stats['languages'] = {
            'distribution': dict(language_counts.most_common()),
            'total_languages': len(language_counts)
        }
        
        # Publication year statistics
        years = [book['year'] for book in books if book['year']]
        if years:
            year_counts = Counter(years)
            self.stats['years'] = {
                'distribution': dict(sorted(year_counts.items())),
                'oldest_book': min(years),
                'newest_book': max(years),
                'span_years': max(years) - min(years),
                'books_per_decade': self.calculate_decade_distribution(years)
            }
            
        # File size analysis
        sizes = [book['file_size_mb'] for book in books]
        self.stats['files'] = {
            'size_distribution': {
                'under_1mb': sum(1 for size in sizes if size < 1),
                '1_5mb': sum(1 for size in sizes if 1 <= size < 5),
                '5_10mb': sum(1 for size in sizes if 5 <= size < 10),
                '10_25mb': sum(1 for size in sizes if 10 <= size < 25),
                'over_25mb': sum(1 for size in sizes if size >= 25)
            },
            'largest_book': max((book['file_size_mb'], book['title']) for book in books)[1] if books else '',
            'smallest_book': min((book['file_size_mb'], book['title']) for book in books)[1] if books else ''
        }
        
    def calculate_decade_distribution(self, years):
        """Calculate book distribution by decade."""
        decade_counts = defaultdict(int)
        for year in years:
            decade = (year // 10) * 10
            decade_counts[f"{decade}s"] += 1
        return dict(decade_counts)
        
    def export_markdown(self, output_file):
        """Export statistics as formatted markdown report."""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# 📚 EPUB Library Statistics Report\n\n")
            f.write(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
            
            # Overview
            overview = self.stats['overview']
            f.write("## 📊 Collection Overview\n\n")
            f.write(f"- **Total Books:** {overview['total_books']:,}\n")
            f.write(f"- **Unique Authors:** {overview['total_authors']:,}\n")
            f.write(f"- **Publishers:** {overview['total_publishers']:,}\n")
            f.write(f"- **Total File Size:** {overview['total_file_size_gb']:.1f} GB ({overview['total_file_size_mb']:.0f} MB)\n")
            f.write(f"- **Average File Size:** {overview['average_file_size_mb']:.1f} MB\n\n")
            
            # Content statistics (if available)
            if self.stats['content']:
                content = self.stats['content']
                f.write("## 📖 Content Analysis\n\n")
                f.write(f"- **Total Words:** {content['total_words']:,}\n")
                f.write(f"- **Total Pages:** {content['total_estimated_pages']:,}\n")
                f.write(f"- **Total Reading Time:** {content['total_reading_time_hours']} hours ({content['total_reading_time_days']} days at 8hrs/day)\n")
                f.write(f"- **Average Book Length:** {content['average_words_per_book']:,} words ({content['average_pages_per_book']} pages)\n")
                f.write(f"- **Average Reading Time:** {content['average_reading_time_hours']} hours per book\n\n")
            
            # Top Authors
            if self.stats['authors']['most_prolific']:
                f.write("## 👥 Top Authors\n\n")
                for author, count in list(self.stats['authors']['most_prolific'].items())[:10]:
                    f.write(f"- **{author}:** {count} book{'s' if count > 1 else ''}\n")
                f.write(f"\n*{self.stats['authors']['multi_book_authors']} authors with multiple books, {self.stats['authors']['single_book_authors']} with single books*\n\n")
            
            # Publication Timeline
            if self.stats['years']:
                years = self.stats['years']
                f.write("## 📅 Publication Timeline\n\n")
                f.write(f"- **Year Range:** {years['oldest_book']} - {years['newest_book']} ({years['span_years']} years)\n")
                f.write(f"- **Books by Decade:**\n")
                for decade, count in sorted(years['books_per_decade'].items()):
                    f.write(f"  - {decade}: {count} books\n")
                f.write("\n")
            
            # Top Subjects/Genres
            if self.stats['subjects']['top_subjects']:
                f.write("## 🏷️ Top Subjects & Genres\n\n")
                for subject, count in list(self.stats['subjects']['top_subjects'].items())[:10]:
                    f.write(f"- **{subject}:** {count} book{'s' if count > 1 else ''}\n")
                f.write("\n")
            
            # Languages
            if self.stats['languages']['distribution']:
                f.write("## 🌍 Language Distribution\n\n")
                for lang, count in self.stats['languages']['distribution'].items():
                    percentage = (count / overview['total_books']) * 100
                    f.write(f"- **{lang}:** {count} books ({percentage:.1f}%)\n")
                f.write("\n")
            
            # File Size Analysis
            files = self.stats['files']
            f.write("## 💾 File Size Analysis\n\n")
            size_dist = files['size_distribution']
            f.write(f"- **Under 1 MB:** {size_dist['under_1mb']} books\n")
            f.write(f"- **1-5 MB:** {size_dist['1_5mb']} books\n")
            f.write(f"- **5-10 MB:** {size_dist['5_10mb']} books\n")
            f.write(f"- **10-25 MB:** {size_dist['10_25mb']} books\n")
            f.write(f"- **Over 25 MB:** {size_dist['over_25mb']} books\n\n")
            f.write(f"- **Largest Book:** {files['largest_book']}\n")
            f.write(f"- **Smallest Book:** {files['smallest_book']}\n\n")
            
            f.write("---\n")
            f.write(f"*Report generated by EPUB Library Statistics Generator v1.0*\n")
            
    def export_json(self, output_file):
        """Export statistics as JSON."""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False, default=str)
            
    def export_csv(self, output_file):
        """Export book list as CSV."""
        if not self.stats['books']:
            return
            
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.stats['books'][0].keys())
            writer.writeheader()
            for book in self.stats['books']:
                # Convert lists to strings for CSV compatibility
                book_copy = book.copy()
                book_copy['authors'] = '; '.join(book['authors'])
                book_copy['subjects'] = '; '.join(book['subjects'])
                writer.writerow(book_copy)


def main():
    """Main function to handle command line arguments and execute analysis."""
    args = docopt(__doc__, version='EPUB Library Statistics Generator 1.0')
    
    folder_path = args['--folder']
    output_file = args['--output']
    output_format = args['--format']
    detailed = args['--detailed']
    quick = args['--quick']
    no_cache = args['--no-cache']
    force_refresh = args['--force-refresh']
    
    # If quick mode is specified, disable detailed analysis
    if quick:
        detailed = False
        
    # Handle caching options
    cache_file = None
    if no_cache:
        cache_file = None  # Disable caching
    else:
        # Use default cache file location
        cache_file = os.path.join(os.path.expanduser(folder_path), '.epub_library_cache.json')
        
        # If force refresh, delete existing cache
        if force_refresh and os.path.exists(cache_file):
            try:
                os.remove(cache_file)
                print(f"🗑️  Removed existing cache file for fresh analysis.")
            except Exception as e:
                print(f"⚠️  Could not remove cache file: {str(e)}")
        
    # Create analyzer
    analyzer = EPUBLibraryAnalyzer(folder_path, detailed=detailed, quiet=False, cache_file=cache_file)
    
    # Perform analysis
    success = analyzer.analyze_library()
    
    if not success:
        return 1
        
    # Generate output filename if not specified
    if not output_file:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        extensions = {'markdown': 'md', 'json': 'json', 'csv': 'csv'}
        ext = extensions.get(output_format, 'md')
        output_file = f"epub_library_stats_{timestamp}.{ext}"
        
    # Export results
    try:
        if output_format == 'json':
            analyzer.export_json(output_file)
        elif output_format == 'csv':
            analyzer.export_csv(output_file)
        else:  # markdown (default)
            analyzer.export_markdown(output_file)
            
        print(f"\\n✅ Statistics exported to: {output_file}")
        
        # Print quick summary
        overview = analyzer.stats['overview']
        print(f"\\n📊 Quick Summary:")
        print(f"   📚 {overview['total_books']} books")
        print(f"   👥 {overview['total_authors']} authors") 
        print(f"   💾 {overview['total_file_size_gb']:.1f} GB total")
        
        if analyzer.stats['content']:
            content = analyzer.stats['content']
            print(f"   📖 {content['total_words']:,} words")
            print(f"   ⏱️  {content['total_reading_time_hours']} hours reading time")
            
        # Show cache status
        if analyzer.cache_file and os.path.exists(analyzer.cache_file):
            cache_date = analyzer.stats['metadata'].get('last_updated', 'Unknown')
            if cache_date != 'Unknown' and cache_date:
                try:
                    cache_dt = datetime.fromisoformat(cache_date.replace('Z', '+00:00'))
                    cache_age = datetime.now() - cache_dt.replace(tzinfo=None)
                    if cache_age.days > 0:
                        age_str = f"{cache_age.days} days ago"
                    elif cache_age.seconds > 3600:
                        age_str = f"{cache_age.seconds // 3600} hours ago"
                    else:
                        age_str = "recently"
                    print(f"   🗂️  Cache updated {age_str}")
                except:
                    print(f"   🗂️  Cache available")
        elif not analyzer.cache_file:
            print(f"   🚫 Cache disabled")
        else:
            print(f"   🆕 Fresh cache created")
            
        return 0
        
    except Exception as e:
        print(f"❌ Error exporting results: {str(e)}")
        return 1


if __name__ == '__main__':
    sys.exit(main())