# -*- coding: utf-8 -*-
"""
	Umbrella Add-on
"""
# Yamtrack (self-hosted media tracker). Built against the dannyvfilms/Yamtrack
# fork's /api/v1/ 
# Auth is a single static bearer token pasted from the
# Yamtrack web UI (Integrations settings) — there is no device-code flow uses API

from datetime import datetime
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urljoin
from json import dumps as jsdumps
from resources.lib.database import yamtracksync
from resources.lib.modules import control
from resources.lib.modules import log_utils

getLS = control.lang
getSetting = control.setting
setSetting = control.setSetting

headers = {'Content-Type': 'application/json'}
session = requests.Session()
retries = Retry(total=4, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504, 520, 521, 522, 524, 530])
session.mount('https://', HTTPAdapter(max_retries=retries, pool_maxsize=100))
session.mount('http://', HTTPAdapter(max_retries=retries, pool_maxsize=100))

yamtrack_icon = control.joinPath(control.artPath(), 'yamtrack.png')
_last_request_time = 0.0

# Status codes (MEDIA_STATUS_MAP in Yamtrack's api/helpers.py)
STATUS_PLANNING = 0
STATUS_WATCHING = 1
STATUS_ONHOLD = 2
STATUS_COMPLETED = 3
STATUS_DROPPED = 4


def yamtrackBaseUrl():
	url = getSetting('yamtrack.baseurl').strip()
	if url and not url.startswith(('http://', 'https://')): url = 'https://' + url
	url = url.rstrip('/')
	if url and not url.endswith('/api/v1'): url = url + '/api/v1'
	return url


def getYamtrackCredentialsInfo():
	return bool(yamtrackBaseUrl() and getSetting('yamtrack.token'))


def getYamtrackIndicatorsInfo():
	return getSetting('indicators.alt') == '5'


#### Core request plumbing (mirrors customtrakt.py's getCustom, minus the reauth loop) ####

def getYamtrack(url, post=None, method=None, silent=False):
	# Returns the raw requests.Response (even for 404/4xx so callers can branch on
	# status_code, e.g. PATCH-then-POST-fallback for untracked items), or None on a
	# hard failure (no base url configured, or an unrecoverable connection error).
	try:
		global _last_request_time
		base = yamtrackBaseUrl()
		if not base: return None
		if time.time() - _last_request_time > 300:
			session.close()
		if not url.startswith(base): url = urljoin(base + '/', url.lstrip('/'))
		req_headers = dict(headers)
		req_headers['Authorization'] = 'Bearer %s' % getSetting('yamtrack.token')
		body = jsdumps(post) if post is not None else None
		if not method: method = 'POST' if post is not None else 'GET'
		method = method.upper()
		for _attempt in range(2):
			try:
				if method == 'POST':
					response = session.post(url, data=body, headers=req_headers, timeout=20)
				elif method == 'PATCH':
					response = session.patch(url, data=body, headers=req_headers, timeout=20)
				elif method == 'DELETE':
					response = session.delete(url, headers=req_headers, timeout=20)
				else:
					response = session.get(url, headers=req_headers, timeout=20)
				_last_request_time = time.time()
				break
			except requests.exceptions.ConnectionError:
				if _attempt == 0:
					log_utils.log('YAMTRACK: connection reset, retrying with fresh connection...', level=log_utils.LOGDEBUG)
					session.close()
				else:
					raise
		status_code = response.status_code
		if status_code == 429:
			if 'Retry-After' in response.headers:
				throttleTime = response.headers['Retry-After']
				control.sleep((int(throttleTime) + 1) * 1000)
				return getYamtrack(url, post=post, method=method, silent=silent)
		if status_code == 401 and not silent:
			log_utils.log_force('YAMTRACK: request unauthorized (invalid/expired token) url=%s' % url, level=log_utils.LOGWARNING)
		elif status_code >= 500 and not silent:
			log_utils.log('YAMTRACK: temporary server problem: %s url=%s' % (status_code, url), level=log_utils.LOGINFO)
		return response
	except Exception as e:
		if not silent: log_utils.log_force('YAMTRACK: getYamtrack exception url=%s error=%s' % (url, e), level=log_utils.LOGWARNING)
		return None


def getYamtrackAsJson(url, post=None, method=None, silent=False):
	try:
		response = getYamtrack(url, post=post, method=method, silent=silent)
		if response is None or response.status_code not in (200, 201): return None
		return response.json()
	except Exception as e:
		if not silent: log_utils.log('YAMTRACK: Error in getYamtrackAsJson: %s' % str(e), level=log_utils.LOGWARNING)
		return None


def get_all_pages(url, silent=False):
	# Confirmed pagination shape: {'pagination': {'total','limit','offset','next','previous'}, 'results': [...]}
	try:
		sep = '&' if '?' in url else '?'
		limit = 250
		offset = 0
		results = []
		while True:
			page_url = url + sep + 'limit=%d&offset=%d' % (limit, offset)
			data = getYamtrackAsJson(page_url, silent=silent)
			if not data: break
			page_results = data.get('results', []) if isinstance(data, dict) else data
			if not page_results: break
			results.extend(page_results)
			if len(page_results) < limit: break
			offset += limit
			if offset > 100000:
				log_utils.log('YAMTRACK: get_all_pages reached safety limit for URL: %s' % url, level=log_utils.LOGWARNING)
				break
		return results
	except Exception as e:
		log_utils.log('YAMTRACK: Error in get_all_pages: %s' % str(e), level=log_utils.LOGWARNING)
		return None


#### Auth: static bearer token pasted from the Yamtrack web UI ####

def yamtrackAuth(fromSettings=0):
	try:
		base = yamtrackBaseUrl()
		token = getSetting('yamtrack.token')
		if not base or not token:
			if fromSettings == 1: control.openSettings('5.6', 'plugin.video.umbrella')
			control.notification(message='Enter a Yamtrack server URL and token first', icon=yamtrack_icon)
			return False
		response = getYamtrack('/media/movie/?limit=1', method='GET', silent=True)
		if not response or response.status_code != 200:
			control.notification(message='Yamtrack Authorization Error - Check URL/Token', icon=yamtrack_icon)
			if fromSettings == 1: control.openSettings('5.6', 'plugin.video.umbrella')
			return False
		setSetting('yamtrack.isauthed', 'true')
		control.notification(message='Yamtrack Authorized Successfully', icon=yamtrack_icon)
		if fromSettings == 1: control.openSettings('5.6', 'plugin.video.umbrella')
		if not control.yesnoDialog('Do you want to set Yamtrack as your service for your watched and unwatched indicators?', '', '', 'Indicators', 'No', 'Yes'): return True
		control.homeWindow.setProperty('umbrella.updateSettings', 'false')
		setSetting('indicators.alt', '5')
		setSetting('scrobble.source', '5')
		control.homeWindow.setProperty('umbrella.updateSettings', 'true')
		setSetting('scrobble', 'Yamtrack')
		setSetting('indicators', 'Yamtrack')
		control.notification(message='Yamtrack Indicators Enabled - Syncing Watched Data...')
		from threading import Thread
		Thread(target=sync_watched, kwargs={'forced': True}).start()
		return True
	except:
		log_utils.error()
		return False


def yamtrackRevoke(fromSettings=0):
	control.homeWindow.setProperty('umbrella.updateSettings', 'false')
	setSetting('yamtrack.user.name', '')
	setSetting('yamtrack.token', '')
	setSetting('yamtrack.isauthed', '')
	control.homeWindow.setProperty('umbrella.updateSettings', 'true')
	try:
		clr_tables = ('bookmarks', 'yamtrack_watched_movies', 'yamtrack_watched_episodes',
			'movies_plantowatch', 'shows_plantowatch', 'movies_watching', 'shows_watching',
			'movies_hold', 'shows_hold', 'movies_completed', 'shows_completed',
			'movies_dropped', 'shows_dropped', 'movies_collection', 'shows_collection')
		yamtracksync.delete_yamtrack_tables(clr_tables)
		if getSetting('indicators.alt') == '5':
			setSetting('indicators.alt', '0')
			setSetting('indicators', 'Local')
		if getSetting('scrobble.source') == '5':
			setSetting('scrobble.source', '0')
			setSetting('scrobble', 'Local')
		setSetting('yamtrack.markwatched', 'false')
		if fromSettings == 1:
			control.openSettings('5.6', 'plugin.video.umbrella')
			control.dialog.ok('Yamtrack', 'Yamtrack Authorization Revoked')
	except:
		log_utils.error()


#### TMDb id resolution (Yamtrack is TMDB-native; Umbrella calls into these with imdb/tvdb) ####

def _resolve_tmdb(media_type, imdb='', tvdb=''):
	try:
		if not imdb and not tvdb: return ''
		from resources.lib.database import cache as _cache
		from resources.lib.indexers import tmdb as _tmdb
		if media_type == 'movie':
			result = _cache.get(_tmdb.Movies().IdLookup, 96, imdb) if imdb else None
		else:
			result = _cache.get(_tmdb.TVshows().IdLookup, 96, imdb, tvdb)
		return str(result.get('id', '')) if result else ''
	except:
		log_utils.error()
		return ''


def _now_iso():
	return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z')


#### URL helpers ####

def _movie_url(tmdb): return '/media/movie/tmdb/%s/' % tmdb
def _tv_url(tmdb): return '/media/tv/tmdb/%s/' % tmdb
def _season_url(tmdb, season): return '/media/tv/tmdb/%s/%s/' % (tmdb, season)
def _episode_url(tmdb, season, episode): return '/media/tv/tmdb/%s/%s/%s/' % (tmdb, season, episode)
def _episode_watch_url(tmdb, season, episode): return '/media/tv/tmdb/%s/%s/episodes/%s/watch/' % (tmdb, season, episode)
def _episode_drop_url(tmdb, season, episode): return '/media/tv/tmdb/%s/%s/episodes/%s/drop/' % (tmdb, season, episode)


def _patch_or_create(detail_url, media_type, tmdb, body, season_number=None):
	# Try PATCH on the already-tracked item first; if it isn't tracked yet (404),
	# fall back to POST to create it. Returns True on success.
	response = getYamtrack(detail_url, post=body, method='PATCH', silent=True)
	if response is not None and response.status_code == 200: return True
	create_body = dict(body)
	create_body['source'] = 'tmdb'
	create_body['media_id'] = str(tmdb)
	if season_number is not None: create_body['season_number'] = int(season_number)
	response = getYamtrack('/media/%s/' % media_type, post=create_body, method='POST', silent=True)
	return bool(response is not None and response.status_code in (200, 201))


#### Watch/unwatch + mark watched ####

def markMovieAsWatched(imdb, tmdb=''):
	try:
		if not tmdb: tmdb = _resolve_tmdb('movie', imdb=imdb)
		if not tmdb: return False
		success = _patch_or_create(_movie_url(tmdb), 'movie', tmdb, {'status': STATUS_COMPLETED})
		if success:
			yamtracksync.upsert_watched_movie(imdb=imdb or '', tmdb=str(tmdb), last_watched_at=_now_iso())
			yamtracksync.cache_delete(yamtracksync._hash_function(syncMovies, ()))
		return success
	except:
		log_utils.error()
		return False

def markMovieAsNotWatched(imdb, tmdb=''):
	try:
		if not tmdb: tmdb = _resolve_tmdb('movie', imdb=imdb)
		if not tmdb: return False
		# PATCH back to Planning rather than DELETE, so score/notes/dates the user
		# set aren't destroyed by an unwatch action.
		response = getYamtrack(_movie_url(tmdb), post={'status': STATUS_PLANNING}, method='PATCH', silent=True)
		success = bool(response is not None and response.status_code == 200)
		if success:
			yamtracksync.delete_watched_movie(tmdb)
			yamtracksync.cache_delete(yamtracksync._hash_function(syncMovies, ()))
		return success
	except:
		log_utils.error()
		return False

def markTVShowAsWatched(imdb, tvdb):
	try:
		tmdb = _resolve_tmdb('tv', imdb=imdb, tvdb=tvdb)
		if not tmdb: return False
		success = _patch_or_create(_tv_url(tmdb), 'tv', tmdb, {'status': STATUS_COMPLETED})
		if success:
			yamtracksync.cache_delete(yamtracksync._hash_function(syncTVShows, ()))
			yamtracksync.cache_delete(yamtracksync._hash_function(_fetchShowProgress, (tmdb,)))
		return success
	except:
		log_utils.error()
		return False

def markTVShowAsNotWatched(imdb, tvdb):
	try:
		tmdb = _resolve_tmdb('tv', imdb=imdb, tvdb=tvdb)
		if not tmdb: return False
		response = getYamtrack(_tv_url(tmdb), post={'status': STATUS_PLANNING}, method='PATCH', silent=True)
		success = bool(response is not None and response.status_code == 200)
		if success:
			for (si, st, sv, s, e) in yamtracksync.get_watched_episodes():
				if st == tmdb: yamtracksync.delete_watched_episode(st, s, e)
			yamtracksync.cache_delete(yamtracksync._hash_function(syncTVShows, ()))
			yamtracksync.cache_delete(yamtracksync._hash_function(_fetchShowProgress, (tmdb,)))
		return success
	except:
		log_utils.error()
		return False

def markSeasonAsWatched(imdb, tvdb, season):
	try:
		tmdb = _resolve_tmdb('tv', imdb=imdb, tvdb=tvdb)
		if not tmdb: return False
		season = int('%01d' % int(season))
		success = _patch_or_create(_season_url(tmdb, season), 'season', tmdb, {'status': STATUS_COMPLETED}, season_number=season)
		if success:
			yamtracksync.cache_delete(yamtracksync._hash_function(syncTVShows, ()))
			yamtracksync.cache_delete(yamtracksync._hash_function(_fetchShowProgress, (tmdb,)))
		return success
	except:
		log_utils.error()
		return False

def markSeasonAsNotWatched(imdb, tvdb, season):
	try:
		tmdb = _resolve_tmdb('tv', imdb=imdb, tvdb=tvdb)
		if not tmdb: return False
		season = int('%01d' % int(season))
		response = getYamtrack(_season_url(tmdb, season), post={'status': STATUS_PLANNING}, method='PATCH', silent=True)
		success = bool(response is not None and response.status_code == 200)
		if success:
			for (si, st, sv, s, e) in yamtracksync.get_watched_episodes():
				if st == tmdb and int(s) == season: yamtracksync.delete_watched_episode(st, s, e)
			yamtracksync.cache_delete(yamtracksync._hash_function(syncTVShows, ()))
			yamtracksync.cache_delete(yamtracksync._hash_function(_fetchShowProgress, (tmdb,)))
		return success
	except:
		log_utils.error()
		return False

def markEpisodeAsWatched(imdb, tvdb, season, episode):
	try:
		tmdb = _resolve_tmdb('tv', imdb=imdb, tvdb=tvdb)
		if not tmdb: return False
		season, episode = int('%01d' % int(season)), int('%01d' % int(episode))
		response = getYamtrack(_episode_watch_url(tmdb, season, episode), post={}, method='POST', silent=True)
		success = bool(response is not None and response.status_code in (200, 201))
		if success:
			yamtracksync.upsert_watched_episode(show_imdb=imdb or '', show_tmdb=tmdb, show_tvdb=str(tvdb or ''), season=season, episode=episode, last_watched_at=_now_iso())
			yamtracksync.cache_delete(yamtracksync._hash_function(syncTVShows, ()))
			yamtracksync.cache_delete(yamtracksync._hash_function(_fetchShowProgress, (tmdb,)))
		return success
	except:
		log_utils.error()
		return False

def markEpisodeAsNotWatched(imdb, tvdb, season, episode):
	try:
		tmdb = _resolve_tmdb('tv', imdb=imdb, tvdb=tvdb)
		if not tmdb: return False
		season, episode = int('%01d' % int(season)), int('%01d' % int(episode))
		response = getYamtrack(_episode_url(tmdb, season, episode), method='DELETE', silent=True)
		success = bool(response is not None and response.status_code in (200, 204))
		if success:
			yamtracksync.delete_watched_episode(tmdb, season, episode)
			yamtracksync.cache_delete(yamtracksync._hash_function(syncTVShows, ()))
			yamtracksync.cache_delete(yamtracksync._hash_function(_fetchShowProgress, (tmdb,)))
		return success
	except:
		log_utils.error()
		return False


def watch(content_type, name, imdb=None, tvdb=None, season=None, episode=None, refresh=True):
	control.busy()
	success = False
	if content_type == 'movie': success = markMovieAsWatched(imdb)
	elif content_type == 'tvshow': success = markTVShowAsWatched(imdb, tvdb)
	elif content_type == 'season': success = markSeasonAsWatched(imdb, tvdb, season)
	elif content_type == 'episode': success = markEpisodeAsWatched(imdb, tvdb, season, episode)
	control.hide()
	if refresh: control.refresh()
	control.trigger_widget_refresh()
	if season and not episode: name = '%s-Season%s...' % (name, season)
	if season and episode: name = '%s-S%sxE%02d...' % (name, season, int(episode))
	if getSetting('yamtrack.general.notifications') == 'true':
		if success is True: control.notification(title='Yamtrack', message='%s Marked as Watched on Yamtrack' % name)
		else: control.notification(title='Yamtrack', message='%s Failed to Mark as Watched on Yamtrack' % name)

def unwatch(content_type, name, imdb=None, tvdb=None, season=None, episode=None, refresh=True):
	control.busy()
	success = False
	if content_type == 'movie': success = markMovieAsNotWatched(imdb)
	elif content_type == 'tvshow': success = markTVShowAsNotWatched(imdb, tvdb)
	elif content_type == 'season': success = markSeasonAsNotWatched(imdb, tvdb, season)
	elif content_type == 'episode': success = markEpisodeAsNotWatched(imdb, tvdb, season, episode)
	control.hide()
	if refresh: control.refresh()
	control.trigger_widget_refresh()
	if season and not episode: name = '%s-Season%s...' % (name, season)
	if season and episode: name = '%s-S%sxE%02d...' % (name, season, int(episode))
	if getSetting('yamtrack.general.notifications') == 'true':
		if success is True: control.notification(title='Yamtrack', message='%s Marked as Unwatched on Yamtrack' % name)
		else: control.notification(title='Yamtrack', message='%s Failed to Mark as Unwatched on Yamtrack' % name)


#### Scrobble (real POST /scrobble/ endpoint — start/pause update the server's live
#### Now Playing card only; local resume/bookmark state is tracked client-side since
#### Yamtrack has no queryable "in progress playback" list to pull from). ####

def scrobbleStart(media_type, title='', tvshowtitle='', year='0', imdb='', tmdb='', tvdb='', season='', episode='', watched_percent=0):
	try:
		ids = {}
		if tmdb: ids['tmdb'] = str(tmdb)
		if imdb: ids['imdb'] = str(imdb)
		if tvdb: ids['tvdb'] = str(tvdb)
		body = {'action': 'start', 'media_type': 'movie' if media_type == 'movie' else 'episode', 'ids': ids,
			'title': title, 'series_title': tvshowtitle,
			'season_number': int(season) if season else None, 'episode_number': int(episode) if episode else None,
			'position_seconds': int(watched_percent), 'duration_seconds': 100}
		getYamtrack('/scrobble/', post=body, method='POST', silent=True)
	except: log_utils.error()

def scrobbleMovie(imdb, tmdb, watched_percent):
	try:
		ids = {}
		if tmdb: ids['tmdb'] = str(tmdb)
		if imdb: ids['imdb'] = str(imdb)
		body = {'action': 'pause', 'media_type': 'movie', 'ids': ids, 'position_seconds': int(watched_percent), 'duration_seconds': 100}
		response = getYamtrack('/scrobble/', post=body, method='POST', silent=True)
		if response is not None and response.status_code == 200:
			yamtracksync.upsert_bookmark(title='', resume_id='', imdb=imdb or '', tmdb=str(tmdb or ''), percent_played=str(watched_percent), paused_at=_now_iso())
			control.trigger_widget_refresh()
	except: log_utils.error()

def scrobbleEpisode(imdb, tmdb, tvdb, season, episode, watched_percent):
	try:
		season, episode = int('%01d' % int(season)), int('%01d' % int(episode))
		ids = {}
		if tmdb: ids['tmdb'] = str(tmdb)
		if imdb: ids['imdb'] = str(imdb)
		if tvdb: ids['tvdb'] = str(tvdb)
		body = {'action': 'pause', 'media_type': 'episode', 'ids': ids, 'season_number': season, 'episode_number': episode,
			'position_seconds': int(watched_percent), 'duration_seconds': 100}
		response = getYamtrack('/scrobble/', post=body, method='POST', silent=True)
		if response is not None and response.status_code == 200:
			yamtracksync.upsert_bookmark(tvshowtitle='x', title='', resume_id='', imdb=imdb or '', tmdb=str(tmdb or ''), tvdb=str(tvdb or ''), season=str(season), episode=str(episode), percent_played=str(watched_percent), paused_at=_now_iso())
			control.trigger_widget_refresh()
	except: log_utils.error()

def scrobbleReset(imdb, tmdb=None, tvdb=None, season=None, episode=None, refresh=True, widgetRefresh=False, clear_local=True):
	if not getYamtrackCredentialsInfo(): return
	try:
		if clear_local: yamtracksync.delete_bookmark(imdb or '', tvdb=tvdb or '', tmdb=str(tmdb or ''), season=season or '', episode=episode or '')
		if refresh: control.refresh()
		if widgetRefresh: control.trigger_widget_refresh()
	except: log_utils.error()


#### Status-bucket sync (Watchlist/Watching/On Hold/Completed/Dropped/Collection) ####

_STATUS_TABLES = {
	STATUS_PLANNING: ('movies_plantowatch', 'shows_plantowatch'),
	STATUS_WATCHING: ('movies_watching', 'shows_watching'),
	STATUS_ONHOLD:   ('movies_hold', 'shows_hold'),
	STATUS_COMPLETED:('movies_completed', 'shows_completed'),
	STATUS_DROPPED:  ('movies_dropped', 'shows_dropped'),
}

def _fetch_status_bucket(media_type, status):
	items = get_all_pages('/media/%s/?status=%s' % (media_type, status), silent=True)
	return items or []

def sync_watchedProgress(activities=None, forced=False):
	try:
		if not getYamtrackCredentialsInfo(): return
		items = _fetch_status_bucket('movie', STATUS_COMPLETED)
		yamtracksync.delete_yamtrack_tables(('yamtrack_watched_movies',))
		for i in items:
			item = i.get('item') or {}
			tmdb = str(item.get('media_id') or '')
			if not tmdb: continue
			yamtracksync.upsert_watched_movie(tmdb=tmdb, title=item.get('title', ''), last_watched_at=i.get('progressed_at') or i.get('created_at') or _now_iso())
		yamtracksync.update_last_watched_at('last_history_at')
		yamtracksync.cache_delete(yamtracksync._hash_function(syncMovies, ()))
		yamtracksync.cache_delete(yamtracksync._hash_function(syncTVShows, ()))
		control.trigger_widget_refresh()
	except: log_utils.error()

def sync_watched(activities=None, forced=False):
	sync_watchedProgress(activities=activities, forced=forced)

def sync_watch_list(activities=None, forced=False):
	# Pulls all 5 status buckets (not just Planning) so every My Movies/My TV Shows
	# Yamtrack submenu list (Watchlist/Watching/On Hold/Completed/Dropped) is populated.
	try:
		if not getYamtrackCredentialsInfo(): return
		for status, (mv_table, tv_table) in _STATUS_TABLES.items():
			yamtracksync.insert_status_list(_fetch_status_bucket('movie', status), mv_table)
			yamtracksync.insert_status_list(_fetch_status_bucket('tv', status), tv_table)
	except: log_utils.error()

def sync_collection(activities=None, forced=False):
	try:
		if not getYamtrackCredentialsInfo(): return
		items = get_all_pages('/collection/?item_media_type=movie', silent=True) or []
		yamtracksync.insert_status_list([{'id': i.get('item', {}).get('id'), 'item': i.get('item'), 'score': None, 'created_at': i.get('collected_at')} for i in items], 'movies_collection')
		items = get_all_pages('/collection/?item_media_type=tv', silent=True) or []
		yamtracksync.insert_status_list([{'id': i.get('item', {}).get('id'), 'item': i.get('item'), 'score': None, 'created_at': i.get('collected_at')} for i in items], 'shows_collection')
	except: log_utils.error()

def sync_playbackProgress(activities=None, forced=False):
	# No queryable server-side "in progress playback" endpoint exists for this
	# provider — local bookmarks are maintained directly by scrobbleMovie/
	# scrobbleEpisode, so this is a deliberate no-op kept for call-site symmetry
	# with the other providers' services_syncs() loop.
	pass

def force_yamtrackSync():
	if not control.yesnoDialog(control.lang(32056), '', ''): return
	control.busy()
	clr_tables = ('yamtrack_watched_movies', 'yamtrack_watched_episodes',
		'movies_plantowatch', 'shows_plantowatch', 'movies_watching', 'shows_watching',
		'movies_hold', 'shows_hold', 'movies_completed', 'shows_completed',
		'movies_dropped', 'shows_dropped', 'movies_collection', 'shows_collection')
	yamtracksync.delete_yamtrack_tables(clr_tables)
	sync_watch_list(forced=True)
	sync_collection(forced=True)
	sync_watchedProgress(forced=True)
	control.hide()
	control.notification(title='Yamtrack', message='Forced Yamtrack Sync Complete')


#### Indicators (movies/shows watched state, seasons/episodes progress) ####

def syncMovies():
	try:
		if not getYamtrackCredentialsInfo(): return None
		return yamtracksync.get_watched_movies() or []
	except:
		log_utils.error()
		return None

def _make_episode_ranges(ep_nums_sorted):
	if not ep_nums_sorted: return []
	ranges = []
	start = end = ep_nums_sorted[0]
	for ep in ep_nums_sorted[1:]:
		if ep == end + 1: end = ep
		else:
			ranges.append((start, end))
			start = end = ep
	ranges.append((start, end))
	return ranges

def syncTVShows():
	try:
		if not getYamtrackCredentialsInfo(): return None
		episodes = yamtracksync.get_watched_episodes()
		if not episodes: return []
		shows = {}
		for (show_imdb, show_tmdb, show_tvdb, season, episode) in episodes:
			if show_tmdb not in shows:
				shows[show_tmdb] = {'ids': {'imdb': show_imdb, 'tmdb': show_tmdb, 'tvdb': show_tvdb}, 'by_season': {}}
			s = int(season)
			shows[show_tmdb]['by_season'].setdefault(s, []).append(int(episode))
		indicators = []
		for v in shows.values():
			ep_ranges = {s: _make_episode_ranges(sorted(eps)) for s, eps in v['by_season'].items()}
			total = sum(e - s + 1 for ranges in ep_ranges.values() for s, e in ranges)
			indicators.append((v['ids'], total, ep_ranges))
		return indicators
	except:
		log_utils.error()
		return None

def getShowProgress(tmdb):
	try:
		if not tmdb: return None
		return yamtracksync.get(_fetchShowProgress, 15, tmdb)
	except:
		log_utils.error()
		return None

def _fetchShowProgress(tmdb):
	# The tv-detail response's nested season progress isn't confirmed reliable
	# enough to trust for per-season total/watched/unwatched counts, so this is
	# computed locally from yamtracksync's tracked-episode table plus TMDb season
	# metadata, mirroring customtrakt.py's _local_syncSeasons fallback exactly.
	try:
		episodes = yamtracksync.get_watched_episodes()
		if not episodes: return [[], {}]
		show_eps = [(s, e) for (si, st, sv, s, e) in episodes if st == tmdb]
		if not show_eps: return [[], {}]
		from collections import defaultdict
		by_season = defaultdict(list)
		for (s, e) in show_eps: by_season[int(s)].append(int(e))
		from resources.lib.database import cache as _cache
		from resources.lib.indexers import tmdb as _tmdb
		season_counts = {}
		try:
			showSeasons = _cache.get(_tmdb.TVshows().get_showSeasons_meta, 96, tmdb)
			if showSeasons:
				for s in showSeasons.get('seasons', []):
					season_counts[s.get('season_number')] = s.get('episode_count', 0)
		except: pass
		result_counts = {}
		fully_watched = []
		for s, watched_eps in by_season.items():
			total = season_counts.get(s, len(set(watched_eps)))
			watched = len(set(watched_eps))
			result_counts[s] = {'total': total, 'watched': watched, 'unwatched': max(total - watched, 0)}
			if watched >= total: fully_watched.append(s)
		return [[str(s) for s in sorted(fully_watched)], result_counts]
	except:
		log_utils.error()
		return None

def syncSeasons(imdb, tvdb):
	try:
		if not getYamtrackCredentialsInfo(): return None
		if not imdb and not tvdb: return None
		tmdb = _resolve_tmdb('tv', imdb=imdb, tvdb=tvdb)
		if not tmdb: return [[], {}]
		progress = getShowProgress(tmdb)
		return progress if progress else [[], {}]
	except:
		log_utils.error()
		return None

def getMoviesWatchedActivity():
	try: return yamtracksync.last_sync('last_history_at')
	except: log_utils.error()
	return 0

def getEpisodesWatchedActivity():
	try: return yamtracksync.last_sync('last_history_at')
	except: log_utils.error()
	return 0

def timeoutsyncMovies():
	return yamtracksync.timeout(syncMovies)

def timeoutsyncTVShows():
	return yamtracksync.timeout(syncTVShows)

def timeoutsyncSeasons(imdb, tvdb):
	try: return yamtracksync.timeout(syncSeasons, imdb, tvdb, returnNone=True)
	except: log_utils.error()

def cachesyncMovies(timeout=720):
	try: return yamtracksync.get(syncMovies, timeout)
	except: log_utils.error()

def cachesyncTVShows(timeout=720):
	try: return yamtracksync.get(syncTVShows, timeout)
	except: log_utils.error()

def cachesyncTV(imdb, tvdb):
	try:
		from threading import Thread as _Thread
		threads = [_Thread(target=cachesyncTVShows, args=(0,)), _Thread(target=cachesyncSeasons, args=(imdb, tvdb, 0))]
		[i.start() for i in threads]
		[i.join() for i in threads]
	except: log_utils.error()

def cachesyncSeasons(imdb, tvdb='', timeout=720):
	try:
		imdb = imdb or ''
		tvdb = tvdb or ''
		return yamtracksync.get(syncSeasons, timeout, imdb, tvdb)
	except: log_utils.error()

def seasonCount(imdb, tvdb):
	try:
		result = syncSeasons(imdb, tvdb)
		if result and len(result) > 1: return result[1]
		return {}
	except: log_utils.error()


#### Watchlist / Collection membership (context-menu actions) ####

def add_to_watchlist(tmdb='', media_type='movie', season_number=None):
	try:
		media = 'movie' if media_type == 'movie' else ('season' if season_number is not None else 'tv')
		body = {'source': 'tmdb', 'media_id': str(tmdb), 'status': STATUS_PLANNING}
		if season_number is not None: body['season_number'] = int(season_number)
		response = getYamtrack('/media/%s/' % media, post=body, method='POST', silent=True)
		return bool(response is not None and response.status_code in (200, 201, 409))
	except:
		log_utils.error()
		return False

def remove_from_watchlist(tmdb='', media_type='movie'):
	try:
		url = _movie_url(tmdb) if media_type == 'movie' else _tv_url(tmdb)
		response = getYamtrack(url, method='DELETE', silent=True)
		return bool(response is not None and response.status_code in (200, 204))
	except:
		log_utils.error()
		return False

def _resolve_item_pk(tmdb, media_type='movie'):
	try:
		url = _movie_url(tmdb) if media_type == 'movie' else _tv_url(tmdb)
		result = getYamtrackAsJson(url, silent=True)
		if not result: return None
		return result.get('id')
	except:
		log_utils.error()
		return None

def add_to_collection(tmdb='', media_type='movie'):
	try:
		item_pk = _resolve_item_pk(tmdb, media_type)
		if not item_pk: return False
		response = getYamtrack('/collection/', post={'item_id': item_pk}, method='POST', silent=True)
		return bool(response is not None and response.status_code in (200, 201))
	except:
		log_utils.error()
		return False

def remove_from_collection(entry_id):
	try:
		response = getYamtrack('/collection/%s/' % entry_id, method='DELETE', silent=True)
		return bool(response is not None and response.status_code in (200, 204))
	except:
		log_utils.error()
		return False

def set_status(tmdb='', media_type='movie', status=STATUS_PLANNING):
	try:
		success = _patch_or_create(_movie_url(tmdb) if media_type == 'movie' else _tv_url(tmdb), media_type, tmdb, {'status': status})
		return success
	except:
		log_utils.error()
		return False


#### Context-menu manager (mirrors customtrakt.manager()/simkl.manager()) ####

def manager(name, imdb=None, tvdb=None, tmdb=None, season=None, episode=None, refresh=True, watched=None, unfinished=False, tvshow=None):
	try:
		if season: season = int(season)
		if episode: episode = int(episode)
		if episode: content_type = 'episode'
		elif season: content_type = 'season'
		elif tvdb and tvdb != 'None': content_type = 'tvshow'
		else: content_type = 'movie'
		media_type = 'movie' if content_type == 'movie' else 'tv'
		hc = getSetting('highlight.color')
		items = []
		if watched is not None:
			items += [('[COLOR %s]Unwatch[/COLOR]' % hc, 'unwatch')] if watched else [('[COLOR %s]Watch[/COLOR]' % hc, 'watch')]
		else:
			items += [('[COLOR %s]Watch[/COLOR]' % hc, 'watch')]
			items += [('[COLOR %s]Unwatch[/COLOR]' % hc, 'unwatch')]
		if content_type in ('movie', 'episode'):
			items += [('[COLOR %s]Clear Scrobble Progress[/COLOR]' % hc, 'scrobbleReset')]
		if content_type in ('movie', 'tvshow'):
			items += [('[COLOR %s]Add to Watchlist[/COLOR]' % hc, 'watchlist_add')]
			items += [('[COLOR %s]Remove from Watchlist[/COLOR]' % hc, 'watchlist_remove')]
			items += [('[COLOR %s]Set to Watching[/COLOR]' % hc, 'set_watching')]
			items += [('[COLOR %s]Set to On Hold[/COLOR]' % hc, 'set_onhold')]
			items += [('[COLOR %s]Set to Dropped[/COLOR]' % hc, 'set_dropped')]
			items += [('[COLOR %s]Add to Collection[/COLOR]' % hc, 'collection_add')]
		control.hide()
		select = control.selectDialog([i[0] for i in items], heading=control.addonInfo('name') + ' - Yamtrack')
		if select == -1: return
		action_key = items[select][1]
		if action_key == 'watch':
			watch(content_type, name, imdb=imdb, tvdb=tvdb, season=season, episode=episode, refresh=refresh)
		elif action_key == 'unwatch':
			unwatch(content_type, name, imdb=imdb, tvdb=tvdb, season=season, episode=episode, refresh=refresh)
		elif action_key == 'scrobbleReset':
			scrobbleReset(imdb=imdb, tmdb=tmdb, tvdb=tvdb, season=season, episode=episode, refresh=True)
		elif action_key == 'watchlist_add':
			resolved_tmdb = tmdb or _resolve_tmdb(media_type, imdb=imdb, tvdb=tvdb)
			if resolved_tmdb and add_to_watchlist(tmdb=resolved_tmdb, media_type=media_type):
				sync_watch_list(forced=True)
				if refresh: control.refresh()
		elif action_key == 'watchlist_remove':
			resolved_tmdb = tmdb or _resolve_tmdb(media_type, imdb=imdb, tvdb=tvdb)
			if resolved_tmdb and remove_from_watchlist(tmdb=resolved_tmdb, media_type=media_type):
				sync_watch_list(forced=True)
				if refresh: control.refresh()
		elif action_key in ('set_watching', 'set_onhold', 'set_dropped'):
			resolved_tmdb = tmdb or _resolve_tmdb(media_type, imdb=imdb, tvdb=tvdb)
			status_map = {'set_watching': STATUS_WATCHING, 'set_onhold': STATUS_ONHOLD, 'set_dropped': STATUS_DROPPED}
			if resolved_tmdb and set_status(tmdb=resolved_tmdb, media_type=media_type, status=status_map[action_key]):
				sync_watch_list(forced=True)
				if refresh: control.refresh()
		elif action_key == 'collection_add':
			resolved_tmdb = tmdb or _resolve_tmdb(media_type, imdb=imdb, tvdb=tvdb)
			if resolved_tmdb and add_to_collection(tmdb=resolved_tmdb, media_type=media_type):
				sync_collection(forced=True)
				if refresh: control.refresh()
	except: log_utils.error()
