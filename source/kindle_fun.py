## support functions for the alfred-eBook workflow

from datetime import datetime, date
from config import (
	log,
	Book,
	Highlight,
	KINDLE_PICKLE,
	IBOOKS_PICKLE,
	YOMU_PICKLE,
	CALIBRE_PICKLE,
	KINDLE_HL_PICKLE,
	IBOOKS_HL_PICKLE,
	YOMU_HL_PICKLE,
	CALIBRE_HL_PICKLE,
	KINDLE_PATH,
	CACHE_FOLDER_IMAGES_KINDLE,
	CACHE_FOLDER_IMAGES_IBOOKS,
	CACHE_FOLDER_IMAGES_CALIBRE,
	MY_URL_STRING,
	YOMU_EPUB_CACHE_DIR,
	CALIBRE_LIBRARY_PATH,
)
import os
import re
import sqlite3
import biplist
import pickle
import xmltodict
import json
import urllib.request
import shutil
import xml.etree.ElementTree as ET



			
def checkMatch (search_string, authorName, title):
				for s in search_string.split():
					if s not in authorName.casefold() and s not in title.casefold():
						return False
				return True


def checkTimeStamp (myFile, timestamp):
	# a function to check the timestamp of the kindle library file and update if it is different from the one stored in a file

	
	new_time = int(os.path.getmtime(myFile))
	
	if not os.path.exists(timestamp):
		with open(timestamp, "w") as f:
			f.write(str(new_time))
			f.close
	
	## checking the timestamp
	with open(timestamp) as f:
		old_time = int(f.readline()) #getting the old UNIX timestamp
		f.close


	if new_time != old_time:
		
		with open(timestamp, "w") as f:
			f.write(str(new_time))
			f.close
		return True
	else:
		return False
	
def getDownloadedASINs(basepath):
	
	myContentBooks = []
	
	# List all subdirectories using scandir()
	try:
		with os.scandir(basepath) as entries:
			for entry in entries:
				if entry.is_dir():
					myContentBooks.append(entry.name.split("_")[0])
		return myContentBooks
	except:
		result= {"items": [{
		"title": "Error: Cannot find Kindle directory",
		"subtitle": basepath,
		"arg": "",
		"icon": {

				"path": "icons/Warning.png"
			}
		}]}
		print (json.dumps(result))


def get_yomu(myDatabase, epub_cache_dir=None):
	"""
	Build a Book list from Yomu's local CoreData/SQLite store.

	Yomu opening uses the document identifiers stored in its local database.
	"""
	if epub_cache_dir is None:
		epub_cache_dir = YOMU_EPUB_CACHE_DIR

	if not myDatabase or not os.path.exists(myDatabase):
		log(f"Yomu database not found: {myDatabase}")
		return []

	conn = sqlite3.connect(myDatabase)
	conn.row_factory = sqlite3.Row
	c = conn.cursor()

	def _yomu_find_cover_path(cache_dir, doc_identifier):
		# 1) Most common (works for some books)
		cover_jpg = f"{cache_dir}/{doc_identifier}/cover.jpg"
		if os.path.exists(cover_jpg):
			return cover_jpg

		# 2) Parse OPF to locate the cover image (Durant uses this)
		for opf_rel in ["content.opf", "OEBPS/content.opf", "OPS/content.opf"]:
			opf_path = f"{cache_dir}/{doc_identifier}/{opf_rel}"
			if not os.path.exists(opf_path):
				continue
			try:
				root = ET.parse(opf_path).getroot()
			except Exception:
				continue

			# Handle namespaced and non-namespaced OPF.
			if root.tag.startswith("{"):
				pkg_ns = root.tag.split("}")[0].strip("{")

				def q(p):
					return p.replace("opf:", f"{{{pkg_ns}}}")
			else:
				def q(p):
					return p.replace("opf:", "")

			cover_id = None
			for m in root.findall(q(".//opf:metadata/opf:meta")):
				if (m.get("name") or "").lower() == "cover":
					cover_id = m.get("content")
					break

			if not cover_id:
				continue

			href = None
			for item in root.findall(q(".//opf:manifest/opf:item")):
				if item.get("id") == cover_id:
					href = item.get("href")
					break

			if not href:
				continue

			# Some OPFs put the file next to the OPF; others use subfolders.
			opf_dir = os.path.dirname(opf_rel)
			if opf_dir:
				cover_path = f"{cache_dir}/{doc_identifier}/{opf_dir}/{href}"
			else:
				cover_path = f"{cache_dir}/{doc_identifier}/{href}"

			if os.path.exists(cover_path):
				return cover_path

		return None

	def _decode_yomu_file_id(file_blob):
		if not file_blob:
			return ""
		try:
			decoded = file_blob[1:].decode("utf-8", "ignore").rstrip("\x00")
			return decoded
		except Exception:
			return ""

	# Tags are in CoreData link table Z_4TAGS (ZDOCUMENT <-> ZTAG).
	# We aggregate tags so each Book becomes one Alfred item.
	query = """
		SELECT
			d.Z_PK,
			d.ZIDENTIFIER,
			d.ZTITLE,
			d.ZAUTHOR,
			d.ZTYPE,
			dm.ZIDENT,
			dd.ZFILE,
			GROUP_CONCAT(t.ZNAME, ', ') AS tags
		FROM ZDOCUMENT d
		LEFT JOIN ZDOCUMENTMETA dm
			ON dm.ZDOCUMENT = d.Z_PK
		LEFT JOIN ZDOCUMENTDATA dd
			ON dd.ZDOCUMENT = d.Z_PK
		LEFT JOIN Z_4TAGS rel
			ON rel.Z_4DOCUMENTS = d.Z_PK
		LEFT JOIN ZTAG t
			ON t.Z_PK = rel.Z_9TAGS
		GROUP BY
			d.Z_PK,
			d.ZIDENTIFIER,
			d.ZTITLE,
			d.ZAUTHOR,
			d.ZTYPE,
			dm.ZIDENT,
			dd.ZFILE
	"""

	books = []
	for row in c.execute(query):
		identifier = row["ZIDENTIFIER"] or ""
		meta_identifier = row["ZIDENT"] or ""
		file_identifier = _decode_yomu_file_id(row["ZFILE"])
		title = row["ZTITLE"] or ""
		author = row["ZAUTHOR"] or ""
		tags = row["tags"] or ""

		# Best-effort icon extraction from Yomu's EPUB cache folder.
		icon_path = _yomu_find_cover_path(epub_cache_dir, identifier) or "icons/ibooks.png"

		book = Book(
			title=title,
			bookID=identifier,
			path=f"yomu-open|{meta_identifier}|{identifier}|{file_identifier}",
			icon_path=icon_path,
			author=author,
			book_desc="",
			read_pct=0.0,
			source="Yomu",
			loaned=0,
			downloaded=1,
			tags=tags,
		)
		books.append(book)

	conn.close()

	with open(YOMU_PICKLE, "wb") as file:
		pickle.dump(books, file)

	return books


def get_calibre(metadata_db_path, calibre_library_path=None):
	"""
	Build a Book list from Calibre's metadata.db.

	Calibre stores book files under:
	  <library>/<relative path from books.path>/<data.name>.<format>
	"""
	if calibre_library_path is None:
		calibre_library_path = CALIBRE_LIBRARY_PATH

	if not metadata_db_path or not os.path.exists(metadata_db_path):
		log(f"Calibre metadata DB not found: {metadata_db_path}")
		with open(CALIBRE_PICKLE, "wb") as file:
			pickle.dump([], file)
		return []

	conn = sqlite3.connect(metadata_db_path)
	conn.row_factory = sqlite3.Row
	c = conn.cursor()

	# Build a per-book map of available formats.
	format_rows = c.execute(
		"SELECT book, format, name FROM data WHERE format IS NOT NULL AND name IS NOT NULL"
	).fetchall()
	formats_by_book = {}
	for row in format_rows:
		book_id = row["book"]
		formats_by_book.setdefault(book_id, []).append(
			{
				"format": (row["format"] or "").lower(),
				"name": row["name"] or "",
			}
		)

	# Pre-aggregate tags per book. Doing it in a sub-select keeps the cardinality
	# of the outer join sane (authors + tags together would multiply rows).
	tag_rows = c.execute(
		"""
		SELECT btl.book AS book_id, t.name AS tag_name
		FROM books_tags_link btl
		JOIN tags t ON t.id = btl.tag
		"""
	).fetchall()
	tags_by_book = {}
	for row in tag_rows:
		tags_by_book.setdefault(row["book_id"], []).append(row["tag_name"] or "")

	query = """
		SELECT
			b.id AS book_id,
			b.title,
			b.path AS book_path,
			b.author_sort,
			cm.text AS comments,
			GROUP_CONCAT(a.name, '; ') AS authors
		FROM books b
		LEFT JOIN comments cm
			ON cm.book = b.id
		LEFT JOIN books_authors_link bal
			ON bal.book = b.id
		LEFT JOIN authors a
			ON a.id = bal.author
		GROUP BY b.id, b.title, b.path, b.author_sort, cm.text
	"""

	preferred_formats = ["epub", "azw3", "kfx", "mobi", "pdf"]
	books = []

	for row in c.execute(query):
		book_id = row["book_id"]
		book_path = row["book_path"] or ""
		title = row["title"] or ""
		author = row["authors"] or row["author_sort"] or ""
		book_desc = row["comments"] or ""
		book_formats = formats_by_book.get(book_id, [])
		book_file = ""

		if book_formats:
			format_map = {fmt["format"]: fmt["name"] for fmt in book_formats if fmt.get("format")}
			selected_format = next(
				(fmt for fmt in preferred_formats if fmt in format_map),
				book_formats[0]["format"],
			)
			filename_base = format_map.get(selected_format)
			if filename_base and book_path:
				book_file = os.path.join(
					calibre_library_path,
					book_path,
					f"{filename_base}.{selected_format}",
				)

		if not book_file:
			continue

		cover_source = os.path.join(calibre_library_path, book_path, "cover.jpg")
		icon_path = f"{CACHE_FOLDER_IMAGES_CALIBRE}{book_id}.jpg"
		if os.path.exists(cover_source):
			try:
				if not os.path.exists(icon_path):
					shutil.copy2(cover_source, icon_path)
			except Exception:
				icon_path = "icons/ibooks.png"
		else:
			icon_path = "icons/ibooks.png"

		book_tags = ", ".join(
			name for name in tags_by_book.get(book_id, []) if name
		)

		book = Book(
			title=title,
			bookID=str(book_id),
			path=f"calibre-open|{book_file}",
			icon_path=icon_path,
			author=author,
			book_desc=book_desc,
			read_pct=0.0,
			source="Calibre",
			loaned=0,
			downloaded=1,
			tags=book_tags,
		)
		books.append(book)

	conn.close()

	with open(CALIBRE_PICKLE, "wb") as file:
		pickle.dump(books, file)

	return books

def get_kindleClassic (myFile, downloaded):
	## Importing the XML table

	with open(myFile) as xml_file:
		data_dict = xmltodict.parse(xml_file.read())
		xml_file.close()


	
	myBooks = data_dict['response']['add_update_list']['meta_data']
	books = []

	for myBook in myBooks:
		if isinstance(myBook['authors']['author'], list):
			myBook ['authorString'] = "; ".join (str(auth['#text']) for auth in myBook['authors']['author'])

		else:
			myBook ['authorString'] = myBook['authors']['author']['#text']


	
		if myBook['ASIN'] in downloaded:
			
			bookURL = f"{KINDLE_PATH}{myBook['ASIN']}_EBOK/{myBook['ASIN']}_EBOK.azw"
			ICON_PATH = f"{CACHE_FOLDER_IMAGES_KINDLE}{myBook['ASIN']}.01"
			isDownloaded = 1
			loaned = 0
			if not os.path.exists(ICON_PATH):
				log ("retrieving image" + ICON_PATH)
				try:
					urllib.request.urlretrieve(f"{MY_URL_STRING}{myBook['ASIN']}.01", ICON_PATH)
				except urllib.error.URLError as e:
					log("Error retrieving image:", e.reason)  # Log the specific error reason


		else:
			isDownloaded = 0
			loaned = 1
			bookURL = f"https://www.amazon.com/dp/{myBook['ASIN']}"
			ICON_PATH = f"{CACHE_FOLDER_IMAGES_KINDLE}{myBook['ASIN']}.01"
			if not os.path.exists(ICON_PATH):
				log ("retrieving image" + ICON_PATH)
				try:
					urllib.request.urlretrieve(f"{MY_URL_STRING}{myBook['ASIN']}.01", ICON_PATH)
				except urllib.error.URLError as e:
					log("Error retrieving image:", e.reason)  # Log the specific error reason

		
		book = Book(
			title=myBook['title']['#text'],
			bookID=myBook['ASIN'],
			path=bookURL,
			icon_path=ICON_PATH,
			author=myBook['authorString'],
			book_desc="",
			read_pct=0,
			source="Kindle",
			loaned=loaned,
			downloaded=isDownloaded
			
			)
		books.append(book)

	# Save the list of books to a file
	with open(KINDLE_PICKLE, 'wb') as file:
		pickle.dump(books, file)

def fetchImageCover(epub_path, ICON_PATH):
	# a function to retrieve the cover image of the book from the ePUB file
	import xml.etree.ElementTree as ET
	
	try:
		# Check if it's a directory (Apple Books format) or a zip file
		if os.path.isdir(epub_path):
			# Handle as directory (Apple Books format)
			container_path = os.path.join(epub_path, 'META-INF', 'container.xml')
			if not os.path.exists(container_path):
				log("Container.xml not found")
				return "icons/ibooks.png"
			
			# Read container.xml to find the OPF file
			with open(container_path, 'rb') as f:
				container_xml = f.read()
			
			# Parse container.xml to find the OPF file
			root = ET.fromstring(container_xml)
			ns = {'ns': 'urn:oasis:names:tc:opendocument:xmlns:container'}
			opf_path = root.find('.//ns:rootfile', ns).get('full-path')
			
			# Read the OPF file
			opf_file_path = os.path.join(epub_path, opf_path)
			if not os.path.exists(opf_file_path):
				log("OPF file not found")
				return "icons/ibooks.png"
			
			with open(opf_file_path, 'rb') as f:
				opf_content = f.read()
			
			# Parse OPF to find manifest items
			opf_root = ET.fromstring(opf_content)
			ns_opf = {'opf': 'http://www.idpf.org/2007/opf'}
			
			# Look for cover-related items in manifest
			manifest_items = opf_root.findall('.//opf:manifest/opf:item', ns_opf)
			cover_items = []
			
			for item in manifest_items:
				item_id = item.get('id', '')
				href = item.get('href', '')
				media_type = item.get('media-type', '')
				
				# Look for cover images (various naming conventions)
				if ('cover' in item_id.lower() or 'cover' in href.lower()) and media_type.startswith('image/'):
					cover_items.append((item_id, href, media_type))
			
			# If no cover items found, look for any image files
			if not cover_items:
				for item in manifest_items:
					item_id = item.get('id', '')
					href = item.get('href', '')
					media_type = item.get('media-type', '')
					
					if media_type.startswith('image/'):
						cover_items.append((item_id, href, media_type))
			
			# Try to extract the cover image
			if cover_items:
				# Use the first cover item
				_, href, _ = cover_items[0]
				
				# Resolve relative path
				opf_dir = os.path.dirname(opf_path)
				if opf_dir:
					cover_path = os.path.join(epub_path, opf_dir, href)
				else:
					cover_path = os.path.join(epub_path, href)
				
				if os.path.exists(cover_path):
					shutil.copy2(cover_path, ICON_PATH)
					log(f"cover image copied from {cover_path}")
					return ICON_PATH
				else:
					log(f"cover image not found at {cover_path}")
			
			# Fallback: check for common cover file names directly in EPUB root
			common_cover_names = ['cover.jpeg', 'cover.jpg', 'cover.png', 'cover.gif']
			for cover_name in common_cover_names:
				cover_path = os.path.join(epub_path, cover_name)
				if os.path.exists(cover_path):
					shutil.copy2(cover_path, ICON_PATH)
					log(f"cover image copied from {cover_path}")
					return ICON_PATH
			
			log("no cover image found")
			return "icons/ibooks.png"
			
		else:
			# Handle as zip file (traditional EPUB format)
			import zipfile
			with zipfile.ZipFile(epub_path, 'r') as epub:
				# Read container.xml to find the OPF file
				container_xml = epub.read('META-INF/container.xml')
				
				# Parse container.xml to find the OPF file
				root = ET.fromstring(container_xml)
				ns = {'ns': 'urn:oasis:names:tc:opendocument:xmlns:container'}
				opf_path = root.find('.//ns:rootfile', ns).get('full-path')
				
				# Read the OPF file
				opf_content = epub.read(opf_path)
				
				# Parse OPF to find manifest items
				opf_root = ET.fromstring(opf_content)
				ns_opf = {'opf': 'http://www.idpf.org/2007/opf'}
				
				# Look for cover-related items in manifest
				manifest_items = opf_root.findall('.//opf:manifest/opf:item', ns_opf)
				cover_items = []
				
				for item in manifest_items:
					item_id = item.get('id', '')
					href = item.get('href', '')
					media_type = item.get('media-type', '')
					
					# Look for cover images (various naming conventions)
					if ('cover' in item_id.lower() or 'cover' in href.lower()) and media_type.startswith('image/'):
						cover_items.append((item_id, href, media_type))
				
				# If no cover items found, look for any image files
				if not cover_items:
					for item in manifest_items:
						item_id = item.get('id', '')
						href = item.get('href', '')
						media_type = item.get('media-type', '')
						
						if media_type.startswith('image/'):
							cover_items.append((item_id, href, media_type))
				
				# Try to extract the cover image
				if cover_items:
					# Use the first cover item
					_, href, _ = cover_items[0]
					
					# Resolve relative path
					opf_dir = os.path.dirname(opf_path)
					if opf_dir:
						cover_path = os.path.join(opf_dir, href)
					else:
						cover_path = href
					
					if cover_path in epub.namelist():
						with open(ICON_PATH, 'wb') as f:
							f.write(epub.read(cover_path))
						log(f"cover image extracted from {cover_path}")
						return ICON_PATH
				
				# Fallback: check for common cover file names
				common_cover_names = ['cover.jpeg', 'cover.jpg', 'cover.png', 'cover.gif']
				for cover_name in common_cover_names:
					if cover_name in epub.namelist():
						with open(ICON_PATH, 'wb') as f:
							f.write(epub.read(cover_name))
						log(f"cover image extracted from {cover_name}")
						return ICON_PATH
				
				log("no cover image found")
				return "icons/ibooks.png"
				
	except Exception as e:
		log(f"Error extracting cover image: {e}")
		return "icons/ibooks.png"

	

def _get_ibooks_collections(conn):
	"""
	Return dict: asset_id (ZASSETID) -> list of user-facing Collection names.

	Apple Books keeps Collections in the same BKLibrary sqlite the rest of
	get_ibooks already reads. We filter out Apple-managed "library type"
	collections (All / Books / PDFs / Audiobooks / My Books) which are
	automatic and not useful as tags. User-managed collections (both the
	built-ins like "Want to Read" / "Finished" and custom UUID-ID ones) are
	kept.

	Runs defensively: if the tables are missing on this macOS version we
	return an empty dict instead of breaking the library build.
	"""
	collections = {}
	try:
		cur = conn.cursor()
		tables = {
			row[0]
			for row in cur.execute(
				"SELECT name FROM sqlite_master WHERE type='table'"
			)
		}
		if 'ZBKCOLLECTION' not in tables or 'ZBKCOLLECTIONMEMBER' not in tables:
			return collections

		# Apple's library-type and auto-populated collections carry fixed
		# ZCOLLECTIONIDs. We skip these because they are automatic and would
		# add noise (e.g. every downloaded book is in "Downloaded"). User-
		# manageable system shelves like "Want to Read" and "Finished" are
		# kept because users actually curate them.
		system_ids = {
			'All_Collection_ID',
			'Books_Collection_ID',
			'Pdfs_Collection_ID',
			'AudioBooks_Collection_ID',
			'Downloaded_Collection_ID',
			'Samples_Collection_ID',
		}

		rows = cur.execute(
			"""
			SELECT m.ZASSETID AS asset_id, col.ZTITLE AS title, col.ZCOLLECTIONID AS cid
			FROM ZBKCOLLECTIONMEMBER m
			JOIN ZBKCOLLECTION col
				ON col.Z_PK = m.ZCOLLECTION
			WHERE m.ZASSETID IS NOT NULL
				AND col.ZTITLE IS NOT NULL
				AND COALESCE(col.ZHIDDEN, 0) = 0
				AND COALESCE(col.ZDELETEDFLAG, 0) = 0
			"""
		).fetchall()

		for r in rows:
			aid = r['asset_id']
			title = (r['title'] or '').strip()
			cid = r['cid'] or ''
			if not aid or not title:
				continue
			if cid in system_ids:
				continue
			if cid.startswith('My_Books_Collection_'):
				continue
			bucket = collections.setdefault(aid, [])
			if title not in bucket:
				bucket.append(title)
	except Exception as e:
		log(f"iBooks collections lookup failed: {e}")
	return collections


def get_ibooks(myDatabase):
	books = []
	if not myDatabase or not os.path.exists(myDatabase):
		log(f"Apple Books database not found: {myDatabase}")
		with open(IBOOKS_PICKLE, "wb") as file:
			pickle.dump(books, file)
		return books
	conn = sqlite3.connect(myDatabase)
	conn.row_factory = sqlite3.Row
	c = conn.cursor()
	collections_by_asset = _get_ibooks_collections(conn)
	c.execute('''SELECT "_rowid_",* FROM "main"."ZBKLIBRARYASSET" ORDER BY "_rowid_" ASC LIMIT 0, 49999;''')
	data = c.fetchall()
	
	for row in data:
		row = dict(row)
		if row['ZSTATE'] == 5:
			continue
		elif row['ZSTATE'] == 3:
			downloaded = 0
		elif row['ZSTATE'] == 1:
			downloaded = 1
		
		
		
		# downloading the cover
			
		ICON_PATH = f"{CACHE_FOLDER_IMAGES_IBOOKS}{row['ZASSETID']}"

		if not os.path.exists(ICON_PATH) and row['ZCOVERURL'] is not None:
			try:
				urllib.request.urlretrieve(row['ZCOVERURL'], ICON_PATH)
			except urllib.error.URLError as e:
				log("Error retrieving image:", e.reason)  # Log the specific error reason

		
		elif not os.path.exists(ICON_PATH) and row['ZPATH'] is not None:
			if row['ZPATH'].endswith('.epub'):
				log ("trying to retrieve image from ePUB file: " + row['ZPATH'])
				try:
					ICON_PATH = fetchImageCover (row['ZPATH'], ICON_PATH)
				except:
					log("Error retrieving image") 
			else:
				ICON_PATH = "icons/ibooks.png"
		elif not os.path.exists(ICON_PATH):
			ICON_PATH = "icons/ibooks.png"
			
		
		book_tags = ", ".join(collections_by_asset.get(row['ZASSETID'], []))

		book = Book(
			title=row['ZTITLE'],
			bookID=row['ZASSETID'] or "",
			path=row['ZPATH'],
			icon_path=ICON_PATH,
			author=row['ZAUTHOR'],
			book_desc=row['ZBOOKDESCRIPTION'],
			read_pct=row['ZREADINGPROGRESS'],
			source="iBooks",
			loaned=0,
			downloaded=downloaded,
			tags=book_tags,
		)
		books.append(book)

	conn.close()

	# Save the list of books to a file
	with open(IBOOKS_PICKLE, 'wb') as file:
		pickle.dump(books, file)
	
	
def get_kindle(myDatabase):
	"""
    a function to build the kindle database for the new kindle app


    """
	if not myDatabase or not os.path.exists(myDatabase):
		log(f"Kindle database not found: {myDatabase}")
		with open(KINDLE_PICKLE, "wb") as file:
			pickle.dump([], file)
		return []

	# Connect to the SQLite database
	conn = sqlite3.connect(myDatabase)
	conn.row_factory = sqlite3.Row
	cursor = conn.cursor()

	# Select the rows with BLOB data
	query = f"SELECT rowid, ZSYNCMETADATAATTRIBUTES, ZDISPLAYTITLE, ZRAWCURRENTPOSITION, ZRAWMAXPOSITION,ZRAWBOOKSTATE, ZBOOKID, ZRAWREADSTATE FROM ZBOOK WHERE ZRAWBOOKTYPE IN (10, 13)"

	cursor.execute(query)


	books = []
	loanCount = 0
	for row in cursor.fetchall():
		
		rowid, blob_data, title, currPos, maxPos, downStatus, asinRaw, isRead = row
		
        # Skip if blob_data is None
		if blob_data is None:
			authorName = ''
		else: 	# Attempt to decode the blob data to text
			try:
				plist_data = biplist.readPlistFromString(blob_data)
				# Search for the string in the decoded text
				authorRow = plist_data['$objects'].index('author')
				authorName = plist_data['$objects'][authorRow+1]
				
				if 'Purchase' in plist_data['$objects']:
						loaned = 0
						
				elif 'PublicLibraryLending' in plist_data['$objects']:
					loaned = 1
					loanCount += 1
					#log (f"Loaned! title: {title}, total: {loanCount}")
				
				if not isinstance(authorName, str):
					
					myAuthorIDs = authorName['NS.objects']
					myAuthorIDs = [int(str(uid).strip('Uid()')) for uid in myAuthorIDs]
					# Fetch elements from list B and join them
					authorName = '; '.join([plist_data['$objects'][i] for i in myAuthorIDs])
					
			except (biplist.InvalidPlistException, biplist.NotBinaryPlistException):
				log("Failed to decode BLOB data as a plist.")
				authorName = ''
			
			if isRead == 1:
				percentRead = 1.0
			else:
				try:
					percentRead = currPos/maxPos

				except:
					percentRead = 0.0
				
			# downloading the cover
			ASIN = asinRaw[2:-2]
			ICON_PATH = f"{CACHE_FOLDER_IMAGES_KINDLE}{ASIN}.01"

			bookURL = f"https://www.amazon.com/dp/{ASIN}"
			
			if not os.path.exists(ICON_PATH):
				log ("retrieving image" + ICON_PATH)
				try:
					urllib.request.urlretrieve(f"{MY_URL_STRING}{ASIN}.01", ICON_PATH)
				except urllib.error.URLError as e:
					ICON_PATH = "icons/kindle.png"
					log("Error retrieving image:", e.reason)  # Log the specific error reason

			
			if downStatus == 3:
				downStatus = 1
			else:
				downStatus = 0
			 
		book = Book(
				title=title,
				bookID=ASIN,
				path=bookURL,
				icon_path=ICON_PATH,
				author=authorName,
				book_desc="",
				read_pct=percentRead,
				source = "Kindle",
				loaned=loaned,
				downloaded=downStatus
				)
		books.append(book)
		

            
	
	conn.close()
	# pickle the books object
	with open(KINDLE_PICKLE, 'wb') as file:
		pickle.dump(books, file)
	log ("building kindle database")
	log ("done 👍")
	return books


# ---------------------------------------------------------------------------
# Highlights extractors. Each returns a list[Highlight] and pickles it to the
# corresponding *_HL_PICKLE file. All are best-effort and log + return [] when
# the source DB isn't available, so the main query path can call them
# unconditionally.
# ---------------------------------------------------------------------------


# Core Data / CFAbsoluteTime uses a Jan-1-2001 epoch; convert to ISO-ish.
_CORE_DATA_EPOCH_OFFSET = 978307200  # seconds between 1970-01-01 and 2001-01-01


def _core_data_ts_to_iso(ts):
	if ts is None:
		return ""
	try:
		unix = float(ts) + _CORE_DATA_EPOCH_OFFSET
		return datetime.utcfromtimestamp(unix).strftime("%Y-%m-%d %H:%M")
	except Exception:
		return ""


def _unix_ms_to_iso(ts):
	if ts is None:
		return ""
	try:
		unix = float(ts)
		# The Kindle KSDK stores ms-since-epoch; some rows are seconds already.
		if unix > 1e12:
			unix = unix / 1000.0
		return datetime.utcfromtimestamp(unix).strftime("%Y-%m-%d %H:%M")
	except Exception:
		return ""


def get_ibooks_highlights(annotation_db_path):
	"""
	Pull highlights + notes from Apple Books' AEAnnotation sqlite.
	Links back to Book.bookID via ZANNOTATIONASSETID.
	"""
	highlights = []
	if not annotation_db_path or not os.path.exists(annotation_db_path):
		log(f"iBooks annotation DB not found: {annotation_db_path}")
		with open(IBOOKS_HL_PICKLE, "wb") as f:
			pickle.dump(highlights, f)
		return highlights

	try:
		conn = sqlite3.connect(f"file:{annotation_db_path}?mode=ro", uri=True)
	except Exception as e:
		log(f"iBooks annotation DB open failed: {e}")
		with open(IBOOKS_HL_PICKLE, "wb") as f:
			pickle.dump(highlights, f)
		return highlights

	conn.row_factory = sqlite3.Row
	try:
		rows = conn.execute(
			"""
			SELECT
				ZANNOTATIONASSETID AS asset_id,
				ZANNOTATIONSELECTEDTEXT AS text,
				ZANNOTATIONNOTE AS note,
				ZANNOTATIONLOCATION AS location,
				ZANNOTATIONSTYLE AS style,
				ZANNOTATIONISUNDERLINE AS is_underline,
				ZANNOTATIONCREATIONDATE AS created,
				ZANNOTATIONMODIFICATIONDATE AS modified
			FROM ZAEANNOTATION
			WHERE COALESCE(ZANNOTATIONDELETED, 0) = 0
				AND ZANNOTATIONASSETID IS NOT NULL
				AND (
					ZANNOTATIONSELECTEDTEXT IS NOT NULL
					OR ZANNOTATIONNOTE IS NOT NULL
				)
			"""
		).fetchall()
	except Exception as e:
		log(f"iBooks annotation DB query failed: {e}")
		rows = []
	finally:
		conn.close()

	for row in rows:
		asset_id = row["asset_id"] or ""
		text = row["text"] or ""
		note = row["note"] or ""
		style_name = "underline" if row["is_underline"] else "highlight"
		if not text and note:
			style_name = "note"
		h = Highlight(
			book_id=asset_id,
			source="iBooks",
			text=text,
			note=note,
			location=row["location"] or "",
			color=str(row["style"]) if row["style"] is not None else "",
			created=_core_data_ts_to_iso(row["created"]),
			modified=_core_data_ts_to_iso(row["modified"]),
			style=style_name,
			# ibooks://assetid/<uuid> is the documented deep-link scheme for
			# opening a specific asset in Apple Books. There's no reliable
			# CFI-based deep-link (Apple doesn't expose one), so we just open
			# the book; the user lands roughly where they left off.
			arg=f"ibooks://assetid/{asset_id}" if asset_id else "",
		)
		highlights.append(h)

	with open(IBOOKS_HL_PICKLE, "wb") as f:
		pickle.dump(highlights, f)
	log(f"iBooks highlights: {len(highlights)}")
	return highlights


def get_calibre_highlights(metadata_db_path):
	"""
	Pull highlights + notes from Calibre's metadata.db `annotations` table.
	Calibre 5.x+ stores the highlighted text in `searchable_text` and a JSON
	blob with start/end CFIs in `annot_data`. Only populated for books opened
	in Calibre's Viewer — imported-but-never-viewed books have no annotations.
	"""
	highlights = []
	if not metadata_db_path or not os.path.exists(metadata_db_path):
		with open(CALIBRE_HL_PICKLE, "wb") as f:
			pickle.dump(highlights, f)
		return highlights

	try:
		conn = sqlite3.connect(f"file:{metadata_db_path}?mode=ro", uri=True)
	except Exception as e:
		log(f"Calibre DB open failed: {e}")
		with open(CALIBRE_HL_PICKLE, "wb") as f:
			pickle.dump(highlights, f)
		return highlights

	conn.row_factory = sqlite3.Row
	try:
		tables = {
			r[0] for r in conn.execute(
				"SELECT name FROM sqlite_master WHERE type='table'"
			)
		}
		if 'annotations' not in tables:
			log("Calibre annotations table not present (older Calibre?)")
			with open(CALIBRE_HL_PICKLE, "wb") as f:
				pickle.dump(highlights, f)
			return highlights

		rows = conn.execute(
			"""
			SELECT
				book AS book_id,
				annot_type AS annot_type,
				annot_data AS annot_data,
				searchable_text AS searchable_text,
				timestamp AS timestamp,
				format AS format
			FROM annotations
			"""
		).fetchall()
	except Exception as e:
		log(f"Calibre annotations query failed: {e}")
		rows = []
	finally:
		conn.close()

	for row in rows:
		data = {}
		try:
			data = json.loads(row["annot_data"] or "{}")
		except Exception:
			pass

		text = (data.get("highlighted_text") or row["searchable_text"] or "").strip()
		note = (data.get("notes") or "").strip()
		start_cfi = data.get("start_cfi") or data.get("pos") or ""

		style_name = (row["annot_type"] or "highlight").lower()
		# Calibre uses "bookmark" / "highlight"; map unknowns to "highlight".
		if style_name not in ("highlight", "bookmark", "note"):
			style_name = "highlight"

		created = ""
		try:
			ts = row["timestamp"]
			if ts is not None:
				created = datetime.utcfromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
		except Exception:
			pass

		book_id_str = str(row["book_id"])
		h = Highlight(
			book_id=book_id_str,
			source="Calibre",
			text=text,
			note=note,
			location=start_cfi,
			color=str(data.get("style", {}).get("kind", "")) if isinstance(data.get("style"), dict) else "",
			created=created,
			modified=created,
			style=style_name,
			# The existing calibre-open handler takes `calibre-open|<file>` and
			# optionally a trailing `|<location>`. We don't know the file path
			# here (that lives on Book.path), so hand the query layer just the
			# book id + CFI and let it join at display time.
			arg=f"calibre-highlight|{book_id_str}|{start_cfi}",
		)
		highlights.append(h)

	with open(CALIBRE_HL_PICKLE, "wb") as f:
		pickle.dump(highlights, f)
	log(f"Calibre highlights: {len(highlights)}")
	return highlights


def get_yomu_highlights(yomu_data_db):
	"""
	Pull highlights + notes from Yomu's CoreData ZANNOTATION table. Joined to
	ZDOCUMENT so we can emit the Yomu document identifier as book_id (matches
	Book.bookID for Yomu rows).
	"""
	highlights = []
	if not yomu_data_db or not os.path.exists(yomu_data_db):
		with open(YOMU_HL_PICKLE, "wb") as f:
			pickle.dump(highlights, f)
		return highlights

	try:
		conn = sqlite3.connect(f"file:{yomu_data_db}?mode=ro", uri=True)
	except Exception as e:
		log(f"Yomu DB open failed: {e}")
		with open(YOMU_HL_PICKLE, "wb") as f:
			pickle.dump(highlights, f)
		return highlights

	conn.row_factory = sqlite3.Row
	try:
		# NOTE on ZSTATE: Yomu stores a small integer here whose meaning
		# isn't publicly documented. Empirically, a locally-created
		# highlight has ZSTATE=1 (NOT 0), so an earlier `ZSTATE = 0`
		# filter silently dropped every real user highlight. Until we
		# identify a specific state value that reliably means
		# "soft-deleted / archived", we include every row and let the
		# downstream code treat it as active. If users ever report that
		# deleted highlights resurface here, revisit this with a known
		# bad state value.
		rows = conn.execute(
			"""
			SELECT
				a.ZTEXT AS text,
				a.ZANNOTATION AS note,
				a.ZTYPE AS type,
				a.ZREF AS ref,
				a.ZCREATED AS created,
				a.ZMODIFIED AS modified,
				a.ZSTATE AS state,
				d.ZIDENTIFIER AS doc_identifier
			FROM ZANNOTATION a
			LEFT JOIN ZDOCUMENT d ON d.Z_PK = a.ZDOCUMENT
			"""
		).fetchall()
	except Exception as e:
		log(f"Yomu annotations query failed: {e}")
		rows = []
	finally:
		conn.close()

	for row in rows:
		doc_id = row["doc_identifier"] or ""
		style_name = (row["type"] or "highlight").lower()
		if style_name not in ("highlight", "note", "bookmark", "underline"):
			style_name = "highlight"
		h = Highlight(
			book_id=doc_id,
			source="Yomu",
			text=row["text"] or "",
			note=row["note"] or "",
			location=row["ref"] or "",
			created=_core_data_ts_to_iso(row["created"]),
			modified=_core_data_ts_to_iso(row["modified"]),
			style=style_name,
			# Reuse the existing yomu-open handler, which re-opens the book by
			# document identifier. Yomu has no known CFI deep-link scheme.
			arg=f"yomu-open||{doc_id}|" if doc_id else "",
		)
		highlights.append(h)

	with open(YOMU_HL_PICKLE, "wb") as f:
		pickle.dump(highlights, f)
	log(f"Yomu highlights: {len(highlights)}")
	return highlights


# Regex to pull the ASIN out of Kindle annotation identifiers like
# "A:B00DACZ9K6-0" (ZRAWBOOKID) and "B00C5R7HMU-EBOK-CR!...-1" (dataset_id).
_KINDLE_ASIN_RE = re.compile(r'(?:^|[^A-Z0-9])([A-Z0-9]{10})(?:[^A-Z0-9]|$)')


def _extract_kindle_asin(raw):
	if not raw:
		return ""
	m = _KINDLE_ASIN_RE.search(raw)
	return m.group(1) if m else ""


def get_kindle_highlights(annot_storage_path, ksdk_annot_db_path):
	"""
	Build a Highlight list for the new Kindle (Lassen) app.

	Amazon strips the selected *passage text* from the local DBs, so HIGHLIGHT
	entries carry no `text`. We still emit them so per-book counts work and so
	the user can see their notes + jump to the cloud notebook. NOTE entries
	have a user-typed `note_text` in the KSDK payload and *are* recoverable.

	We prefer KSDK rows when both stores reference the same annotation because
	KSDK carries the note payload and timestamps in ms. Entries from
	AnnotationStorage that aren't in KSDK are added by (ASIN, ZLONGPOSITION)
	so counts stay correct when the sync layer is behind.
	"""
	highlights = []

	by_key = {}

	# KSDK pass. Each row has a JSON payload with type, positions, note text,
	# and modification time.
	if ksdk_annot_db_path and os.path.exists(ksdk_annot_db_path):
		try:
			conn = sqlite3.connect(f"file:{ksdk_annot_db_path}?mode=ro", uri=True)
			conn.row_factory = sqlite3.Row
			try:
				tables = {
					r[0] for r in conn.execute(
						"SELECT name FROM sqlite_master WHERE type='table'"
					)
				}
				if 'server_view' in tables:
					rows = conn.execute(
						"""
						SELECT dataset_id, annotation_id, serialized_payload,
							created_time, modified_time
						FROM server_view
						"""
					).fetchall()
				else:
					rows = []
			finally:
				conn.close()
		except Exception as e:
			log(f"Kindle KSDK open/query failed: {e}")
			rows = []

		for row in rows:
			try:
				payload = json.loads(row["serialized_payload"] or "{}")
			except Exception:
				continue

			book_data = payload.get("book_data") or {}
			asin = (book_data.get("asin") or "").strip()
			if not asin:
				asin = _extract_kindle_asin(row["dataset_id"])
			if not asin:
				continue

			p_type = (payload.get("type") or "").upper()
			style_name = {
				"HIGHLIGHT": "highlight",
				"NOTE": "note",
				"BOOKMARK": "bookmark",
			}.get(p_type, "highlight")
			# Skip bookmarks from counts+UI by default; they're not highlights.
			if style_name == "bookmark":
				continue

			note_text = ""
			try:
				jm = payload.get("json_metadata")
				if isinstance(jm, str) and jm:
					jm = json.loads(jm)
				if isinstance(jm, dict):
					note_text = (jm.get("note_text") or "").strip()
			except Exception:
				pass

			start = payload.get("start_position", {}) or {}
			end = payload.get("end_position", {}) or {}
			start_pos = start.get("shortPosition") or start.get("longPosition") or ""
			end_pos = end.get("shortPosition") or end.get("longPosition") or ""
			location = f"{start_pos}-{end_pos}" if (start_pos or end_pos) else ""

			modified = payload.get("last_modified") or row["modified_time"]

			key = (asin, str(start_pos), str(end_pos))
			h = Highlight(
				book_id=asin,
				source="Kindle",
				text="",  # Amazon does not expose the selected passage locally
				note=note_text,
				location=location,
				created=_unix_ms_to_iso(row["created_time"]),
				modified=_unix_ms_to_iso(modified),
				style=style_name,
				# Amazon's cloud notebook is the only place the highlight text
				# actually exists, so we deep-link there.
				arg=f"https://read.amazon.com/notebook?asin={asin}&contentLimitState=&",
			)
			by_key[key] = h

	# AnnotationStorage fallback for anything KSDK didn't see.
	if annot_storage_path and os.path.exists(annot_storage_path):
		try:
			conn = sqlite3.connect(f"file:{annot_storage_path}?mode=ro", uri=True)
			conn.row_factory = sqlite3.Row
			try:
				rows = conn.execute(
					"""
					SELECT ZRAWBOOKID AS raw_book_id,
						ZLONGSTART AS long_start,
						ZLONGEND AS long_end,
						ZRAWSTART AS raw_start,
						ZRAWEND AS raw_end,
						ZRAWANNOTATIONTYPE AS annot_type,
						ZUSERTEXT AS user_text,
						ZNUMHIGHLIGHTERS AS num_highlighters
					FROM ZANNOTATION
					"""
				).fetchall()
			finally:
				conn.close()
		except Exception as e:
			log(f"Kindle AnnotationStorage open/query failed: {e}")
			rows = []

		for row in rows:
			asin = _extract_kindle_asin(row["raw_book_id"])
			if not asin:
				continue
			# ZRAWANNOTATIONTYPE examples: "lpr" (last page read), "hlt"
			# (highlight), "nt" (note), "bkm" (bookmark). Keep highlights and
			# notes; skip the rest so progress bookmarks don't inflate counts.
			t = (row["annot_type"] or "").lower()
			if t not in ("hlt", "nt", ""):
				continue
			style_name = {"hlt": "highlight", "nt": "note"}.get(t, "highlight")

			start = row["long_start"] or str(row["raw_start"] or "")
			end = row["long_end"] or str(row["raw_end"] or "")
			key = (asin, str(start), str(end))
			if key in by_key:
				# Already covered by KSDK row, which has richer metadata.
				continue
			h = Highlight(
				book_id=asin,
				source="Kindle",
				text="",
				note=(row["user_text"] or "").strip(),
				location=f"{start}-{end}" if (start or end) else "",
				style=style_name,
				arg=f"https://read.amazon.com/notebook?asin={asin}&contentLimitState=&",
			)
			by_key[key] = h

	highlights = list(by_key.values())

	with open(KINDLE_HL_PICKLE, "wb") as f:
		pickle.dump(highlights, f)
	log(f"Kindle highlights: {len(highlights)}")
	return highlights
