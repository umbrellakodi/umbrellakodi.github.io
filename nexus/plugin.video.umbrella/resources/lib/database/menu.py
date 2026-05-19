# -*- coding: utf-8 -*-
"""
	Umbrella Add-on
"""

import sqlite3 as db
from resources.lib.modules import control

menuFile = control.joinPath(control.dataPath, 'menu.db')

_ROOT_DEFAULTS = [
	# (item_id, label, action, icon, poster, is_folder, is_action, enabled, sort_order, is_custom)
	('searchMovies',    '33042', 'movieSearch',                            'searchmovies.png', 'searchmovies.png', 1, 1, 1, 0,  0),
	('searchTVShows',   '33043', 'tvSearch',                               'searchtv.png',     'searchtv.png',     1, 1, 1, 1,  0),
	('movies',          '33046', 'movieNavigator',                         'movies.png',       'movies.png',       1, 1, 1, 2,  0),
	('tvshows',         '33047', 'tvNavigator',                            'tvshows.png',      'tvshows.png',      1, 1, 1, 3,  0),
	('anime',           'Anime', 'anime_Navigator',                        'boxsets.png',      'boxsets.png',      1, 1, 1, 4,  0),
	('myMovies',        '32003', 'mymovieNavigator',                       'mymovies.png',     'mymovies.png',     1, 1, 1, 5,  0),
	('myTVShows',       '32004', 'mytvNavigator',                          'mytvshows.png',    'mytvshows.png',    1, 1, 1, 6,  0),
	('youtube',         'YouTube Videos', 'youtube',                       'youtube.png',      'youtube.png',      1, 1, 1, 7,  0),
	('search',          '32010', 'tools_searchNavigator',                  'search.png',       'search.png',       1, 1, 1, 8,  0),
	('tools',           '32008', 'tools_toolNavigator',                    'tools.png',        'tools.png',        1, 1, 1, 9,  0),
	('downloads',       '32009', 'downloadNavigator',                      'downloads.png',    'downloads.png',    1, 1, 1, 10, 0),
	('favourites',      '40464', 'favouriteNavigator',                     'highly-rated.png', 'highly-rated.png', 1, 1, 1, 11, 0),
	('premiumServices', 'Premium Services', 'premiumNavigator',            'premium.png',      'premium.png',      1, 1, 1, 12, 0),
	('changelog',       '32014', 'tools_ShowChangelog&name=Umbrella',      'changelog.png',    'changelog.png',    0, 1, 0, 13, 0),
	('fullChangelog',   '40589', 'tools_ShowFullChangelog&name=Umbrella',  'changelog.png',    'changelog.png',    0, 1, 0, 14, 0),
]

MENU_DEFAULTS = {
	'root': _ROOT_DEFAULTS,
	# 'movies': _MOVIES_DEFAULTS,   # future
	# 'tvshows': _TVSHOWS_DEFAULTS, # future
}


def _get_connection():
	if not control.existsPath(control.dataPath):
		control.makeFile(control.dataPath)
	dbcon = db.connect(menuFile, timeout=60)
	dbcon.execute('PRAGMA journal_mode = WAL')
	dbcon.execute('PRAGMA synchronous = NORMAL')
	dbcon.execute('PRAGMA temp_store = memory')
	dbcon.row_factory = lambda c, r: {col[0]: r[i] for i, col in enumerate(c.description)}
	return dbcon


def _populate_defaults(dbcon, menu_name):
	defaults = MENU_DEFAULTS.get(menu_name, [])
	dbcon.executemany(
		'INSERT OR IGNORE INTO menu_items '
		'(menu_name, item_id, label, action, icon, poster, is_folder, is_action, enabled, sort_order, is_custom) '
		'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
		[(menu_name,) + row for row in defaults]
	)
	dbcon.commit()


def initialize(menu_name='root'):
	dbcon = _get_connection()
	dbcon.execute('''CREATE TABLE IF NOT EXISTS menu_items (
		id          INTEGER PRIMARY KEY AUTOINCREMENT,
		menu_name   TEXT NOT NULL,
		item_id     TEXT NOT NULL,
		label       TEXT NOT NULL,
		action      TEXT NOT NULL,
		icon        TEXT NOT NULL,
		poster      TEXT NOT NULL,
		is_folder   INTEGER NOT NULL DEFAULT 1,
		is_action   INTEGER NOT NULL DEFAULT 1,
		enabled     INTEGER NOT NULL DEFAULT 1,
		sort_order  INTEGER NOT NULL,
		is_custom   INTEGER NOT NULL DEFAULT 0,
		UNIQUE(menu_name, item_id)
	)''')
	dbcon.commit()
	cur = dbcon.cursor()
	cur.execute('SELECT COUNT(*) as cnt FROM menu_items WHERE menu_name=?', (menu_name,))
	if cur.fetchone()['cnt'] == 0:
		_populate_defaults(dbcon, menu_name)
	dbcon.close()


def get_menu_items(menu_name='root'):
	dbcon = _get_connection()
	cur = dbcon.cursor()
	cur.execute('SELECT * FROM menu_items WHERE menu_name=? AND enabled=1 ORDER BY sort_order', (menu_name,))
	items = cur.fetchall()
	dbcon.close()
	return items


def get_all_menu_items(menu_name='root'):
	dbcon = _get_connection()
	cur = dbcon.cursor()
	cur.execute('SELECT * FROM menu_items WHERE menu_name=? ORDER BY sort_order', (menu_name,))
	items = cur.fetchall()
	dbcon.close()
	return items


def toggle_item(menu_name, item_id):
	dbcon = _get_connection()
	dbcon.execute(
		'UPDATE menu_items SET enabled = CASE WHEN enabled=1 THEN 0 ELSE 1 END WHERE menu_name=? AND item_id=?',
		(menu_name, item_id)
	)
	dbcon.commit()
	dbcon.close()


def move_item_up(menu_name, item_id):
	dbcon = _get_connection()
	cur = dbcon.cursor()
	cur.execute('SELECT id, item_id, sort_order FROM menu_items WHERE menu_name=? ORDER BY sort_order', (menu_name,))
	rows = cur.fetchall()
	for i, row in enumerate(rows):
		if row['item_id'] == item_id and i > 0:
			prev = rows[i - 1]
			dbcon.execute('UPDATE menu_items SET sort_order=? WHERE id=?', (prev['sort_order'], row['id']))
			dbcon.execute('UPDATE menu_items SET sort_order=? WHERE id=?', (row['sort_order'], prev['id']))
			dbcon.commit()
			break
	dbcon.close()


def move_item_down(menu_name, item_id):
	dbcon = _get_connection()
	cur = dbcon.cursor()
	cur.execute('SELECT id, item_id, sort_order FROM menu_items WHERE menu_name=? ORDER BY sort_order', (menu_name,))
	rows = cur.fetchall()
	for i, row in enumerate(rows):
		if row['item_id'] == item_id and i < len(rows) - 1:
			nxt = rows[i + 1]
			dbcon.execute('UPDATE menu_items SET sort_order=? WHERE id=?', (nxt['sort_order'], row['id']))
			dbcon.execute('UPDATE menu_items SET sort_order=? WHERE id=?', (row['sort_order'], nxt['id']))
			dbcon.commit()
			break
	dbcon.close()


def reorder_enabled_items(menu_name, new_item_id_order):
	dbcon = _get_connection()
	cur = dbcon.cursor()
	cur.execute(
		'SELECT id, item_id, sort_order FROM menu_items WHERE menu_name=? AND enabled=1 ORDER BY sort_order',
		(menu_name,)
	)
	enabled_rows = cur.fetchall()
	old_sort_orders = [r['sort_order'] for r in enabled_rows]
	new_order_map = {item_id: old_sort_orders[i] for i, item_id in enumerate(new_item_id_order)}
	for row in enabled_rows:
		dbcon.execute('UPDATE menu_items SET sort_order=? WHERE id=?', (new_order_map[row['item_id']], row['id']))
	dbcon.commit()
	dbcon.close()


def move_item_to(menu_name, item_id, target_index):
	dbcon = _get_connection()
	cur = dbcon.cursor()
	cur.execute('SELECT id, item_id FROM menu_items WHERE menu_name=? ORDER BY sort_order', (menu_name,))
	rows = cur.fetchall()
	ids = [r['id'] for r in rows]
	moved_id = next((r['id'] for r in rows if r['item_id'] == item_id), None)
	if moved_id is None:
		dbcon.close()
		return
	ids.remove(moved_id)
	ids.insert(target_index, moved_id)
	for i, row_id in enumerate(ids):
		dbcon.execute('UPDATE menu_items SET sort_order=? WHERE id=?', (i, row_id))
	dbcon.commit()
	dbcon.close()


def delete_item(menu_name, item_id):
	dbcon = _get_connection()
	dbcon.execute('DELETE FROM menu_items WHERE menu_name=? AND item_id=? AND is_custom=1', (menu_name, item_id))
	dbcon.commit()
	dbcon.close()


def add_custom_item(menu_name, label, action, icon, poster, is_folder=1, is_action=1):
	dbcon = _get_connection()
	cur = dbcon.cursor()
	cur.execute('SELECT MAX(sort_order) as mx FROM menu_items WHERE menu_name=?', (menu_name,))
	row = cur.fetchone()
	next_order = (row['mx'] or 0) + 1
	# Generate a unique item_id from label
	import re
	base_id = 'custom_' + re.sub(r'[^a-z0-9]', '_', label.lower())[:30]
	item_id = base_id
	suffix = 1
	while True:
		cur.execute('SELECT id FROM menu_items WHERE menu_name=? AND item_id=?', (menu_name, item_id))
		if not cur.fetchone():
			break
		item_id = '%s_%d' % (base_id, suffix)
		suffix += 1
	dbcon.execute(
		'INSERT INTO menu_items (menu_name, item_id, label, action, icon, poster, is_folder, is_action, enabled, sort_order, is_custom) '
		'VALUES (?,?,?,?,?,?,?,?,1,?,1)',
		(menu_name, item_id, label, action, icon, poster, is_folder, is_action, next_order)
	)
	dbcon.commit()
	dbcon.close()


def reset_to_defaults(menu_name='root'):
	dbcon = _get_connection()
	dbcon.execute('DELETE FROM menu_items WHERE menu_name=?', (menu_name,))
	dbcon.commit()
	_populate_defaults(dbcon, menu_name)
	dbcon.close()
