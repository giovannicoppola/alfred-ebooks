# CONFIG file for the alfred-eBooks workflow

import os
import sys
import shutil



CACHE_FOLDER = os.getenv('alfred_workflow_cache')
DATA_FOLDER = os.getenv('alfred_workflow_data')
CACHE_FOLDER_IMAGES_KINDLE = CACHE_FOLDER+"/images/kindle/"
CACHE_FOLDER_IMAGES_IBOOKS = CACHE_FOLDER+"/images/ibooks/"
CACHE_FOLDER_IMAGES_CALIBRE = CACHE_FOLDER+"/images/calibre/"
TIMESTAMP_KINDLE = CACHE_FOLDER+"/timestamp_kindle.txt"
TIMESTAMP_IBOOKS = CACHE_FOLDER+"/timestamp_ibooks.txt"
TIMESTAMP_YOMU = CACHE_FOLDER+"/timestamp_yomu.txt"
TIMESTAMP_CALIBRE = CACHE_FOLDER+"/timestamp_calibre.txt"



MY_URL_STRING = "https://ecx.images-amazon.com/images/P/"





def move_images_to_newFolder(parent_folder, newFolder):
    """
    Compatibility with previous version and file structure 
    moving existing cover images from the previous version of the workflow to the new folder structure
    Note: this function can be removed in future versions
    
    """    
    
    # Get a list of all files in the parent folder
    for file_name in os.listdir(parent_folder):
        # Construct the full file path
        file_path = os.path.join(parent_folder, file_name)

        # Check if the file is an image (you can add more extensions if needed)
        if os.path.isfile(file_path):
            # Move the file to the subfolder
            shutil.move(file_path, newFolder)
            



if not os.path.exists(CACHE_FOLDER):
    os.makedirs(CACHE_FOLDER)
if not os.path.exists(CACHE_FOLDER_IMAGES_KINDLE):
    os.makedirs(CACHE_FOLDER_IMAGES_KINDLE)
    move_images_to_newFolder(CACHE_FOLDER+"/images/", CACHE_FOLDER_IMAGES_KINDLE)
if not os.path.exists(CACHE_FOLDER_IMAGES_IBOOKS):
    os.makedirs(CACHE_FOLDER_IMAGES_IBOOKS)
if not os.path.exists(CACHE_FOLDER_IMAGES_CALIBRE):
    os.makedirs(CACHE_FOLDER_IMAGES_CALIBRE)

if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# Per-highlight QuickLook JPG cache. Mirrors the readwise-workflow
# pattern: each highlight is rendered to a JPG once (lazily, on first
# drill-down) and Alfred's `quicklookurl` points at it so Space / ⇧
# pops a rendered preview. Files live in the volatile cache folder so
# they're safe to delete; they'll be regenerated on next access.
#
# HIGHLIGHT_RENDER_VERSION is baked into the cached filename so that
# changes to the renderer (font, layout, auto-height, colour palette,
# …) automatically invalidate every previously rendered bitmap – the
# same highlight gets a new filename and the old one simply becomes
# an orphan until it's pruned.
#
# Bump history:
#   v1 — initial JPG renderer (1200×800 fixed, NewYork/Georgia).
#   v2 — Newsreader Medium body, auto-fit height, normalized
#        intra-paragraph whitespace, darker ink, q=85 JPG.
HIGHLIGHT_RENDER_VERSION = "v2"
HIGHLIGHTS_IMG_FOLDER = f"{CACHE_FOLDER}/highlights_img/"
if not os.path.exists(HIGHLIGHTS_IMG_FOLDER):
    os.makedirs(HIGHLIGHTS_IMG_FOLDER)

# Bump the suffix whenever the Book schema changes so old caches are ignored
# without manual --refresh. v2 introduces the Book.tags field (Yomu tags,
# Calibre tags, Apple Books Collections). v3 adds highlights_count.
_PICKLE_VERSION = "v3"
KINDLE_PICKLE = f"{DATA_FOLDER}/kindle_books_{_PICKLE_VERSION}.pkl"
IBOOKS_PICKLE = f"{DATA_FOLDER}/ibooks_books_{_PICKLE_VERSION}.pkl"
YOMU_PICKLE = f"{DATA_FOLDER}/yomu_books_{_PICKLE_VERSION}.pkl"
CALIBRE_PICKLE = f"{DATA_FOLDER}/calibre_books_{_PICKLE_VERSION}.pkl"

# Highlights live in their own pickles, one per source, so that a Book object
# stays small (just a count) and a highlights query can load just the needed
# source without touching the books list.
_HIGHLIGHTS_VERSION = "v1"
KINDLE_HL_PICKLE = f"{DATA_FOLDER}/kindle_highlights_{_HIGHLIGHTS_VERSION}.pkl"
IBOOKS_HL_PICKLE = f"{DATA_FOLDER}/ibooks_highlights_{_HIGHLIGHTS_VERSION}.pkl"
YOMU_HL_PICKLE = f"{DATA_FOLDER}/yomu_highlights_{_HIGHLIGHTS_VERSION}.pkl"
CALIBRE_HL_PICKLE = f"{DATA_FOLDER}/calibre_highlights_{_HIGHLIGHTS_VERSION}.pkl"

# Yomu defaults (can be overridden via environment variables in Alfred)
YOMU_CONTAINER_ID = os.getenv('YOMU_CONTAINER_ID', 'net.cecinestpasparis.yomu')
YOMU_DATA_DB = os.path.expanduser(
    os.getenv(
        'YOMU_DATA_DB',
        f"~/Library/Containers/{YOMU_CONTAINER_ID}/Data/Documents/Yomu/Yomu_data.sqlite",
    )
)
YOMU_EPUB_CACHE_DIR = os.path.expanduser(
    os.getenv(
        'YOMU_EPUB_CACHE_DIR',
        f"~/Library/Containers/{YOMU_CONTAINER_ID}/Data/Library/Caches/EBook/EPub",
    )
)
CALIBRE_LIBRARY_PATH = os.path.expanduser(
    (os.getenv('CALIBRE_LIBRARY_PATH', "~/Calibre Library") or "~/Calibre Library").strip()
)
_calibre_metadata_env = (os.getenv('CALIBRE_METADATA_DB', '') or '').strip()
_calibre_metadata_from_library = os.path.join(CALIBRE_LIBRARY_PATH, "metadata.db")
if _calibre_metadata_env:
    _calibre_metadata_candidate = os.path.expanduser(_calibre_metadata_env)
else:
    _calibre_metadata_candidate = _calibre_metadata_from_library

# If an explicit metadata path is stale/missing but the library-derived one exists,
# prefer the library-derived DB so CALIBRE_LIBRARY_PATH works as expected.
if (
    _calibre_metadata_candidate != _calibre_metadata_from_library
    and not os.path.exists(_calibre_metadata_candidate)
    and os.path.exists(_calibre_metadata_from_library)
):
    _calibre_metadata_candidate = _calibre_metadata_from_library

CALIBRE_METADATA_DB = _calibre_metadata_candidate

def log(s, *args):
    if args:
        s = s % args
    print(s, file=sys.stderr)


def defineKindleFolder ():
    """
    a function to find the kindle folder
    it will look for the newer kindle app, then the classic one, so if both are present it will use the new one

    """


    # checking the possible kindle folders
    pathA = os.path.expanduser('~')+'/Library/Containers/com.amazon.Lassen/Data/Library/'
    pathB = os.path.expanduser('~')+'/Library/Containers/com.amazon.Kindle/Data/Library/Application Support/Kindle/'
    pathC = os.path.expanduser('~')+'/Library/Application Support/Kindle/'
    

    if (os.path.exists(pathA)):
        kindle_path = pathA
        KINDLE_CONTENT = kindle_path+'Protected/BookData.sqlite'
        XML_CACHE = kindle_path+'/Cache/KindleSyncMetadataCache.xml'
        log ("using new Kindle app")
        KINDLE_APP = 'new'
        KINDLE_APP_PATH = "/Applications/Amazon Kindle.app"
        

    elif (os.path.exists(pathB)):
        kindle_path = pathB
        XML_CACHE = kindle_path+'/Cache/KindleSyncMetadataCache.xml'
        KINDLE_CONTENT = kindle_path+'/My Kindle Content/'
        log ("using Kindle Classic app")
        KINDLE_APP = 'classic'

    elif (os.path.exists(pathC)):
        kindle_path = pathC
        XML_CACHE = kindle_path+'/Cache/KindleSyncMetadataCache.xml'
        KINDLE_CONTENT = kindle_path+'/My Kindle Content/'
        log ("using Kindle Classic app")
        KINDLE_APP = 'classic'

    else:
        kindle_path = ''
    return XML_CACHE, KINDLE_CONTENT, KINDLE_APP



def define_iBooksFolder ():
    iBooks_path = os.path.expanduser('~/Library/Containers/com.apple.iBooksX/Data/Documents/BKLibrary/')
    dbs = []
    dbs += [each for each in os.listdir(iBooks_path)
            if (each.endswith('.sqlite') and each.startswith('BKLibrary'))]
    db_path = iBooks_path + dbs[0]
    return db_path


def define_iBooksAnnotationDB():
    """
    Locate the Apple Books annotation sqlite file.

    Apple embeds a (non-semantic) version string in the filename, e.g.
    `AEAnnotation_v10312011_1727_local.sqlite`, so we have to glob.
    Returns "" if the folder / file is missing (e.g. Apple Books not used).
    """
    folder = os.path.expanduser(
        '~/Library/Containers/com.apple.iBooksX/Data/Documents/AEAnnotation/'
    )
    if not os.path.isdir(folder):
        return ""
    candidates = [
        f for f in os.listdir(folder)
        if f.startswith('AEAnnotation') and f.endswith('.sqlite')
    ]
    if not candidates:
        return ""
    return folder + candidates[0]


def define_kindle_annotation_paths():
    """
    Return (local_annotation_storage, ksdk_annotation_db) paths for the new
    Kindle (Lassen) app, or ("", "") if not present.

    - `AnnotationStorage` is a CoreData sqlite with positional-only highlight
      data (515 rows in the author's test). We use it for *counts* because
      Amazon strips the highlighted passage text locally.
    - `KSDK/amzn1.account.<id>/annotation.db` is the Kindle SDK sync store
      whose `server_view` table contains JSON payloads. User-typed NOTE text
      is recoverable from `json_metadata` here even though HIGHLIGHT text is
      not.
    """
    base = os.path.expanduser(
        '~/Library/Containers/com.amazon.Lassen/Data/Library/'
    )
    annot_storage = os.path.join(base, 'AnnotationStorage')
    if not os.path.exists(annot_storage):
        annot_storage = ""

    ksdk_db = ""
    ksdk_root = os.path.join(base, 'KSDK')
    if os.path.isdir(ksdk_root):
        for entry in os.listdir(ksdk_root):
            if entry.startswith('amzn1.account.'):
                candidate = os.path.join(ksdk_root, entry, 'annotation.db')
                if os.path.exists(candidate):
                    ksdk_db = candidate
                    break
    return annot_storage, ksdk_db



class Book:
    """
    Storing book information from Kindle and iBooks
    """

    books = 0

    def __init__(self, title, bookID, path, icon_path, author, book_desc,
                 read_pct, source, loaned, downloaded, tags="",
                 highlights_count=0):
        self.title = title
        self.bookID = bookID
        self.path = path
        self.icon_path = icon_path
        self.author = author
        self.book_desc = book_desc if book_desc \
            else "No book description for this title available in Books"
        self.read_pct = '0%' if not read_pct else f"{(read_pct * 100):.1f}%"
        self.source = source
        self.loaned = loaned
        self.downloaded = downloaded
        # Normalized, comma-separated tag string (e.g. Calibre tags, Yomu tags,
        # Apple Books user Collections). Empty string when the source has no tags.
        self.tags = tags or ""
        # Number of highlights/notes this book has, across all local sources
        # that expose them. Populated at query time by joining the highlights
        # pickles into the books list; stored on Book for O(1) access in the
        # UI. Kindle contributes a count even though the highlight *text*
        # isn't recoverable locally.
        self.highlights_count = int(highlights_count or 0)
        Book.books += 1

    def __getattr__(self, name):
        # Backward-compat shim for pickles created before a new attribute
        # existed. Returning a zero/empty value keeps older caches usable
        # until they are rebuilt (pickle filenames are versioned, so this
        # is only a belt-and-braces guard).
        if name == 'tags':
            return ""
        if name == 'highlights_count':
            return 0
        raise AttributeError(name)

    @property
    def tag_list(self):
        """Return tags as a list of trimmed, unique strings (order preserved)."""
        if not self.tags:
            return []
        seen = []
        for raw in self.tags.split(","):
            name = raw.strip()
            if name and name not in seen:
                seen.append(name)
        return seen

    def display_book(self):
        return {
            'title:': self.title,
            'bookID:': self.bookID,
            'path:': self.path,
            'icon_path:': self.icon_path,
            'author:': self.author,
            'read_pct:': self.read_pct,
            'book_desc:': self.book_desc,
            'source:': self.source,
            'loaned:': self.loaned,
            'downloaded:': self.downloaded,
            'tags:': self.tags,
            'highlights_count:': self.highlights_count,
        }


class Highlight:
    """
    One highlight, user-added note, or bookmark extracted from a local
    ebook app. Stored in per-source pickles and grouped onto Book objects
    via (source, book_id).

    Kindle is the awkward case: Amazon doesn't store the selected passage
    text locally for HIGHLIGHT entries, only character offsets. We still
    create a Highlight row for each one so counts and open-in-app work; the
    text field is empty (or holds the user's typed NOTE when present).
    """

    def __init__(
        self,
        book_id,
        source,
        text="",
        note="",
        location="",
        color="",
        created="",
        modified="",
        style="highlight",
        arg="",
    ):
        self.book_id = book_id or ""
        self.source = source or ""
        self.text = (text or "").strip()
        self.note = (note or "").strip()
        self.location = location or ""
        self.color = color or ""
        self.created = created or ""
        self.modified = modified or ""
        # One of: "highlight", "note", "bookmark", "underline".
        self.style = style or "highlight"
        # Alfred `arg` handed to the open handler when the user hits return on
        # this highlight. Each source fills this in with its own URL scheme
        # (e.g. ibooks://..., calibre-open|..., kindle-lassen-open|...).
        self.arg = arg or ""

    @property
    def display_text(self):
        """What to show as the main line in Alfred. Prefers the highlighted
        passage; falls back to the user's note; falls back to a placeholder."""
        if self.text:
            return self.text
        if self.note:
            return self.note
        if self.source == "Kindle":
            return "(Kindle highlight — text not stored locally)"
        return "(empty highlight)"

    @property
    def quicklook_file_id(self):
        """
        Stable, filesystem-safe identifier used to name the cached
        QuickLook JPG for this highlight. Derived from the full
        signature (source, book, location, passage, note, date) so
        the same highlight always resolves to the same file and two
        distinct highlights never collide.

        The `HIGHLIGHT_RENDER_VERSION` prefix is bumped whenever the
        renderer changes in a user-visible way (font, layout, colour
        palette, etc.) so that stale bitmaps from the previous
        render generation aren't silently reused – they simply become
        orphans that `prune_stale_highlight_images()` can clean up.
        """
        import hashlib
        signature = "\x1f".join([
            self.source or "",
            self.book_id or "",
            self.location or "",
            (self.text or "")[:500],
            (self.note or "")[:200],
            self.created or "",
            self.style or "",
        ])
        digest = hashlib.sha1(signature.encode("utf-8")).hexdigest()[:16]
        return f"{HIGHLIGHT_RENDER_VERSION}-{digest}"

    def display_count(self):
        return 'Total books: ' + str(Book.books)




BOOK_CONTENT_SYMBOL = os.path.expanduser(os.getenv('BookContent'))
GHOST_SYMBOL = os.path.expanduser(os.getenv('GhostContent'))
GHOST_RESULTS = os.path.expanduser(os.getenv('SHOW_GHOST'))
SEARCH_SCOPE = os.path.expanduser(os.getenv('SEARCH_SCOPE'))


def env_flag(name, default='1'):
    return os.getenv(name, default) not in ['0', 'false', 'False', '']


USE_KINDLE = env_flag('USE_KINDLE', '1')
USE_IBOOKS = env_flag('USE_IBOOKS', '1')
USE_YOMU = env_flag('USE_YOMU', '1')
USE_CALIBRE = env_flag('USE_CALIBRE', '1')


if USE_KINDLE:
    XML_CACHE, KINDLE_PATH, KINDLE_APP = defineKindleFolder()
    KINDLE_ANNOT_STORAGE, KINDLE_KSDK_ANNOT_DB = define_kindle_annotation_paths()
else:
    XML_CACHE, KINDLE_PATH, KINDLE_APP = '', '', ''
    KINDLE_ANNOT_STORAGE, KINDLE_KSDK_ANNOT_DB = '', ''


IBOOKS_PATH = define_iBooksFolder() if USE_IBOOKS else ''
IBOOKS_ANNOTATION_DB = define_iBooksAnnotationDB() if USE_IBOOKS else ''