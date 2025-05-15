# -*- coding: utf-8 -*-
# By Umbrella for Umbrella (04/15/25)
"""
	Umbrella Add-on
"""
from resources.lib.modules.control import existsPath, dataPath, makeFile, scrobbleSyncFile, setting as getSetting
from sqlite3 import dbapi2 as db

def fetch_bookmarks(imdb, tmdb='', tvdb='', season=None, episode=None, ret_all=None, ret_type='movies'):
	progress = '0'
	try:
		dbcon = get_connection()
		dbcur = get_connection_cursor(dbcon)
		ck_table = dbcur.execute('''SELECT * FROM sqlite_master WHERE type='table' AND name='bookmarks';''').fetchone()
		if not ck_table:
			dbcur.execute('''CREATE TABLE IF NOT EXISTS bookmarks (tvshowtitle TEXT, title TEXT, resume_id TEXT, imdb TEXT, tmdb TEXT, tvdb TEXT, season TEXT, episode TEXT, genre TEXT, mpaa TEXT, 
									studio TEXT, duration TEXT, percent_played TEXT, paused_at TEXT, UNIQUE(resume_id, imdb, tmdb, tvdb, season, episode));''')
			dbcur.connection.commit()
			return progress
		if ret_all:
			if ret_type == 'movies':
				match = dbcur.execute('''SELECT * FROM bookmarks WHERE (tvshowtitle='')''').fetchall()
				progress = [{'title': i[1], 'resume_id': i[2], 'imdb': i[3], 'tmdb': i[4], 'duration': int(i[11]), 'progress': i[12], 'paused_at': i[13]} for i in match]
			else:
				match = dbcur.execute('''SELECT * FROM bookmarks WHERE NOT (tvshowtitle='')''').fetchall()
				progress = [{'tvshowtitle': i[0], 'title': i[1], 'resume_id': i[2], 'imdb': i[3], 'tmdb': i[4], 'tvdb': i[5], 'season': int(i[6]), 'episode': int(i[7]), 'genre': i[8], 'mpaa': i[9],
									'studio': i[10], 'duration': int(i[11]), 'progress': i[12], 'paused_at': i[13]} for i in match]
		else:
			if not episode:
				try: # Lookup both IMDb and TMDb first for more accurate movie match.
					match = dbcur.execute('''SELECT * FROM bookmarks WHERE (imdb=? AND tmdb=? AND NOT imdb='' AND NOT tmdb='')''', (imdb, tmdb)).fetchone()
					if ret_type == 'resume_info': progress = (match[1], match[2])
					else: progress = match[12]
				except:
					try:
						match = dbcur.execute('''SELECT * FROM bookmarks WHERE (imdb=? AND NOT imdb='')''', (imdb,)).fetchone()
						if ret_type == 'resume_info': progress = (match[1], match[2])
						else: progress = match[12]
					except: pass
			else:
				try: # Lookup both IMDb and TVDb first for more accurate episode match.
					match = dbcur.execute('''SELECT * FROM bookmarks WHERE (imdb=? AND tvdb=? AND season=? AND episode=? AND NOT imdb='' AND NOT tvdb='')''', (imdb, tvdb, season, episode)).fetchone()
					if ret_type == 'resume_info': 
						progress = (match[0], match[2])
						log_utils.log('Getting resume from database imdb. Match: %s' % (str(match)),1)
					else: progress = match[12]
				except:
					try:
						match = dbcur.execute('''SELECT * FROM bookmarks WHERE (tvdb=? AND season=? AND episode=? AND NOT tvdb='')''', (tvdb, season, episode)).fetchone()
						if ret_type == 'resume_info': 
							progress = (match[0], match[2])
							log_utils.log('Getting resume from database tvdb. Match: %s' % (str(match)),1)
						else: progress = match[12]
					except: pass
	except:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		dbcur.close() ; dbcon.close()
	return progress

def delete_bookmark(items):
	try:
		dbcon = get_connection()
		dbcur = get_connection_cursor(dbcon)
		ck_table = dbcur.execute('''SELECT * FROM sqlite_master WHERE type='table' AND name='bookmarks';''').fetchone()
		if not ck_table:
			dbcur.execute('''CREATE TABLE IF NOT EXISTS bookmarks (tvshowtitle TEXT, title TEXT, resume_id TEXT, imdb TEXT, tmdb TEXT, tvdb TEXT, season TEXT, episode TEXT, genre TEXT, mpaa TEXT, 
									studio TEXT, duration TEXT, percent_played TEXT, paused_at TEXT, UNIQUE(resume_id, imdb, tmdb, tvdb, season, episode));''')
			dbcur.execute('''CREATE TABLE IF NOT EXISTS service (setting TEXT, value TEXT, UNIQUE(setting));''')
			dbcur.connection.commit()
			return
		for i in items:
			if i.get('type') == 'episode':
				ids = i.get('show').get('ids')
				imdb, tvdb, season, episode, = str(ids.get('imdb', '')), str(ids.get('tvdb', '')), str(i.get('episode').get('season')), str(i.get('episode').get('number'))
			else:
				tvdb, season, episode = '', '', ''
				ids = i.get('movie').get('ids')
				imdb = str(ids.get('imdb', ''))
			try:
				dbcur.execute('''DELETE FROM bookmarks WHERE (imdb=? AND tvdb=? AND season=? AND episode=?)''', (imdb, tvdb, season, episode))
				dbcur.execute('''INSERT OR REPLACE INTO service Values (?, ?)''', ('last_paused_at', i.get('paused_at', '')))
				dbcur.connection.commit()
			except: pass
	except:
		from resources.lib.modules import log_utils
		log_utils.error()
	finally:
		dbcur.close() ; dbcon.close()

def get_connection(setRowFactory=False):
	if not existsPath(dataPath): makeFile(dataPath)
	dbcon = db.connect(scrobbleSyncFile, timeout=60) # added timeout 3/23/21 for concurrency with threads
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