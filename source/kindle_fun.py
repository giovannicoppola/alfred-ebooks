## support functions for the alfred-eBook workflow

from datetime import datetime, date
from config import (
	log,
	Book,
	KINDLE_PICKLE,
	IBOOKS_PICKLE,
	YOMU_PICKLE,
	CALIBRE_PICKLE,
	KINDLE_PATH,
	CACHE_FOLDER_IMAGES_KINDLE,
	CACHE_FOLDER_IMAGES_IBOOKS,
	CACHE_FOLDER_IMAGES_CALIBRE,
	MY_URL_STRING,
	YOMU_EPUB_CACHE_DIR,
	CALIBRE_LIBRARY_PATH,
)
import os
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
			book_desc=tags,
			read_pct=0.0,
			source="Yomu",
			loaned=0,
			downloaded=1,
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

	

def get_ibooks(myDatabase):
	books = []
	conn = sqlite3.connect(myDatabase)
	conn.row_factory = sqlite3.Row
	c = conn.cursor()
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
			
		
		book = Book(
			title=row['ZTITLE'],
			bookID="",
			
			path=row['ZPATH'],
			icon_path=ICON_PATH,
			author=row['ZAUTHOR'],
			book_desc=row['ZBOOKDESCRIPTION'],
			read_pct=row['ZREADINGPROGRESS'],
			source="iBooks",
			loaned=0,
			downloaded=downloaded
			
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



   

             
