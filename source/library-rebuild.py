from config import log, USE_KINDLE, USE_IBOOKS, USE_YOMU, USE_CALIBRE, KINDLE_APP, KINDLE_PATH, XML_CACHE, IBOOKS_PATH, YOMU_DATA_DB, CALIBRE_METADATA_DB
from kindle_fun import  get_kindle, get_ibooks, getDownloadedASINs, get_kindleClassic, get_yomu, get_calibre
import json
from time import time


def main():
    main_start_time = time()
    log ("rebuilding database ⏳...")
    
    
    if USE_KINDLE:
        if KINDLE_APP == "classic":

            myContentBooks = getDownloadedASINs(KINDLE_PATH) # output is a list of downloaded book ASINs
            #log(myContentBooks)
            get_kindleClassic(XML_CACHE, myContentBooks)
            log ("rebuilding Kindle Classic database ...")
            

        elif KINDLE_APP == "new":
            get_kindle(KINDLE_PATH)
            log ("rebuilding Kindle database ...")
            


    if USE_IBOOKS:
        get_ibooks(IBOOKS_PATH)
        log ("rebuilding iBooks database ...")

    if USE_YOMU:
        get_yomu(YOMU_DATA_DB)
        log("rebuilding Yomu database ...")

    if USE_CALIBRE:
        get_calibre(CALIBRE_METADATA_DB)
        log("rebuilding Calibre database ...")

    main_timeElapsed = time() - main_start_time

    log(f"done 👍\nscript duration: {round(main_timeElapsed, 3)} seconds")

    result = {
        "items": [
            {
                "title": "Done!",
                "subtitle": "ready to search now",
                "arg": "",
                "icon": {
                    "path": "icons/done.png"
                }
            }
        ]
    }
    print(json.dumps(result))


if __name__ == '__main__':
	main ()





	


