# -*- coding: utf-8 -*-
# By Umbrella for Umbrella (04/15/25)
"""
	Umbrella Add-on
"""
from resources.lib.modules import log_utils
from resources.lib.modules import control
from urllib.parse import urljoin
from json import dumps as jsdumps, loads as jsloads
import requests
from resources.lib.database import cache, scrobblesync

session = requests.Session()
getSetting = control.setting
BASE_URL = 'https://scrobblesync.xyz'
API_KEY = getSetting('scrobblesync.key')
session.headers['Authorization'] = 'Bearer %s' % API_KEY
headers = {'Content-Type': 'application/json', 'Authorization': ''}

def get_scrobblesync(url, post=None, extended=False):
	try:
		if not url.startswith(BASE_URL): url = urljoin(BASE_URL, url)
		if headers['Authorization'] == '': headers['Authorization']='Bearer %s' % API_KEY
		if post: post = jsdumps(post)
		if post:
			response = session.post(url, data=post, headers=headers, timeout=20)
		else:
			response = session.get(url, headers=headers, timeout=20)
		status_code = str(response.status_code)

		if response and status_code in ('200', '201'):
			if extended: return response, response.headers
			else: return response
		else: return None
	except: log_utils.error('get_scrobblesync Error: ')
	return None

def scrobbleMovie(imdb, tmdb, watched_percent):
	log_utils.log('ScrobbleSync Scrobble Movie Called. Received: imdb: %s tmdb: %s watched_percent: %s' % (imdb, tmdb, watched_percent), level=log_utils.LOGDEBUG)
	try:
		if not imdb.startswith('tt'): imdb = 'tt' + imdb
		success = get_scrobblesync('/records/', {"imdb": imdb, "type": "movie", "percent_watched": watched_percent})
		if success:
			log_utils.log('ScrobbleSync Scrobble Movie Success: imdb: %s s' % (imdb), level=log_utils.LOGDEBUG)
			if getSetting('scrobblesync.scrobble.notify') == 'true': control.notification(message=40599)
			control.sleep(1000)
			#sync_playbackProgress(forced=True)
			#control.trigger_widget_refresh()
		else: control.notification(message=40600)
	except: log_utils.error()

def scrobbleEpisode(imdb, tmdb, tvdb, season, episode, watched_percent):
	try:
		season, episode = int('%01d' % int(season)), int('%01d' % int(episode))
		success = get_scrobblesync('/scrobble/pause', {"show": {"ids": {"tvdb": tvdb}}, "episode": {"season": season, "number": episode}, "progress": watched_percent})
		if success:
			log_utils.log('ScrobbleSync Scrobble Episode Success: imdb: %s s' % (imdb), level=log_utils.LOGDEBUG)
			if getSetting('scrobblesync.scrobble.notify') == 'true': control.notification(message=40599)
			control.sleep(1000)
			#sync_playbackProgress(forced=True)
			#control.trigger_widget_refresh()
		else: control.notification(message=40600)
	except: log_utils.error()

def scrobbleReset(imdb, tmdb=None, tvdb=None, season=None, episode=None, refresh=True, widgetRefresh=False):
	if not control.player.isPlaying(): control.busy()
	success = False
	try:
		content_type = 'movie' if not episode else 'episode'
		resume_info = scrobblesync.fetch_bookmarks(imdb, tmdb, tvdb, season, episode, ret_type='resume_info')
		if resume_info == '0': return control.hide() # returns string "0" if no data in db 
		headers['Authorization'] = 'Bearer %s' % getSetting('trakt.user.token')
		success = session.delete('https://api.trakt.tv/sync/playback/%s' % resume_info[1], headers=headers).status_code == 204
		if content_type == 'movie':
			items = [{'type': 'movie', 'movie': {'ids': {'imdb': imdb}}}]
			label_string = resume_info[0]
		else:
			items = [{'type': 'episode', 'episode': {'season': season, 'number': episode}, 'show': {'ids': {'imdb': imdb, 'tvdb': tvdb}}}]
			label_string = resume_info[0] + ' - ' + 'S%02dE%02d' % (int(season), int(episode))
		control.hide()
		if success:
			timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
			items[0].update({'paused_at': timestamp})
			traktsync.delete_bookmark(items)
			if refresh: control.refresh()
			if widgetRefresh: control.trigger_widget_refresh() # skinshortcuts handles the widget_refresh when plyback ends, but not a manual clear from Trakt Manager
			if getSetting('trakt.scrobble.notify') == 'true': control.notification(title=32315, message='Successfuly Removed playback progress:  [COLOR %s]%s[/COLOR]' % (highlight_color, label_string))
			log_utils.log('Successfuly Removed Trakt Playback Progress:  %s  with resume_id=%s' % (label_string, str(resume_info[1])), __name__, level=log_utils.LOGDEBUG)
		else:
			#if getSetting('trakt.scrobble.notify') == 'true': control.notification(title=32315, message='Failed to Remove playback progress:  [COLOR %s]%s[/COLOR]' % (highlight_color, label_string))
			log_utils.log('Failed to Remove Trakt Playback Progress:  %s  with resume_id=%s' % (label_string, str(resume_info[1])), __name__, level=log_utils.LOGDEBUG)
	except: log_utils.error()

def sync_playbackProgress(activities=None, forced=False):
	#log_utils.log('Trakt Sync Playback Called Forced: %s' % (str(forced)), level=log_utils.LOGDEBUG)
	try:
		link = '/sync/playback/?extended=full'
		if forced:
			items = get_scrobblesync_as_json(link, silent=True)
			if items: traktsync.insert_bookmarks(items)
		else:
			db_last_paused = traktsync.last_sync('last_paused_at')
			activity = getPausedActivity(activities)
			if activity - db_last_paused >= 120: # do not sync unless 2 min difference or more
				items = get_scrobblesync_as_json(link, silent=True)
				if items: traktsync.insert_bookmarks(items)
	except: log_utils.error()

def get_scrobblesync_as_json(url, post=None, silent=False):
	try:
		r = get_scrobblesync(url=url, post=post, extended=True, silent=silent)
		if isinstance(r, tuple) and len(r) == 2: r = r[0]
		if not r: return
		r = r.json()
		return r
	except: log_utils.error()

def getPausedActivity(activities=None):
	try:
		if activities: i = activities
		else: i = get_scrobblesync_as_json('/activities')
		if not i: return 0
		activity = []
		activity.append(i['movies']['paused_at'])
		activity.append(i['episodes']['paused_at'])
		activity = [int(cleandate.iso_2_utc(i)) for i in activity]
		activity = sorted(activity, key=int)[-1]
		return activity
	except: log_utils.error()