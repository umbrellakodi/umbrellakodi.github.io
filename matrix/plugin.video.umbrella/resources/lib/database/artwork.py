#Added 2/11/25 by Umbrella_Dev for custom artwork
from resources.lib.modules.control import existsPath, dataPath, makeFile, artworkFile
from resources.lib.modules import log_utils
from sqlite3 import dbapi2 as db


def fetch_movie(imdb):
	list = ''
	try:
		dbcon = get_connection()
		dbcur = get_connection_cursor(dbcon)
		ck_table = dbcur.execute('''SELECT * FROM sqlite_master WHERE type='table' AND name=?;''', ('movies',)).fetchone()
		if not ck_table:
			dbcur.execute('''CREATE TABLE IF NOT EXISTS %s (imdb TEXT, poster TEXT, fanart TEXT, landscape TEXT, banner TEXT, clearart TEXT, clearlogo TEXT, discart TEXT, keyart TEXT, UNIQUE(imdb));''' % 'movies')
			dbcur.connection.commit()
			return list
		try:
			match = dbcur.execute('''SELECT * FROM movies WHERE imdb=?''' , (imdb,)).fetchall()
			list = [{'imdb': i[0], 'poster': i[1], 'fanart': i[2], 'landscape': i[3], 'banner': i[4], 'clearart': i[5], 'clearlogo': i[6], 'discart': i[7], 'keyart': i[8]} for i in match]
		except: pass
	except:
		
		log_utils.error()
	finally:
		dbcur.close() ; dbcon.close()
	return list

def get_connection(setRowFactory=False):
	if not existsPath(dataPath): makeFile(dataPath)
	dbcon = db.connect(artworkFile, timeout=60)
	dbcon.execute('''PRAGMA page_size = 32768''')
	dbcon.execute('''PRAGMA journal_mode = OFF''')
	dbcon.execute('''PRAGMA synchronous = OFF''')
	dbcon.execute('''PRAGMA temp_store = memory''')
	dbcon.execute('''PRAGMA mmap_size = 30000000000''')
	if setRowFactory: dbcon.row_factory = _dict_factory
	return dbcon

def get_connection_cursor(dbcon):
	dbcur = dbcon.cursor()
	return dbcur

def _dict_factory(cursor, row):
	d = {}
	for idx, col in enumerate(cursor.description): d[col[0]] = row[idx]
	return d