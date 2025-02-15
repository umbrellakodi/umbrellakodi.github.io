#Added 2/11/25 by Umbrella_Dev for custom artwork
from resources.lib.modules import control
from resources.lib.modules.control import existsPath, dataPath, makeFile, artworkFile
from resources.lib.modules import log_utils
from sqlite3 import dbapi2 as db
from json import loads as jsloads, dumps as jsdumps

def fetch_movie(imdb, tmdb):
	list = ''
	try:
		dbcon = get_connection()
		dbcur = get_connection_cursor(dbcon)
		ck_table = dbcur.execute('''SELECT * FROM sqlite_master WHERE type='table' AND name=?;''', ('movies',)).fetchone()
		if not ck_table:
			dbcur.execute('''CREATE TABLE IF NOT EXISTS %s (imdb TEXT, tmdb TEXT, poster TEXT, fanart TEXT, landscape TEXT, banner TEXT, clearart TEXT, clearlogo TEXT, discart TEXT, keyart TEXT, UNIQUE(imdb));''' % 'movies')
			dbcur.connection.commit()
			return list
		try:
			match = dbcur.execute('''SELECT * FROM movies WHERE imdb=?''' , (imdb,)).fetchall()
			list = [{'imdb': i[0], 'tmdb': i[1], 'poster': i[2], 'fanart': i[3], 'landscape': i[4], 'banner': i[5], 'clearart': i[6], 'clearlogo': i[7], 'discart': i[8], 'keyart': i[9]} for i in match]
		except: pass
	except:
		
		log_utils.error()
	finally:
		dbcur.close() ; dbcon.close()
	return list

def show_artwork_options_with_current(**kwargs):
	mediatype = kwargs.get('mediatype', '')
	#variables needed
	refesh = True
	heading = control.infoLabel('Container.ListItem.Title')
	artworkType = kwargs.get('artworktype', '')
	imdb = kwargs.get('imdb','')
	tmdb = kwargs.get('tmdb', '')
	tvdb = kwargs.get('tvdb','')
	season = kwargs.get('season','')
	episode = kwargs.get('episode','')
	poster = kwargs.get('poster')
	fanart = kwargs.get('fanart')
	landscape = kwargs.get('landscape')
	banner = kwargs.get('banner')
	clearart = kwargs.get('clearart')
	clearlogo = kwargs.get('clearlogo')
	discart = kwargs.get('discart')
	keyart = kwargs.get('keyart')
	

	try:
		control.busy()
		items = [{"poster": poster}, {"fanart": fanart}, {"landscape": landscape}, {"banner": banner}, {"clearart": clearart}, {"clearlogo": clearlogo}, {"discart": discart}, {"keyart": keyart }, {"reset all": "reset_all"}]
		control.hide()
		from resources.lib.windows.artselection import ArtTypeSelect
		itemsDumped = jsdumps(items)
		window = ArtTypeSelect('artwork.xml', control.addonPath(control.addonId()), artworkType=artworkType, mediatype=mediatype, heading=heading, items=itemsDumped)
		selected_items = window.run()
		del window
		if selected_items or selected_items == 0:
			selectedItem = items[selected_items]
			for each in selectedItem.keys():
				artworktype = each
			if artworktype == 'reset all':
				delete_artwork(imdb=imdb, tmdb=tmdb)
			elif mediatype == 'movie':
				heading = artworktype + ' artwork for: %s' % control.infoLabel('Container.ListItem.Title')
				log_utils.log('Umbrella Customize Art "%s" Selected.' % (artworktype), 1)
				show_artwork_window(imdb=imdb, tmdb=tmdb, mediatype=mediatype, heading=heading, artworktype=artworktype)
		control.hide()
	except:
		log_utils.error()
		control.hide()

def show_artwork_standard_select(**kwargs):
	lists = []
	imdb = kwargs.get('imdb','')
	tmdb = kwargs.get('tmdb', '')
	tvdb = kwargs.get('tvdb','')
	season = kwargs.get('season','')
	episode = kwargs.get('episode','')
	mediatype = kwargs.get('mediatype', '')
	try:
		if season: season = int(season)
		if episode: episode = int(episode)
		media_type = 'Show' if tvdb else 'Movie'
		items = [('poster', 'poster')]
		items += [('fanart', 'fanart')]
		items += [('landscape', 'landscape')]
		items += [('banner', 'banner')]
		items += [('clearart', 'clearart')]
		items += [('clearlogo', 'clearlogo')]
		items += [('discart', 'discart')]
		items += [('keyart', 'keyart')]

		control.hide()
		select = control.selectDialog([i[0] for i in items], heading=control.addonInfo('name') + ' - ' + 'Customize Artwork')
		refresh = True
		if select == -1: return
		if select >= 0:
			if items[select][1] == 'poster':
				heading = str(items[select][1] ) + ' artwork for: %s' % control.infoLabel('Container.ListItem.Title')
				log_utils.log('Umbrella Customize Art "%s" Selected. Current %s is: %s' % (items[select][1], items[select][1], control.infoLabel('Container.ListItem.Art(poster)')), 1)
				show_artwork_window(imdb=imdb, tmdb=tmdb, mediatype=mediatype, heading=heading, artworktype=str(items[select][1] ))
			if items[select][1] == 'fanart':
				heading = str(items[select][1] ) + ' artwork for: %s' % control.infoLabel('Container.ListItem.Title')
				log_utils.log('Umbrella Customize Art "%s" Selected. Current %s is: %s' % (items[select][1], items[select][1], control.infoLabel('Container.ListItem.Art(fanart)')), 1)
				show_artwork_window(imdb=imdb, tmdb=tmdb, mediatype=mediatype, heading=heading, artworktype=str(items[select][1] ))
			if items[select][1] == 'landscape':
				heading = str(items[select][1] ) + ' artwork for: %s' % control.infoLabel('Container.ListItem.Title')
				log_utils.log('Umbrella Customize Art "%s" Selected. Current %s is: %s' % (items[select][1], items[select][1], control.infoLabel('Container.ListItem.Art(landscape)')), 1)
				show_artwork_window(imdb=imdb, tmdb=tmdb, mediatype=mediatype, heading=heading, artworktype=str(items[select][1] ))
			if items[select][1] == 'banner':
				heading = str(items[select][1] ) + ' artwork for: %s' % control.infoLabel('Container.ListItem.Title')
				log_utils.log('Umbrella Customize Art "%s" Selected. Current %s is: %s' % (items[select][1], items[select][1], control.infoLabel('Container.ListItem.Art(banner)')), 1)
				show_artwork_window(imdb=imdb, tmdb=tmdb, mediatype=mediatype, heading=heading, artworktype=str(items[select][1] ))
			if items[select][1] == 'clearart':
				heading = str(items[select][1] ) + ' artwork for: %s' % control.infoLabel('Container.ListItem.Title')
				log_utils.log('Umbrella Customize Art "%s" Selected. Current %s is: %s' % (items[select][1], items[select][1], control.infoLabel('Container.ListItem.Art(clearart)')), 1)
				show_artwork_window(imdb=imdb, tmdb=tmdb, mediatype=mediatype, heading=heading, artworktype=str(items[select][1] ))
			if items[select][1] == 'clearlogo':
				heading = str(items[select][1] ) + ' artwork for: %s' % control.infoLabel('Container.ListItem.Title')
				log_utils.log('Umbrella Customize Art "%s" Selected. Current %s is: %s' % (items[select][1], items[select][1], control.infoLabel('Container.ListItem.Art(clearlogo)')), 1)
				show_artwork_window(imdb=imdb, tmdb=tmdb, mediatype=mediatype, heading=heading, artworktype=str(items[select][1] ))
			if items[select][1] == 'discart':
				heading = str(items[select][1] ) + ' artwork for: %s' % control.infoLabel('Container.ListItem.Title')
				log_utils.log('Umbrella Customize Art "%s" Selected. Current %s is: %s' % (items[select][1], items[select][1], control.infoLabel('Container.ListItem.Art(discart)')), 1)
				show_artwork_window(imdb=imdb, tmdb=tmdb, mediatype=mediatype, heading=heading, artworktype=str(items[select][1] ))
			if items[select][1] == 'keyart':
				heading = str(items[select][1] ) + ' artwork for: %s' % control.infoLabel('Container.ListItem.Title')
				log_utils.log('Umbrella Customize Art "%s" Selected. Current %s is: %s' % (items[select][1], items[select][1], control.infoLabel('Container.ListItem.Art(keyart)')), 1)
				show_artwork_window(imdb=imdb, tmdb=tmdb, mediatype=mediatype, heading=heading, artworktype=str(items[select][1] ))
			control.hide()
	except:
		log_utils.error()
		control.hide()

def show_artwork_window(**kwargs):
	mediatype = kwargs.get('mediatype', '')
	heading = kwargs.get('heading', 'Umbrella Art')
	artworkType = kwargs.get('artworktype', '')
	imdb = kwargs.get('imdb','')
	tmdb = kwargs.get('tmdb', '')
	tvdb = kwargs.get('tvdb','')
	season = kwargs.get('season','')
	episode = kwargs.get('episode','')
	refresh = True
	try:
		control.busy()
		items = get_artwork(imdb=imdb, tmdb=tmdb, tvdb=tvdb, season=season, episode=episode, mediatype=mediatype, artworkType=artworkType)
		if not items: return control.notification('Art Missing', 'No %s artwork found.' % artworkType)
		resetItem = {'artworkType': items[0]['artworkType'], 'source': 'Reset to Default', 'url': ''}
		items.append(resetItem)
		control.hide()
		itemsDumped = jsdumps(items)
		from resources.lib.windows.artselection import ArtSelect
		window = ArtSelect('artwork.xml', control.addonPath(control.addonId()), mediatype=mediatype, heading=heading, items=itemsDumped)
		selected_items = window.run()
		del window
		if selected_items or selected_items == 0:
			selectedUrl = items[selected_items].get('url')
			if mediatype == 'movie' and selectedUrl == '': delete_artwork_one_item(artworkType=artworkType, imdb=imdb)
			if mediatype == 'movie':
				add_movie_entry(artworkType=artworkType,mediatype=mediatype, imdb=imdb, tmdb=tmdb, tvdb=tvdb, season=season, episode=episode, url=selectedUrl)
			if control.setting('debug.level') == '1':
				log_utils.log('selected item: %s' % str(items[selected_items]), 1)
		control.hide()
		control.sleep(300)
	except:
		log_utils.error()
		control.hide()

def get_artwork(**kwargs):
	arttype = kwargs.get('mediatype')
	if arttype == 'movie':
		artworkList = []
		from resources.lib.indexers import fanarttv
		fanartList = fanarttv.FanartTv().get_all_movie_art(imdb=kwargs.get('imdb',''), tmdb=kwargs.get('tmdb',''), artworkType=kwargs.get('artworkType'))
		if fanartList and fanartList != '404:NOT FOUND':
			artworkList.extend(fanartList)
		from resources.lib.indexers import tmdb
		tmdbList = tmdb.Movies().get_all_movie_art(imdb=kwargs.get('imdb',''), tmdb=kwargs.get('tmdb',''), artworkType=kwargs.get('artworkType'))
		if tmdbList:
			artworkList.extend(tmdbList)
		if not artworkList:
			return control.notification('No Artwork', 'No %s artwork was found for imdb id: %s' % (kwargs.get('artworkType'), kwargs.get('imdb')))
		return artworkList

	else:
		pass
	return type


def add_movie_entry(**kwargs):
	try:
		dbcon = get_connection()
		dbcur = get_connection_cursor(dbcon)
		ck_table = dbcur.execute('''SELECT * FROM sqlite_master WHERE type='table' AND name=?;''', ('movies',)).fetchone()
		if not ck_table:
			dbcur.execute('''CREATE TABLE IF NOT EXISTS %s (imdb TEXT, tmdb TEXT, poster TEXT, fanart TEXT, landscape TEXT, banner TEXT, clearart TEXT, clearlogo TEXT, discart TEXT, keyart TEXT, UNIQUE(imdb));''' % 'movies')
			dbcur.connection.commit()
		try:
			imdb = kwargs.get('imdb','')
			artworkType =  kwargs.get('artworkType','')
			url = kwargs.get('url','')
			dbcur.execute(f'''INSERT INTO movies (imdb, {artworkType}) Values (?, ?) ON CONFLICT(imdb) DO UPDATE SET {artworkType} = excluded.{artworkType}''', (imdb, url))
		except Exception as e:
			log_utils.log("Exception: %s" % (str(e)), 1)  # Log the problematic item
		dbcur.connection.commit()
	except:
		log_utils.error()
	finally:
		dbcur.close() ; dbcon.close()
		control.refresh()
		control.trigger_widget_refresh()

def delete_artwork(**kwargs):
	try:
		dbcon = get_connection()
		dbcur = get_connection_cursor(dbcon)
		ck_table = dbcur.execute('''SELECT * FROM sqlite_master WHERE type='table' AND name=?;''', ('movies',)).fetchone()
		if not ck_table:
			dbcur.execute('''CREATE TABLE IF NOT EXISTS %s (imdb TEXT, tmdb TEXT, poster TEXT, fanart TEXT, landscape TEXT, banner TEXT, clearart TEXT, clearlogo TEXT, discart TEXT, keyart TEXT, UNIQUE(imdb));''' % 'movies')
			dbcur.connection.commit()
		try:
			imdb = kwargs.get('imdb','')
			dbcur.execute("DELETE FROM movies WHERE imdb = ?;", (imdb,))
		except Exception as e:
			log_utils.log("Exception: %s" % (str(e)), 1)  # Log the problematic item
		dbcur.connection.commit()
	except:
		log_utils.error()
	finally:
		dbcur.close() ; dbcon.close()
		control.refresh()
		control.trigger_widget_refresh()

def delete_artwork_one_item(**kwargs):
	try:
		dbcon = get_connection()
		dbcur = get_connection_cursor(dbcon)
		ck_table = dbcur.execute('''SELECT * FROM sqlite_master WHERE type='table' AND name=?;''', ('movies',)).fetchone()
		if not ck_table:
			dbcur.execute('''CREATE TABLE IF NOT EXISTS %s (imdb TEXT, tmdb TEXT, poster TEXT, fanart TEXT, landscape TEXT, banner TEXT, clearart TEXT, clearlogo TEXT, discart TEXT, keyart TEXT, UNIQUE(imdb));''' % 'movies')
			dbcur.connection.commit()
		try:
			imdb = kwargs.get('imdb','')
			artworkType = kwargs.get('artwork_type')
			dbcur.execute(f"UPDATE movies SET {artworkType} = NULL WHERE imdb = ?;", (imdb,))
		except Exception as e:
			log_utils.log("Exception: %s" % (str(e)), 1)  # Log the problematic item
		dbcur.connection.commit()
	except:
		log_utils.error()
	finally:
		dbcur.close() ; dbcon.close()
		control.refresh()
		control.trigger_widget_refresh()

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