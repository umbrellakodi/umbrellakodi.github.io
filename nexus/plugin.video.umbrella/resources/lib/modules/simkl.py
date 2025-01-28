# -*- coding: utf-8 -*-
"""
	Umbrella Add-on (added by Umbrella Dev 12/23/22)
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from resources.lib.modules import control
from resources.lib.database import simklsync
from resources.lib.modules import log_utils
from datetime import datetime
#from threading import Thread
from concurrent.futures import ThreadPoolExecutor

getLS = control.lang
getSetting = control.setting
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
			if fromSettings == 1:
				control.openSettings('9.0', 'plugin.video.umbrella')
				control.notification(message="Simkl Authorized", icon=simkl_icon)
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
			if fromSettings == 1:
				control.openSettings('9.0', 'plugin.video.umbrella')
			control.dialog.ok(getLS(40343), getLS(32320))

		except: log_utils.error()

	def getSimKLCredentialsInfo():
		token = getSetting('simkltoken')
		if (token == ''): return False
		return True

	def get_request(self, url):
		try:
			try: response = session.get(url, timeout=20)
			except requests.exceptions.SSLError:
				response = session.get(url, verify=False)
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
				return self.get_request(url)
			else:
				if getSetting('debug.level') == '1':
					log_utils.log('SIMKL get_request() failed: URL: %s\n                       msg : SIMKL Response: %s' % (url, response.text), __name__, log_utils.LOGDEBUG)
				return None
		except:
			log_utils.error()
			return None

	def post_request(url, data=None):
		url  = 'https://api.simkl.com%s' % url
		headers['Authorization'] = 'Bearer %s' % getSetting('simkltoken')
		headers['simkl-api-key'] = simklclientid
		
		try:
			response = session.post(url, data=data, headers=headers, timeout=20)
		except requests.exceptions.ConnectionError:
			control.notification(message=40349)
			log_utils.error()
			return None
		try:
			if response.status_code in (200, 201): return response.json()
			else:
				if getSetting('debug.level') == '1':
					log_utils.log('SIMKL post_request() failed: URL: %s\n                       msg : SIMKL Response: %s' % (url, response.text), __name__, log_utils.LOGDEBUG)
				return None
		except:
			log_utils.error()
			return None

	def simkl_list(self, url):
		if not url: return
		url = url % simklclientid
		try:
			#result = cache.get(self.get_request, 96, url % self.API_key)
			result = self.get_request(url)
			if result is None: return
			items = result
		except: return
		self.list = [] ; sortList = []
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
				self.list.append(values)
			except:
				log_utils.error()
		return self.list

	def watch(content_type, name, imdb=None, tvdb=None, season=None, episode=None, refresh=True):
		control.busy()
		success = False
		if content_type == 'movie':
			success = markMovieAsWatched(imdb)
			if success: update_syncMovies(imdb)
		elif content_type == 'tvshow':
			success = markTVShowAsWatched(imdb, tvdb)
			#if success: cachesyncTV(imdb, tvdb)
		elif content_type == 'season':
			success = markSeasonAsWatched(imdb, tvdb, season)
			#if success: cachesyncTV(imdb, tvdb)
		elif content_type == 'episode':
			success = markEpisodeAsWatched(imdb, tvdb, season, episode)
			#if success: cachesyncTV(imdb, tvdb)
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
			#cachesyncTV(imdb, tvdb) new methods need to be written to sync simkl
		elif content_type == 'season':
			success = markSeasonAsNotWatched(imdb, tvdb, season)
			#cachesyncTV(imdb, tvdb) new methods need to be written to sync simkl
		elif content_type == 'episode':
			success = markEpisodeAsNotWatched(imdb, tvdb, season, episode)
			#cachesyncTV(imdb, tvdb) new methods need to be written to sync simkl
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

def markMovieAsWatched(imdb):
	try:
		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		data = {"movies": [{"watched_at": timestamp,"ids": {"imdb": imdb}}]}
		result = SIMKL.post_request('/sync/history', data)
		result = result['added']['movies'] != 0
		if getSetting('debug.level') == '1':
			log_utils.log('SimKL markMovieAsWatched IMDB: %s Result: %s' % (imdb, result), level=log_utils.LOGDEBUG)
		return result
	except: log_utils.error()

def markMovieAsNotWatched(imdb):
	try:
		result = SIMKL.post_request('/sync/history/remove', {"movies": [{"ids": {"imdb": imdb}}]})
		return result['deleted']['movies'] != 0
	except: log_utils.error()

def markTVShowAsWatched(imdb, tvdb):
	try:
		result = SIMKL.post_request('/sync/history', {"shows": [{"ids": {"imdb": imdb, "tvdb": tvdb}}]})
		if result['added']['episodes'] == 0 and tvdb: # fail, trying again with tvdb as fallback
			control.sleep(1000) # POST 1 call per sec rate-limit
			result = SIMKL.post_request('/sync/history', {"shows": [{"ids": {"tvdb": tvdb}}]})
			if not result: return False
		return result['added']['shows'] != 0
	except: log_utils.error()

def markTVShowAsNotWatched(imdb, tvdb):
	try:
		result = SIMKL.post_request('/sync/history/remove', {"shows": [{"ids": {"imdb": imdb, "tvdb": tvdb}}]})
		if not result: return False
		if result['deleted']['episodes'] == 0 and tvdb: # fail, trying again with tvdb as fallback
			control.sleep(1000) # POST 1 call per sec rate-limit
			result = SIMKL.post_request('/sync/history/remove', {"shows": [{"ids": {"tvdb": tvdb}}]})
			if not result: return False
		return result['deleted']['shows'] != 0
	except: log_utils.error()

def markSeasonAsWatched(imdb, tvdb, season):
	try:
		season = int('%01d' % int(season))
		result = SIMKL.post_request('/sync/history', {"shows": [{"seasons": [{"number": season}], "ids": {"imdb": imdb, "tvdb": tvdb}}]})
		if not result: return False
		if result['added']['episodes'] == 0 and tvdb: # # fail, trying again with tvdb as fallback
			control.sleep(1000) # POST 1 call per sec rate-limit
			result = SIMKL.post_request('/sync/history', {"shows": [{"seasons": [{"number": season}], "ids": {"tvdb": tvdb}}]})
			if not result: return False
		return result['added']['shows'] != 0
	except: log_utils.error()

def markSeasonAsNotWatched(imdb, tvdb, season):
	try:
		season = int('%01d' % int(season))
		result = SIMKL.post_request('/sync/history/remove', {"shows": [{"seasons": [{"number": season}], "ids": {"imdb": imdb, "tvdb": tvdb}}]})
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
		result = SIMKL.post_request('/sync/history', {"shows": [{"seasons": [{"episodes": [{"number": episode}], "number": season}], "ids": {"imdb": imdb, "tvdb": tvdb}}]})
		if not result: result = False
		if result['added']['episodes'] == 0 and tvdb:
			control.sleep(1000)
			result = SIMKL.post_request('/sync/history', {"shows": [{"seasons": [{"episodes": [{"number": episode}], "number": season}], "ids": {"imdb": tvdb}}]})
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
		result = SIMKL.post_request('/sync/history/remove', {"shows": [{"seasons": [{"episodes": [{"number": episode}], "number": season}], "ids": {"imdb": imdb, "tvdb": tvdb}}]})
		if not result: return False
		if result['deleted']['episodes'] == 0 and tvdb:
			control.sleep(1000)
			result = SIMKL.post_request('/sync/history/remove', {"shows": [{"seasons": [{"episodes": [{"number": episode}], "number": season}], "ids": {"imdb": tvdb}}]})
			if not result: return False
		return result['deleted']['episodes'] !=0
	except: log_utils.error()

def update_syncMovies(imdb, remove_id=False):
	try:
		indicators = simklsync.cache_existing(syncMovies)
		if remove_id: indicators.remove(imdb)
		else: indicators.append(imdb)
		key = simklsync._hash_function(syncMovies, ())
		simklsync.cache_insert(key, repr(indicators))
	except: log_utils.error()

def syncMovies():
	try:
		if not SIMKL.getSimKLCredentialsInfo(): return
		indicators = SIMKL.post_request('/sync/all-items/movies/') #indicators may be different with simkl
		if not indicators: return None
		indicators = [i['movie']['ids'] for i in indicators]
		indicators = [str(i['imdb']) for i in indicators if 'imdb' in i]
		return indicators
	except: log_utils.error()

# def cachesyncTV(imdb, tvdb): # sync full watched shows then sync imdb_id "season indicators" and "season counts"
# 	try:
# 		threads = [Thread(target=cachesyncTVShows), Thread(target=cachesyncSeasons, args=(imdb, tvdb))]
# 		[i.start() for i in threads]
# 		[i.join() for i in threads]
# 		simklsync.insert_syncSeasons_at()
# 	except: log_utils.error()

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
		if not SIMKL.getSimKLCredentialsInfo(): return
		data = SIMKL.post_request('/sync/all-items/shows/?extended=full', None)
		if not data: return None
# /shows/ID/progress/watched  endpoint only accepts imdb or trakt ID so write all ID's
		#indicators = [({'imdb': i['show']['ids']['imdb'], 'tvdb': str(i['show']['ids']['tvdb']), 'tmdb': str(i['show']['ids']['tmdb']), 'trakt': str(i['show']['ids']['trakt'])}, \
		#									i['show']['aired_episodes'], sum([[(s['number'], e['number']) for e in s['episodes'] if i['reset_at'] is None or e['last_watched_at'] > i['reset_at']] for s in i['seasons']], [])) for i in indicators]
		#indicators = [({'imdb': i['show']['ids']['imdb'],'tvdb': str(i['show']['ids']['tvdb']),'tmdb': str(i['show']['ids']['tmdb']),'simkl': str(i['show']['ids']['simkl'])},(int(i['total_episodes_count'])-int(i['not_aired_episodes_count'])),sum([[(s['number'], e['number']) for e in s['episodes']]for s in (i.get('seasons'), 0)])], [])) for i in indicators['shows']]
		
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
					for season in show['seasons']
					for episode in season.get('episodes', [])
				],
			)
			for show in data['shows']
			if show['status'] == 'watching'
		]
		
		indicators = [(i[0], int(i[1]), i[2]) for i in indicators]
		log_utils.log('SimKL Watched Shows Indicators: %s' % indicators, level=log_utils.LOGDEBUG)
		return indicators
	except: log_utils.error()

def cachesyncSeasons(imdb, tvdb, simkl=None, timeout=0):
	try:
		imdb = imdb or ''
		tvdb = tvdb or ''
		indicators = simklsync.get(syncSeasons, timeout, imdb, tvdb, simkl=simkl) # named var not included in function md5_hash
		return indicators
	except: log_utils.error()

def syncSeasons(imdb, tvdb, simkl=None): # season indicators and counts for watched shows ex. [['1', '2', '3'], {1: {'total': 8, 'watched': 8, 'unwatched': 0}, 2: {'total': 10, 'watched': 10, 'unwatched': 0}}]
	pass # code needs to be written for this.
	return None