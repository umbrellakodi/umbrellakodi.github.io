# -*- coding: utf-8 -*-

import sys
from xbmc import getInfoLabel, executebuiltin
try: #Py2
	from urlparse import parse_qsl
	from urllib import quote_plus
except ImportError: #Py3
	from urllib.parse import parse_qsl, quote_plus

if __name__ == '__main__':
	item = sys.listitem
	# message = item.getLabel()
	path = item.getPath()

	plugin = 'plugin://plugin.video.umbrella/'
	args = path.split(plugin, 1)
	params = dict(parse_qsl(args[1].replace('?', '')))
	name = params['tvshowtitle'] if 'tvshowtitle' in params else params['title']
	sysname = quote_plus(name)

	imdb = params.get('imdb', '')
	tvdb = params.get('tvdb', '')
	tmdb = params.get('tmdb', '')
	# Episodes and seasons must reach the manager as such, not as the whole show.
	season = params.get('season', '')
	episode = params.get('episode', '')
	tvshow = 'tvshow' if getInfoLabel('ListItem.DBType') == 'tvshow' else ''

	playcount = getInfoLabel('ListItem.Playcount')
	watched = (int(playcount) >= 1) if playcount else False

	path = 'RunPlugin(%s?action=tools_mdbWatchlist&name=%s&imdb=%s&tvdb=%s&tmdb=%s&season=%s&episode=%s&watched=%s&tvshow=%s)' % (
				plugin, sysname, imdb, tvdb, tmdb, season, episode, watched, tvshow)
	executebuiltin(path)