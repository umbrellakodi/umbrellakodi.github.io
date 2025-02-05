# -*- coding: utf-8 -*-
"""
	Umbrella Add-on (added by Umbrella Dev 12/23/22)
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from resources.lib.modules import control
from resources.lib.database import simklsync, cache
from resources.lib.modules import log_utils
from datetime import datetime
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
from resources.lib.modules import cleandate
import json
from itertools import islice


getLS = control.lang
getSetting = control.setting
BASE_URL = 'https://api.simkl.com'
oauth_base_url = 'https://api.simkl.com/oauth/pin'
simkl_icon = control.joinPath(control.artPath(), 'simkl.png')
simklclientid = 'cecec23773dff71d940876860a316a4b74666c4c31ad719fe0af8bb3064a34ab'
session = requests.Session()
retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
session.mount('https://api.simkl.com', HTTPAdapter(max_retries=retries, pool_maxsize=100))
sim_qr = control.joinPath(control.artPath(), 'simklqr.png')
highlightColor = control.setting('highlight.color')
headers = {}

class SIMKL:
	name = "Simkl"
	def __init__(self):
		self.hosters = None
		self.hosts = None
		self.token = getSetting('simkltoken')
		self.secret = getSetting('simkl')
		self.device_code = ''
		self.user_code = ''
		self.auth_timeout = 0
		self.auth_step = 0
		

	def auth_loop(self, fromSettings=0):
		control.sleep(self.auth_step*1000)
		url = '/%s?client_id=%s&redirect_uri=urn:ietf:wg:oauth:2.0:oob' % (self.user_code, self.client_ID)
		url = oauth_base_url + url
		response = session.get(url)
		if response.status_code == 200:
			responseJson = response.json()
			if responseJson.get('result') == 'KO':
				return #
			else:
				try:
					self.progressDialog.close()
					self.secret = responseJson['access_token']
				except:
					log_utils.error()
					control.okDialog(title='default', message=40347)
					if fromSettings == 1:
						control.openSettings('9.0', 'plugin.video.umbrella')
				return
		else:
			log_utils.error()
			return

	def auth(self, fromSettings=0):
		self.secret = ''
		self.client_ID = simklclientid
        #https://api.simkl.com/oauth/pin?client_id=xxxxxxxxxxxx&redirect_uri=urn:ietf:wg:oauth:2.0:oob
        #https://api.simkl.com/oauth/pin/YYYYY?client_id=xxxxxxxxxxxx
		url = '?client_id=%s&redirect_uri=urn:ietf:wg:oauth:2.0:oob' % self.client_ID
		url = oauth_base_url + url
		response = session.get(url).json()
		line = '%s\n%s\n%s'
		if control.setting('dialogs.useumbrelladialog') == 'true':
			self.progressDialog = control.getProgressWindow(getLS(40346), sim_qr, 1)
			self.progressDialog.set_controls()
		else:
			self.progressDialog = control.progressDialog
			self.progressDialog.create(getLS(40346))
		self.progressDialog.update(-1, line % (getLS(32513) % (highlightColor, 'https://simkl.com/pin/'), getLS(32514) % (highlightColor,response['user_code']), getLS(40390)))
		self.auth_timeout = int(response['expires_in'])
		self.auth_step = int(response['interval'])
		self.device_code = response['device_code']
		self.user_code = response['user_code']        
		while self.secret == '':
			if self.progressDialog.iscanceled():
				self.progressDialog.close()
				break
			self.auth_loop(fromSettings=fromSettings)
		if self.secret: self.save_token(fromSettings=fromSettings)

	def save_token(self, fromSettings=0):
		try:
			self.token = self.secret
			control.sleep(500)
			control.setSetting('simkltoken', self.token)
			control.notification(message="Simkl Authorized", icon=simkl_icon)
			if not control.yesnoDialog('Do you want to set Simkl as your service for your watched and unwatched indicators?','','','Indicators', 'No', 'Yes'): return True, None
			control.homeWindow.setProperty('umbrella.updateSettings', 'false')
			control.setSetting('indicators.alt', '2')
			control.homeWindow.setProperty('umbrella.updateSettings', 'true')
			control.setSetting('indicators', 'Simkl')
			if fromSettings == 1:
				control.openSettings('9.0', 'plugin.video.umbrella')
			return True, None
		except:
			log_utils.error('Simkl Authorization Failed : ')
			if fromSettings == 1:
				control.openSettings('9.0', 'plugin.video.umbrella')
			return False, None

	def reset_authorization(self, fromSettings=0):
		try:
			control.setSetting('simkltoken', '')
			control.setSetting('simklusername', '')
			from resources.lib.database import simklsync
			clr_simklsync = {'bookmarks': True, 'movies_watchlist': True, 'shows_watchlist': True, 'watched': True, 'movies_history': True, 'shows_history': True}
			simklsync.delete_tables(clr_simklsync)
			if getSetting('indicators.alt') == '2':
				control.setSetting('indicators.alt', '0')
				control.setSetting('indicators', 'Local')
			if fromSettings == 1:
				control.openSettings('9.0', 'plugin.video.umbrella')
			control.dialog.ok(getLS(40342), getLS(32320))
		except: log_utils.error()

	def get_account_info(self):
		try:
			#https://api.simkl.com/users/settings
			url = "https://api.simkl.com/users/settings"
			headers['Authorization'] = 'Bearer %s' % getSetting('simkltoken')
			headers['simkl-api-key'] = simklclientid
			headers['User-Agent'] = 'Umbrella/%s' % control.addon('plugin.video.umbrella').getAddonInfo('version')
			response = session.post(url, headers=headers, timeout=20)
			if response.status_code == 200:
				response = response.json()
				from datetime import datetime
				try:
					account_info = response['user']
					username = account_info['name']
					joined = datetime.strptime(account_info['joined_at'], '%Y-%m-%dT%H:%M:%SZ').strftime('%m-%d-%Y %I:%M %p')
					heading = getLS(40342).upper()
					items = []
					items += ['Name: %s' % username]
					items += ['Joined: %s' % joined]
					return control.selectDialog(items, heading=heading)
				except: log_utils.error()
			else:
				log_utils.error()
				return
		except: log_utils.error()
def get_request(url):
	try:
		if not url.startswith(BASE_URL): url = urljoin(BASE_URL, url)
		if '?' not in url:
			url += '?client_id=%s' % simklclientid
		else:
			url += '&client_id=%s' % simklclientid
		headers['Authorization'] = 'Bearer %s' % getSetting('simkltoken')
		headers['simkl-api-key'] = simklclientid
		headers['User-Agent'] = 'Umbrella/%s' % control.addon('plugin.video.umbrella').getAddonInfo('version')
		try: response = session.get(url, headers=headers, timeout=20)
		except requests.exceptions.SSLError:
			response = session.get(url, headers=headers, verify=False)
	except requests.exceptions.ConnectionError:
		control.notification(message=40349)
		log_utils.error()
		return None
	try:
		if response.status_code in (200, 201): return response.json()
		elif response.status_code == 404:
			if getSetting('debug.level') == '1':
				log_utils.log('Simkl get_request() failed: (404:NOT FOUND) - URL: %s' % url, level=log_utils.LOGDEBUG)
			return '404:NOT FOUND'
		elif 'Retry-After' in response.headers: # API REQUESTS ARE BEING THROTTLED, INTRODUCE WAIT TIME (TMDb removed rate-limit on 12-6-20)
			throttleTime = response.headers['Retry-After']
			control.notification(message='SIMKL Throttling Applied, Sleeping for %s seconds' % throttleTime)
			control.sleep((int(throttleTime) + 1) * 1000)
			return get_request(url)
		else:
			if getSetting('debug.level') == '1':
				log_utils.log('SIMKL get_request() failed: URL: %s\n                       msg : SIMKL Response: %s' % (url, response.text), __name__, log_utils.LOGDEBUG)
			return None
	except:
		log_utils.error()
		return None

def getSimklAsJson(url, post=None, silent=False):
	try:
		from resources.lib.modules import simkl
		if post: r = simkl.post_request(url, data=post)
		else: r = get_request(url)
		if not r: return
		if '/sync/all-items/shows/watching' in url: return r['shows']
		r = r.json()
		return r
	except: log_utils.error()

def simkl_list(url):
	if not url: return
	url = url % simklclientid
	try:
		#result = cache.get(self.get_request, 96, url % self.API_key)
		result = get_request(url)
		if result is None: return
		items = result
	except: return
	simkllist = [] ; sortList = []
	next = ''
	for item in items:
		try:
			values = {}
			values['next'] = next 
			values['tmdb'] = str(item.get('ids').get('tmdb')) if item.get('ids').get('tmdb') else ''
			sortList.append(values['tmdb'])
			values['imdb'] = ''
			values['tvdb'] = ''
			values['metacache'] = False 
			simkllist.append(values)
		except:
			log_utils.error()
	return simkllist

def simklCompleted(url):
	if not url: return
	try:
		#result = cache.get(self.get_request, 96, url % self.API_key)
		result = get_request(url)
		if result is None: return
		items = result['movies']
	except: return
	simkllist = [] ; sortList = []
	next = ''
	for item in items:
		try:
			values = {}
			values['next'] = next 
			values['tmdb'] = str(item['movie'].get('ids').get('tmdb')) if item['movie'].get('ids').get('tmdb') else ''
			sortList.append(values['tmdb'])
			values['imdb'] = item['movie'].get('ids').get('imdb')
			values['tvdb'] = item['movie'].get('ids').get('tvdb')
			values['metacache'] = False 
			simkllist.append(values)
		except:
			log_utils.error()
	return simkllist

def simklPlantowatch(url):
	if not url: return
	try:
		#result = cache.get(self.get_request, 96, url % self.API_key)
		result = get_request(url)
		if result is None: return
		items = result['movies']
	except: return
	simkllist = [] ; sortList = []
	next = ''
	for item in items:
		try:
			values = {}
			values['next'] = next 
			values['tmdb'] = str(item['movie'].get('ids').get('tmdb')) if item['movie'].get('ids').get('tmdb') else ''
			sortList.append(values['tmdb'])
			values['imdb'] = item['movie'].get('ids').get('imdb')
			values['tvdb'] = item['movie'].get('ids').get('tvdb')
			values['metacache'] = False 
			simkllist.append(values)
		except:
			log_utils.error()
	return simkllist


def watch(content_type, name, imdb=None, tvdb=None, season=None, episode=None, refresh=True):
	control.busy()
	success = False
	if content_type == 'movie':
		success = markMovieAsWatched(imdb)
		if success: update_syncMovies(imdb)
	elif content_type == 'tvshow':
		success = markTVShowAsWatched(imdb, tvdb)
		if success: cachesyncTV(imdb, tvdb)
	elif content_type == 'season':
		success = markSeasonAsWatched(imdb, tvdb, season)
		if success: cachesyncTV(imdb, tvdb)
	elif content_type == 'episode':
		success = markEpisodeAsWatched(imdb, tvdb, season, episode)
		if success: cachesyncTV(imdb, tvdb)
	else: success = False
	control.hide()
	if refresh: control.refresh()
	control.trigger_widget_refresh()
	if season and not episode: name = '%s-Season%s...' % (name, season)
	if season and episode: name = '%s-S%sxE%02d...' % (name, season, int(episode))
	if getSetting('simkl.general.notifications') == 'true':
		if success is True: control.notification(title=32315, message=getLS(35502) % ('[COLOR %s]%s[/COLOR]' % (highlightColor, name)))
		else: control.notification(title=32315, message=getLS(35504) % ('[COLOR %s]%s[/COLOR]' % (highlightColor, name)))
	if not success: log_utils.log(getLS(35504) % name + ' : ids={imdb: %s, tvdb: %s}' % (imdb, tvdb), __name__, level=log_utils.LOGDEBUG)

def unwatch(content_type, name, imdb=None, tvdb=None, season=None, episode=None, refresh=True):
	control.busy()
	success = False
	if content_type == 'movie':
		success = markMovieAsNotWatched(imdb)
		update_syncMovies(imdb, remove_id=True)
	elif content_type == 'tvshow':
		success = markTVShowAsNotWatched(imdb, tvdb)
		cachesyncTV(imdb, tvdb) 
	elif content_type == 'season':
		success = markSeasonAsNotWatched(imdb, tvdb, season)
		cachesyncTV(imdb, tvdb)
	elif content_type == 'episode':
		success = markEpisodeAsNotWatched(imdb, tvdb, season, episode)
		cachesyncTV(imdb, tvdb)
	else: success = False
	control.hide()
	if refresh: control.refresh()
	control.trigger_widget_refresh()
	if season and not episode: name = '%s-Season%s...' % (name, season)
	if season and episode: name = '%s-S%sxE%02d...' % (name, season, int(episode))
	if getSetting('simkl.general.notifications') == 'true':
		if success is True: control.notification(title=32315, message=getLS(35503) % ('[COLOR %s]%s[/COLOR]' % (highlightColor, name)))
		else: control.notification(title=32315, message=getLS(35505) % ('[COLOR %s]%s[/COLOR]' % (highlightColor, name)))
	if not success: log_utils.log(getLS(35505) % name + ' : ids={imdb: %s, tvdb: %s}' % (imdb, tvdb), __name__, level=log_utils.LOGDEBUG)

def getSimKLCredentialsInfo():
	token = getSetting('simkltoken')
	if (token == ''): return False
	return True

def getSimKLIndicatorsInfo():
	indicators = getSetting('indicators.alt')
	indicators = True if indicators == '2' else False
	return indicators

def post_request(url, data=None):
	if type(data) == dict or type(data) == list: data = json.dumps(data)
	if not url.startswith(BASE_URL): url = urljoin(BASE_URL, url)
	if '?' not in url:
		url += '?client_id=%s' % simklclientid
	else:
		url += '&client_id=%s' % simklclientid
	headers['Authorization'] = 'Bearer %s' % getSetting('simkltoken')
	headers['simkl-api-key'] = simklclientid
	headers['User-Agent'] = 'Umbrella/%s' % control.addon('plugin.video.umbrella').getAddonInfo('version')
	log_utils.log('SIMKL post_request() URL: %s' % url, __name__, log_utils.LOGDEBUG)
	try:
		response = session.post(url, data=data, headers=headers, timeout=20)
	except requests.exceptions.ConnectionError:
		control.notification(message=40349)
		log_utils.error()
		return None
	try:
		if response.status_code in (200, 201): 
			return response.json()
		# elif response.status_code == 400:
		# 	control.sleep(1000)
		# 	from resources.lib.modules import simkl
		# 	return simkl.post_request(url, data=data)
		else:
			if getSetting('debug.level') == '1':
				log_utils.log('SIMKL post_request() failed: URL: %s\n                       msg : SIMKL Response: %s' % (url, response.text), __name__, log_utils.LOGDEBUG)
			return None
	except:
		log_utils.error()
		return None

def markMovieAsWatched(imdb):
	try:
		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		data = {"movies": [{"watched_at": timestamp,"ids": {"imdb": imdb}}]}
		from resources.lib.modules import simkl
		result = simkl.post_request('/sync/history', data)
		result = result['added']['movies'] != 0
		if getSetting('debug.level') == '1':
			log_utils.log('SimKL markMovieAsWatched IMDB: %s Result: %s' % (imdb, result), level=log_utils.LOGDEBUG)
		return result
	except: log_utils.error()

def markMovieAsNotWatched(imdb):
	try:
		from resources.lib.modules import simkl
		result = simkl.post_request('/sync/history/remove', {"movies": [{"ids": {"imdb": imdb}}]})
		return result['deleted']['movies'] != 0
	except: log_utils.error()

def markTVShowAsWatched(imdb, tvdb):
	try:
		from resources.lib.modules import simkl
		#result = simkl.post_request('/sync/history', {"shows": [{"ids": {"imdb": imdb, "tvdb": tvdb}}]})
		result = simkl.post_request('/sync/add-to-list', {"shows": [{"to": "completed", "ids": {"imdb": imdb, "tvdb": tvdb}}]})
		if result['added']['shows'] == 0 and tvdb: # fail, trying again with tvdb as fallback
			control.sleep(1000) # POST 1 call per sec rate-limit
			result = simkl.post_request('/sync/history', {"shows": [{"ids": {"tvdb": tvdb}}]})
			if not result: return False
		return len(result.get('added').get('shows', 0)) != 0
	except: log_utils.error()

def markTVShowAsNotWatched(imdb, tvdb):
	try:
		from resources.lib.modules import simkl
		result = simkl.post_request('/sync/history/remove', {"shows": [{"ids": {"imdb": imdb, "tvdb": tvdb}}]})
		if not result: return False
		if result['deleted']['shows'] == 0 and tvdb: # fail, trying again with tvdb as fallback
			control.sleep(1000) # POST 1 call per sec rate-limit
			result = simkl.post_request('/sync/history/remove', {"shows": [{"ids": {"tvdb": tvdb}}]})
			if not result: return False
		return result['deleted']['shows'] != 0
	except: log_utils.error()

def markSeasonAsWatched(imdb, tvdb, season):
	try:
		from resources.lib.modules import simkl
		season = int('%01d' % int(season))
		result = simkl.post_request('/sync/history', {"shows": [{"seasons": [{"number": season}], "ids": {"imdb": imdb, "tvdb": tvdb}}]})
		if not result: return False
		if result['added']['episodes'] == 0 and tvdb: # # fail, trying again with tvdb as fallback
			control.sleep(1000) # POST 1 call per sec rate-limit
			result = simkl.post_request('/sync/history', {"shows": [{"seasons": [{"number": season}], "ids": {"tvdb": tvdb}}]})
			if not result: return False
		return result['added']['shows'] != 0
	except: log_utils.error()

def markSeasonAsNotWatched(imdb, tvdb, season):
	try:
		from resources.lib.modules import simkl
		season = int('%01d' % int(season))
		result = simkl.post_request('/sync/history/remove', {"shows": [{"seasons": [{"number": season}], "ids": {"imdb": imdb, "tvdb": tvdb}}]})
		if not result: return False
		if result['deleted']['episodes'] == 0 and tvdb: # fail, trying again with tvdb as fallback
			control.sleep(1000) # POST 1 call per sec rate-limit
			result = SIMKL.post_request('/sync/history/remove', {"shows": [{"seasons": [{"number": season}], "ids": {"tvdb": tvdb}}]})
			if not result: return False
		return result['deleted']['shows'] != 0
	except: log_utils.error()

def markEpisodeAsWatched(imdb, tvdb, season, episode):
	try:
		season, episode = int('%01d' % int(season)), int('%01d' % int(episode)) #same
		from resources.lib.modules import simkl
		result = simkl.post_request('/sync/history', {"shows": [{"seasons": [{"episodes": [{"number": episode}], "number": season}], "ids": {"imdb": imdb, "tvdb": tvdb}}]})
		if not result: result = False
		if result['added']['episodes'] == 0 and tvdb:
			control.sleep(1000)
			result = simkl.post_request('/sync/history', {"shows": [{"seasons": [{"episodes": [{"number": episode}], "number": season}], "ids": {"imdb": tvdb}}]})
			if not result: result = False
			result = result['added']['episodes'] !=0
		else:
			result = result['added']['episodes'] !=0
		if getSetting('debug.level') == '1':
			log_utils.log('SimKL markEpisodeAsWatched IMDB: %s TVDB: %s Season: %s Episode: %s Result: %s' % (imdb, tvdb, season, episode, result), level=log_utils.LOGDEBUG)
		return result
	except: log_utils.error()

def markEpisodeAsNotWatched(imdb, tvdb, season, episode):

	try:
		season, episode = int('%01d' % int(season)), int('%01d' % int(episode))
		from resources.lib.modules import simkl
		result = simkl.post_request('/sync/history/remove', {"shows": [{"seasons": [{"episodes": [{"number": episode}], "number": season}], "ids": {"imdb": imdb, "tvdb": tvdb}}]})
		if not result: return False
		if result['deleted']['episodes'] == 0 and tvdb:
			control.sleep(1000)
			result = simkl.post_request('/sync/history/remove', {"shows": [{"seasons": [{"episodes": [{"number": episode}], "number": season}], "ids": {"imdb": tvdb}}]})
			if not result: return False
		return result['deleted']['episodes'] !=0
	except: log_utils.error()

def seasonCount(imdb, tvdb): # return counts for all seasons of a show from simklsync.db
	try:
		counts = simklsync.cache_existing(syncSeasons, imdb, tvdb)
		if not counts: return
		return counts[1]
	except:
		log_utils.error()
		return None

def timeoutsyncSeasons(imdb, tvdb):
	try:
		timeout = simklsync.timeout(syncSeasons, imdb, tvdb, returnNone=True) # returnNone must be named arg or will end up considered part of "*args"
		return timeout
	except: log_utils.error()

def update_syncMovies(imdb, remove_id=False):
	try:
		indicators = simklsync.cache_existing(syncMovies)
		if remove_id: indicators.remove(imdb)
		else: indicators.append(imdb)
		key = simklsync._hash_function(syncMovies, ())
		simklsync.cache_insert(key, repr(indicators))
	except: log_utils.error()

def cachesyncMovies(timeout=0):
	indicators = simklsync.get(syncMovies, timeout)
	#if getSetting('sync.watched.library') == 'true':
		#syncMoviesLibrary(indicators)
	return indicators

def syncMovies():
	try:
		from resources.lib.modules import simkl
		if not getSimKLCredentialsInfo(): return
		from resources.lib.modules import simkl
		indicators = simkl.post_request('/sync/all-items/movies/') #indicators may be different with simkl
		if not indicators: return None
		indicators = indicators['movies']
		indicators = [i['movie']['ids'] for i in indicators]
		indicators = [str(i['imdb']) for i in indicators if 'imdb' in i]
		return indicators
	except: log_utils.error()

def cachesyncTV(imdb, tvdb):  # Sync full watched shows then sync imdb_id "season indicators" and "season counts"
	try:
		with ThreadPoolExecutor() as executor:
			# Submit tasks to the thread pool
			executor.submit(cachesyncTVShows)
			executor.submit(cachesyncSeasons, imdb, tvdb)
		simklsync.insert_syncSeasons_at()
	except Exception as e:
		log_utils.error(f"Error in cachesyncTV: {e}")

def cachesyncTVShows(timeout=0):
	try:
		indicators = simklsync.get(syncTVShows, timeout)
		return indicators
	except:
		indicators = ''
		return indicators

def syncTVShows(): # sync all watched shows ex. [({'imdb': 'tt12571834', 'tvdb': '384435', 'tmdb': '105161', 'trakt': '163639'}, 16, [(1, 16)]), ({'imdb': 'tt11761194', 'tvdb': '377593', 'tmdb': '119845', 'trakt': '158621'}, 2, [(1, 1), (1, 2)])]
	try:
		from resources.lib.modules import simkl
		if not getSimKLCredentialsInfo():
			return
		data = simkl.post_request('/sync/all-items/shows/?extended=full', None)
		if not data:
			return None

		indicators = [
			(
				{
					'imdb': show['show']['ids'].get('imdb', None),
					'tvdb': str(show['show']['ids'].get('tvdb', '')),
					'tmdb': str(show['show']['ids'].get('tmdb', '')),
					'simkl': str(show['show']['ids'].get('simkl', '')),
				},
				show['total_episodes_count'] - show['not_aired_episodes_count'],
				[
					(season['number'], episode['number'])
					for season in show.get('seasons', [])  # Default to an empty list if 'seasons' is missing
					for episode in season.get('episodes', [])  # Default to an empty list if 'episodes' is missing
				],
			)
			for show in data.get('shows', [])  # Default to an empty list if 'shows' is missing
			if show.get('status') == 'watching'  # Use .get() to prevent KeyError
		]

		indicators = [(i[0], int(i[1]), i[2]) for i in indicators]
		return indicators
	except: log_utils.error()

def chunked_iterator(iterable, size):
    iterator = iter(iterable)
    while chunk := list(islice(iterator, size)):
        yield chunk

def batchCacheSyncSeason(data):
    #Process all items in data in chunks because simkl api had limit of 100 items per request
    extended_param = 'full,specials' if getSetting('tv.specials') == 'true' else 'full'

    def process_chunk(chunk):
        #Handles API request and season syncing for a batch.
        formatted_data = [show for show in chunk]  # Format each batch
        results = post_request(f'/sync/watched?extended={extended_param}', data=formatted_data)
        if not results:
            return
        with ThreadPoolExecutor() as executor:
            for show in chunk:
                imdb = show.get('imdb')
                tvdb = show.get('tvdb')
                simkl_id = show.get('simkl')
                executor.submit(cachesyncSeasons, imdb, tvdb, simkl_id, 0, results)

    with ThreadPoolExecutor() as executor:
        for chunk in chunked_iterator(data, 100):  # Process 100 items at a time
            executor.submit(process_chunk, chunk)

def cachesyncSeasons(imdb, tvdb, simkl_id=None, timeout=0, data=None):
	try:
		imdb = imdb or ''
		tvdb = tvdb or ''
		indicators = simklsync.get(syncSeasons, timeout, imdb, tvdb, simkl_id, data) # named var and data not included in function md5_hash
		return indicators
	except: log_utils.error()

def syncSeasons(imdb, tvdb, simkl_id=None, data=None): # season indicators and counts for watched shows ex. [['1', '2', '3'], {1: {'total': 8, 'watched': 8, 'unwatched': 0}, 2: {'total': 10, 'watched': 10, 'unwatched': 0}}]
	indicators_and_counts = []
	try:
		if all(not value for value in (imdb, tvdb, simkl_id)): return
		from resources.lib.modules import simkl
		if not getSimKLCredentialsInfo() : return
		log_utils.log('Trying Sync Seasons: imdb=%s, tvdb=%s, simkl=%s' % (imdb, tvdb, simkl_id), level=log_utils.LOGDEBUG)
		id = imdb or simkl_id
		if not id and tvdb:
			log_utils.log('syncSeasons missing imdb_id, pulling simkl id from watched shows database', level=log_utils.LOGDEBUG)
			db_watched = simklsync.cache_existing(syncTVShows) # pull simkl ID from db because imdb ID is missing
			ids = [i[0] for i in db_watched if i[0].get('tvdb') == tvdb]
			id = ids[0].get('simkl', '') if ids[0].get('simkl') else ''
			if not id:
				log_utils.log("syncSeasons FAILED: missing required imdb and simkl ID's for tvdb=%s" % tvdb, level=log_utils.LOGDEBUG)
				return
		if not data:
			if getSetting('tv.specials') == 'true':
				data = [{"imdb": id}]
				#/sync/watched?extended=counters
				from resources.lib.modules import simkl
				results = simkl.post_request('/sync/watched?extended=full,specials', data=data)
			else:
				
				data = [{"imdb": id}]
				from resources.lib.modules import simkl
				results = simkl.post_request('/sync/watched?extended=full', data=data)
			if not results: return
		else:
			results = data
		show_data = results
		for show in show_data:
			if show.get('imdb') != imdb:
				continue
			seasons = show.get('seasons', [])
        
			indicators = [(season['number'], [ep['watched'] for ep in season['episodes']]) for season in seasons]
			indicators = ['%01d' % int(season[0]) for season in indicators if all(season[1])]
			indicators_and_counts.append(indicators)

			counts = {
				season['number']: {
					'total': season['episodes_aired'],
					'watched': season['episodes_watched'],
					'unwatched': season['episodes_aired'] - season['episodes_watched']
				}
				for season in seasons
			}

			indicators_and_counts.append(counts)
		
		# indicators = [(i['number'], [x['completed'] for x in i['episodes']]) for i in seasons]
		# indicators = ['%01d' % int(i[0]) for i in indicators if False not in i[1]]
		# indicators_and_counts.append(indicators)
		# counts = {season['number']: {'total': season['aired'], 'watched': season['completed'], 'unwatched': season['aired'] - season['completed']} for season in seasons}
		# indicators_and_counts.append(counts)
		return indicators_and_counts
	except:
		log_utils.error()
		return None

def timeoutsyncTVShows():
	timeout = simklsync.timeout(syncTVShows)
	return timeout

def getProgressActivity(activities=None):
	try:
		if activities: i = activities
		else: i = getSimklAsJson('/sync/last_activities')
		if not i: return 0
		i = json.loads(i)
		activity = []
		activity.append(i['tv_shows']['watching'])
		if len(activity) == 0: return 0
		activity = [datetime.strptime(dt, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%dT%H:%M:%S.000Z") for dt in activity] if activity else []
		activity = [int(cleandate.iso_2_utc(i)) for i in activity]
		activity = sorted(activity, key=int)[-1]
		return activity
	except: 
		log_utils.error() 
		return 0

def getWatchListedActivity(activities=None):
	try:
		if activities: i = activities
		else: i = getSimklAsJson('/sync/last_activities')
		if not i: return 0
		i = json.loads(i)
		activity = []
		activity.append(i['movies']['plantowatch'])
		activity.append(i['tv_shows']['plantowatch'])
		if len(activity) == 0: return 0
		activity = [datetime.strptime(dt, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%dT%H:%M:%S.000Z") for dt in activity]
		activity = [int(cleandate.iso_2_utc(i)) for i in activity]
		activity = sorted(activity, key=int)[-1]
		return activity
	except: 
		return 0

def getHistoryListedActivity(activities=None):
	try:
		if activities: i = activities
		else: i = getSimklAsJson('/sync/last_activities')
		if not i: return 0
		i = json.loads(i)
		activity = []
		activity.append(i['movies']['completed'])
		activity.append(i['tv_shows']['completed'])
		if len(activity) == 0: return 0
		activity = [datetime.strptime(dt, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%dT%H:%M:%S.000Z") for dt in activity]
		activity = [int(cleandate.iso_2_utc(i)) for i in activity]
		activity = sorted(activity, key=int)[-1]
		return activity
	except: 
		return 0

def getEpisodesWatchedActivity(activities=None):
	try:
		if activities: i = activities
		else: i = getSimklAsJson('/sync/last_activities')
		if not i: return 0
		i = json.loads(i)
		activity = []
		activity.append(i['tv_shows']['all'])
		if len(activity) == 0: return 0
		activity = [datetime.strptime(dt, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%dT%H:%M:%S.000Z") for dt in activity]
		activity = [int(cleandate.iso_2_utc(i)) for i in activity]
		activity = sorted(activity, key=int)[-1]
		return activity
	except: 
		log_utils.error() 
		return 0

def getMoviesWatchedActivity(activities=None):
	try:
		if activities: i = activities
		else: i = getSimklAsJson('/sync/last_activities')
		if not i: return 0
		i = json.loads(i)
		activity = []
		activity.append(i['movies']['completed'])
		if len(activity) == 0: return 0
		activity = [datetime.strptime(dt, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%dT%H:%M:%S.000Z") for dt in activity]
		activity = [int(cleandate.iso_2_utc(i)) for i in activity]
		activity = sorted(activity, key=int)[-1]
		return activity
	except: 
		log_utils.error() 
		return 0

def sync_watchedProgress(activities=None, forced=False):
	try:
		from resources.lib.menus import episodes
		direct = getSetting('simkl.directProgress.scrape') == 'true'
		url = '/sync/all-items/shows/watching?extended=full'
		progressActivity = getProgressActivity(activities)
		local_listCache = cache.timeout(episodes.Episodes().simkl_progress_list, url, direct)
		if forced or (progressActivity > local_listCache) or progressActivity == 0:
			cache.get(episodes.Episodes().simkl_progress_list, 0, url, direct)
			if forced: log_utils.log('Forced - SimKl Progress List Sync Complete', __name__, log_utils.LOGDEBUG)
			else:
				log_utils.log('SimKl Progress List Sync Update...(local db latest "list_cached_at" = %s, simkl api latest "progress_activity" = %s)' % \
									(str(local_listCache), str(progressActivity)), __name__, log_utils.LOGDEBUG)
	except: log_utils.error()

def sync_watch_list(activities=None, forced=False):
	try:
		link = '/sync/all-items/%s/plantowatch'
		if forced:
			items = get_request(link % 'movies')
			items = items.get('movies', None)
			if items: simklsync.insert_watch_list(items, 'movies_watchlist')
			items = get_request(link % 'shows')
			items = items.get('shows', None)
			if items: simklsync.insert_watch_list(items, 'shows_watchlist')
		else:
			db_last_watchList = simklsync.last_sync('last_watchlisted_at')
			watchListActivity = getWatchListedActivity(activities)
			if (watchListActivity - db_last_watchList >= 60) or watchListActivity == 0: # do not sync unless 1 min difference or more
				log_utils.log('Simkl (watchlist) Sync Update...(local db latest "watchlist_at" = %s, simkl api latest "watchlisted_at" = %s)' % \
									(str(db_last_watchList), str(watchListActivity)), __name__, log_utils.LOGINFO)
				clr_simklsync = {'bookmarks': False, 'movies_watchlist': True, 'shows_watchlist': True, 'watched': False, 'movies_history': False, 'shows_history': False}
				simklsync.delete_tables(clr_simklsync)
				items = get_request(link % 'movies')
				items = items.get('movies',None)
				if items: simklsync.insert_watch_list(items, 'movies_watchlist')
				items = get_request(link % 'shows')
				items = items.get('shows', None)
				if items: simklsync.insert_watch_list(items, 'shows_watchlist')
	except: log_utils.error()

def sync_history(activities=None, forced=False):
	try:
		link = '/sync/all-items/%s/completed'
		if forced:
			items = get_request(link % 'movies')
			items = items.get('movies', None)
			if items: simklsync.insert_history_list(items, 'movies_history')
			items = get_request(link % 'shows')
			items = items.get('shows', None)
			if items: simklsync.insert_history_list(items, 'shows_history')
		else:
			db_last_historyList = simklsync.last_sync('last_history_at')
			historyListActivity = getHistoryListedActivity(activities)
			if (historyListActivity - db_last_historyList >= 60) or historyListActivity == 0: # do not sync unless 1 min difference or more
				log_utils.log('Simkl Watched History (watchlist) Sync Update...(local db latest "watchlist_at" = %s, simkl api latest "watchlisted_at" = %s)' % \
									(str(db_last_historyList), str(historyListActivity)), __name__, log_utils.LOGINFO)
				clr_simklsync = {'bookmarks': False, 'movies_watchlist': False, 'shows_watchlist': False, 'watched': False, 'movies_history': True, 'shows_history': True}
				simklsync.delete_tables(clr_simklsync)
				items = get_request(link % 'movies')
				items = items.get('movies', None)
				if items: simklsync.insert_history_list(items, 'movies_history')
				items = get_request(link % 'shows')
				items = items.get('shows')
				if items:  simklsync.insert_history_list(items, 'shows_history')
	except: log_utils.error()


def service_syncSeasons(): # season indicators and counts for watched shows ex. [['1', '2', '3'], {1: {'total': 8, 'watched': 8, 'unwatched': 0}, 2: {'total': 10, 'watched': 10, 'unwatched': 0}}]
	try:
		log_utils.log('Service - Simkl Watched Shows Season Sync...', __name__, log_utils.LOGDEBUG)
		indicators = simklsync.cache_existing(syncTVShows) # use cached data from service cachesyncTVShows() just written fresh
		threads = []
		batch = []
		for indicator in indicators:
			imdb = indicator[0].get('imdb', '') if indicator[0].get('imdb') else ''
			tvdb = str(indicator[0].get('tvdb', '')) if indicator[0].get('tvdb') else ''
			simkl_id = str(indicator[0].get('simkl', '')) if indicator[0].get('simkl') else ''
			batch.append({'imdb': imdb, 'tvdb': tvdb})
			#threads.append(Thread(target=cachesyncSeasons, args=(imdb, tvdb, simkl_id))) # season indicators and counts for an entire show
		#[i.start() for i in threads]
		#[i.join() for i in threads]
		#cachesyncSeasons('tt2152112', None, None)
		batchCacheSyncSeason(batch)
	except: log_utils.error()

def sync_watched(activities=None, forced=False): # writes to simkl.db as of 1-19-2022
	try:
		if forced:
			cachesyncMovies()
			cachesyncTVShows()
			control.sleep(5000)
			service_syncSeasons() # syncs all watched shows season indicators and counts
			simklsync.insert_syncSeasons_at()
		else:
			moviesWatchedActivity = getMoviesWatchedActivity(activities)
			db_movies_last_watched = timeoutsyncMovies()
			if (moviesWatchedActivity - db_movies_last_watched >= 30) or moviesWatchedActivity == 0: # do not sync unless 30secs more to allow for variation between simkl post and local db update.
				log_utils.log('Simkl Watched Movie Sync Update...(local db latest "watched_at" = %s, simkl api latest "watched_at" = %s)' % \
								(str(db_movies_last_watched), str(moviesWatchedActivity)), __name__, log_utils.LOGDEBUG)
				cachesyncMovies()
			episodesWatchedActivity = getEpisodesWatchedActivity(activities)
			if episodesWatchedActivity == 0:
				episodesWatchedActivity = 10000000
			db_last_syncTVShows = timeoutsyncTVShows()
			db_last_syncSeasons = simklsync.last_sync('last_syncSeasons_at')
			if any(episodesWatchedActivity > value for value in (db_last_syncTVShows, db_last_syncSeasons)):
				log_utils.log('Simkl Watched Shows Sync Update...(local db latest "watched_at" = %s, simkl api latest "watched_at" = %s)' % \
								(str(min(db_last_syncTVShows, db_last_syncSeasons)), str(episodesWatchedActivity)), __name__, log_utils.LOGDEBUG)
				cachesyncTVShows()
				control.sleep(5000)
				service_syncSeasons() # syncs all watched shows season indicators and counts
				simklsync.insert_syncSeasons_at()
	except: log_utils.error()

def timeoutsyncMovies():
	timeout = simklsync.timeout(syncMovies)
	return timeout

# Watching - In Progress
# Completed - History
# Plan to Watch - watchlist

def force_simklSync():
	if not control.yesnoDialog(getLS(32056), '', ''): return
	control.busy()

	# wipe all tables and start fresh
	clr_simkl = {'bookmarks': True, 'movies_watchlist': True, 'shows_watchlist': True, 'watched': True, 'movies_history': True, 'shows_history': True}
	simklsync.delete_tables(clr_simkl)

	sync_watch_list(forced=True) # writes to simkl.db as of 2-4-2025
	sync_history(forced=True) #history can be a large table better to cache
	sync_watched(forced=True) 
	sync_watchedProgress(forced=True) # simkl progress sync
	control.hide()
	control.notification(message='Forced Simkl Sync Complete')