# -*- coding: utf-8 -*-
"""A resume point is stale once the same movie or episode is marked watched after it.

Watched records come from every service's local sync database, not only the service that
holds the resume point: services mark watched on their own thresholds (MDBList at 80%,
the main service at the user's threshold), so the finish often reaches only some of them,
while the stale pause stays on another and keeps showing in Finish Watching.
"""
import calendar
import re
import sqlite3
import time

# Watched dates are often rounded to the minute, so a pause written at the same stop as the
# watched record can appear up to a minute later than it.
TOLERANCE_SECONDS = 60
_CACHE_SECONDS = 60
_cache = {'at': 0, 'paths': None, 'data': None}
_TS = re.compile(r'(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?\s*(Z|[+-]\d{2}:?\d{2})?$')


def parse_time(value):
	"""Seconds since the epoch for an ISO date or a numeric timestamp; None if unknown.
	(datetime.strptime is unreliable in threads on some Android builds.)"""
	if value in (None, '', 'None'): return None
	if isinstance(value, (int, float)): return float(value) if value > 0 else None
	text = str(value).strip()
	try:
		number = float(text)
		return number if number > 0 else None
	except ValueError: pass
	match = _TS.match(text)
	if not match: return None
	year, month, day, hour, minute, second, zone = match.groups()
	seconds = calendar.timegm((int(year), int(month), int(day), int(hour), int(minute), int(second or 0), 0, 0, 0))
	if zone and zone != 'Z':
		sign = -1 if zone[0] == '-' else 1
		zone = zone[1:].replace(':', '')
		seconds -= sign * (int(zone[:2]) * 3600 + int(zone[2:]) * 60)
	return float(seconds)


def _sync_paths():
	from resources.lib.modules import control
	return [getattr(control, name) for name in ('customTraktSyncFile', 'mdbSyncFile', 'floppySyncFile', 'punchplaySyncFile',
			'scrobSyncFile', 'simKLSyncFile', 'traktSyncFile') if getattr(control, name, None)]


def _keep_latest(table, key, stamp):
	if stamp is not None and stamp > table.get(key, 0): table[key] = stamp


def _load(paths):
	movies, episodes = {}, {}
	for path in paths:
		try: dbcon = sqlite3.connect('file:%s?mode=ro' % path, uri=True, timeout=5)
		except Exception: continue
		try:
			tables = {row[0] for row in dbcon.execute("SELECT name FROM sqlite_master WHERE type='table'")}
			for table in tables:
				try:
					if table.endswith('_watched_episodes'):
						for imdb, tmdb, tvdb, season, episode, watched in dbcon.execute(
								'SELECT show_imdb, show_tmdb, show_tvdb, season, episode, last_watched_at FROM %s' % table):
							stamp = parse_time(watched)
							for kind, ident in (('imdb', imdb), ('tmdb', tmdb), ('tvdb', tvdb)):
								if ident: _keep_latest(episodes, (kind, str(ident), int(season), int(episode)), stamp)
					elif table.endswith('_watched_movies') or table == 'movies_history':
						for imdb, tmdb, watched in dbcon.execute('SELECT imdb, tmdb, last_watched_at FROM %s' % table):
							stamp = parse_time(watched)
							for kind, ident in (('imdb', imdb), ('tmdb', tmdb)):
								if ident: _keep_latest(movies, (kind, str(ident)), stamp)
				except Exception: pass
			if 'watched' in tables:
				# Trakt keeps per-movie watched dates in its request cache (episodes only per show).
				try:
					import ast
					for (value,) in dbcon.execute("SELECT value FROM watched WHERE key LIKE '_fetch_watched_movies_dates%'"):
						for imdb, watched in (ast.literal_eval(value) or {}).items():
							_keep_latest(movies, ('imdb', str(imdb)), parse_time(watched))
				except Exception: pass
		finally: dbcon.close()
	return movies, episodes


def _watched(paths=None):
	now = time.time()
	paths = paths if paths is not None else _sync_paths()
	if _cache['data'] is None or _cache['paths'] != paths or now - _cache['at'] > _CACHE_SECONDS:
		_cache.update(at=now, paths=paths, data=_load(paths))
	return _cache['data']


def _episode_number(value):
	try: return int(value)
	except (TypeError, ValueError): return None


def watched_at(imdb='', tmdb='', tvdb='', season=None, episode=None, paths=None):
	"""Latest watched time (epoch seconds) of this movie or episode across all services."""
	movies, episodes = _watched(paths)
	season, episode = _episode_number(season), _episode_number(episode)
	stamps = []
	if episode is not None and season is not None:
		for kind, ident in (('imdb', imdb), ('tmdb', tmdb), ('tvdb', tvdb)):
			if ident: stamps.append(episodes.get((kind, str(ident), season, episode)))
	elif episode is None:
		for kind, ident in (('imdb', imdb), ('tmdb', tmdb)):
			if ident: stamps.append(movies.get((kind, str(ident))))
	stamps = [s for s in stamps if s]
	return max(stamps) if stamps else None


def superseded(paused_at, imdb='', tmdb='', tvdb='', season=None, episode=None, paths=None):
	"""True when the item was marked watched after this resume point was saved."""
	try:
		paused = parse_time(paused_at)
		if paused is None: return False
		watched = watched_at(imdb, tmdb, tvdb, season, episode, paths)
		return watched is not None and watched >= paused - TOLERANCE_SECONDS
	except Exception: return False


def drop_superseded(items, paths=None):
	"""Finish Watching rows minus those watched after their pause."""
	try:
		return [i for i in items or [] if not (isinstance(i, dict) and superseded(i.get('paused_at'), i.get('imdb', ''),
			i.get('tmdb', ''), i.get('tvdb', ''), i.get('season') if i.get('episode') not in (None, '', 0, '0') else None,
			i.get('episode') if i.get('episode') not in (None, '', 0, '0') else None, paths))]
	except Exception: return items


def bookmark_superseded(db_path, imdb='', tmdb='', tvdb='', season=None, episode=None, paths=None):
	"""Whether the newest resume point stored in db_path for this item predates a watched record."""
	try:
		ids = [(col, str(val)) for col, val in (('imdb', imdb), ('tmdb', tmdb), ('tvdb', tvdb)) if val not in (None, '', 'None', '0', 0)]
		if not ids: return False
		where = ' OR '.join('%s=?' % col for col, _ in ids)
		args = [val for _, val in ids]
		if episode not in (None, '', 'None'):
			sql = "SELECT paused_at FROM bookmarks WHERE (%s) AND season=? AND episode=? AND NOT tvshowtitle=''" % where
			args += [str(season), str(episode)]
		else:
			sql = "SELECT paused_at FROM bookmarks WHERE (%s) AND tvshowtitle=''" % where
		dbcon = sqlite3.connect('file:%s?mode=ro' % db_path, uri=True, timeout=5)
		try: rows = dbcon.execute(sql, args).fetchall()
		finally: dbcon.close()
		stamps = [parse_time(r[0]) for r in rows]
		stamps = [s for s in stamps if s]
		if not stamps: return False
		latest = max(stamps)
		return superseded(latest, imdb, tmdb, tvdb, season if episode not in (None, '', 'None') else None,
			episode if episode not in (None, '', 'None') else None, paths)
	except Exception: return False
