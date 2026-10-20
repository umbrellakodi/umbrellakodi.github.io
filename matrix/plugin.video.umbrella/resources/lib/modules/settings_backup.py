"""Portable preference backups. Account settings are never read or applied.

This explicit list is intentional: new settings must be reviewed before they can
be exported. Do not replace it with a credential-name blacklist or prefix match.
"""
import json
import math
from datetime import datetime
from xml.etree import ElementTree


ALLOWED_SETTINGS = frozenset("""
appearance.1
icon.logos
index.labels
highlight.color
api.language
mpa.country
mpa.prefix
useLanguageforOriginal
useOriginCountries
originCountry
searchmovie.indexer
searchtv.indexer
page.item.limit
search.page.limit
fanart
enable.fanarttv
prefer.tmdbArt
tmdb.imageResolutions
prefer.fanarttv
hidecinema
hidecinema.rollback
movie.unaired.identify
enable.umbrellahidewatched
notification.sound
general.checkAddonUpdates
umbrella.autostart
enable.containerTitles
favourite.refreshwidgets
favourite.refreshcontainer
movies.showyear
sort.movies.tmdblist.type
sort.movies.tmdblist.order
sort.movies.type
sort.movies.order
sort.collections.type
sort.collections.order
sort.movies.plantowatch.type
sort.movies.plantowatch.order
sort.movies.watchlist.type
sort.movies.watchlist.order
sort.movies.favourites.type
sort.movies.favourites.order
sort.movies.history.type
sort.movies.history.order
dialogs.useumbrelladialog
dialogs.lightordarkmode
dialogs.customcolor
dialogs.usecolortitle
dialogs.titlebar.color
dialogs.button.color
flatten.tvshows
flatten.desc
tv.specials
tvshows.show.year
showunaired
unaired.identify
multi.unwatched.enabled
tvshows.calendar.extended
tvshows.progress.watched
tvshows.episodecount
sort.shows.tmdblist.type
sort.shows.tmdblist.order
sort.shows.type
sort.shows.order
sort.shows.plantowatch.type
sort.shows.plantowatch.order
sort.shows.watchlist.type
sort.shows.watchlist.order
sort.progress.type
sort.progress.order
sort.watched.type
sort.watched.order
sort.shows.favourite.type
sort.shows.favourite.order
tvshows.air.enabled
tvshows.air.zone
tvshows.air.location
tvshows.air.format
tvshows.air.day
tvshows.air.time
tvshows.air.bold
bookmarks
bookmarks.auto
skip.intro.enable
skip.recap.enable
skip.intro.auto
skip.recap.auto
crefresh
markwatched.percent
enable.playnext
umbrella.multiSeason
playnext.theme
playnext.background.color
enable.playnext.theme
playnext.method
playnext.segment.fallback
playnext.time
playnext.percent
playnext.min.seconds
playnext.sub.backupmethod
playnext.sub.seconds
playnext.sub.percent
playnext.default.action
playnext.hidebutton
stillwatching.count
stillwatching.default.action
source.prioritize.hdrdv
source.prioritize.dolbyvisionfirst
source.prioritize.av1
source.prioritize.hevc
hosts.quality
source.checkReboots
source.filtermbysize
source.movie.linespeed
source.min.moviesize
source.max.moviesize
source.filterebysize
source.min.epsize
source.max.epsize
source.episode.linespeed
remove.duplicates
remove.duplicates.logging
remove.duplicates.popup
torrent.remove.uncached
sources.nocachepopup
sources.retryall
remove.dolby.vision
remove.hdr
remove.hevc
remove.av1
remove.atvp
remove.avc
remove.aiupscaled.sources
remove.divx
remove.mp4
remove.mpeg
remove.wmv
remove.cam.sources
remove.sd.sources
remove.3D.sources
torrent.min.seeders
remove.audio.opus
remove.audio.dd
remove.audio.ddplus
remove.audio.atmos
remove.audio.ddtruehd
remove.audio.dts
remove.audio.dtshd
remove.audio.dtshdma
remove.audio.dtsx
remove.audio.aac
remove.audio.mp3
remove.channel.2ch
remove.channel.6ch
remove.channel.7ch
remove.channel.8ch
play.mode
play.mode.movie
play.mode.tv
rescrape.default
rescrape.default2
scrapers.prioritize
cf.disable
imdb.Moviemeta.check
imdb.Movietitle.check
imdb.Movieyear.check
imdb.Showmeta.check
imdb.Showtitle.check
imdb.Showyear.check
sources.useTitleSubs
progress.dialog
sources.dialog.fanartBG
scrapers.timeout
scraper.dialog.color
terminate.onCloud.sources
preemptive.termination.movie
preemptive.limit.movie
preemptive.res.movie
preemptive.termination.tv
preemptive.limit.tv
preemptive.res.tv
sources.select.fanartBG
sources.highlightmethod
sources.highlight.color
sources.real-debrid.color
sources.alldebrid.color
sources.offcloud.color
sources.premiumize.me.color
sources.torbox.color
sources.easynews.color
sources.plexshare.color
sources.gdrive.color
sources.filepursuit.color
sources.usecoloricons
sources.sort.order
source.prefer.smaller
cloud.sources.first
uncached.seeder.sort
autoplay.sd
sources.useonlyone
sources.backbutton
scrobble.notify
trakt.markwatched
simkl.markwatched
mdblist.markwatched
custom.markwatched
floppy.markwatched
scrob.markwatched
punchplay.markwatched
services.directProgress.scrape
services.progressFlatten
services.paginate.lists
services.general.notifications
simkl.progressFlatten
simkl.progress.showunaired
simkl.UpcomingProgress.prependDate
simkl.service.syncInterval
simkl.progress.episodes
simkl.progress.shows
background.service.syncInterval
trakt.server.notifications
trakt.useLanguage
trakt.rating
trakt.progress.showunaired
trakt.UpcomingProgress.prependDate
trakt.collection.hideWatched
trakt.lists.showowner
trakt.progress.episodes
trakt.progress.shows
mdblist.service.syncInterval
mdblist.progressFlatten
mdblist.progress.showunaired
mdblist.UpcomingProgress.prependDate
mdblist.progress.episodes
mdblist.progress.shows
floppy.readonly
floppy.service.syncInterval
floppy.progress.showunaired
floppy.UpcomingProgress.prependDate
scrob.service.syncInterval
punchplay.service.syncInterval
punchplay.progress.showunaired
alldebrid.enable
alldebridexpirynotice
alldebrid.priority
alldebrid.saveToCloud
ad_cloud.enabled
ad_cloud.ignore.m2ts
alldebrid.server.notifications
offcloud.enable
offcloud.priority
oc_cloud.enabled
premiumize.enable
premiumizeexpirynotice
premiumize.priority
premiumize.saveToCloud
pm_cloud.enabled
pm_cloud.ignore.m2ts
premiumize.server.notifications
realdebrid.alternateapi
realdebrid.enable
realdebridexpirynotice
realdebrid.priority
realdebrid.saveToCloud
realdebrid.filter.filename
rd_cloud.enabled
rd_cloud.ignore.m2ts
realdebrid.server.notifications
torbox.enable
torbox.priority
torbox.saveToCloud
tb_cloud.enabled
provider.external.enabled
plexshare.enable
plexshare.priority
easynews.enable
easynews.moderation
easynews.title.chk
easynews.seekable
easynews.priority
filepursuit.enable
filepursuit.priority
gdrive.enable
gdrive.title.chk
gdrive.priority
tmdb.paginate.lists
library.general.notification
library.service.update
library.import.hours
library.service.notification
library.autoimportlists
library.update
library.check
library.importdelay
library.include_specials
library.include_unknown
library.include_unaired
library.strm.use_tmdbhelper
downloads
downloads.file.format
torrent.cacheprogress.dialog
simkl.general.notifications
simkl.directProgress.scrape
simkl.paginate.lists
trakt.general.notifications
trakt.directProgress.scrape
trakt.progressFlatten
trakt.paginate.lists
trakt.HiddenManager.hideWatched
mdblist.general.notifications
mdblist.paginate.lists
mdblist.directProgress.scrape
custom.general.notifications
custom.directProgress.scrape
custom.paginate.lists
floppy.general.notifications
floppy.paginate.lists
floppy.directProgress.scrape
scrob.general.notifications
scrob.paginate.lists
scrob.directProgress.scrape
punchplay.general.notifications
punchplay.paginate.lists
punchplay.directProgress.scrape
subtitles
subtitles.notification
subtitles.prefer.embedded
subtitles.prefer.hearing_impaired
subtitles.prefer.forced
subtitles.utf
subtitles.lang.1
subtitles.lang.2
cache.tmdblist
cache.tmdbcollection
cache.tmdbrecentday
cache.tmdbrecentweek
cache.traktunfinished
cache.traktprogress
cache.trakthistory
cache.traktpopular
cache.trakttrending
cache.traktother
cache.traktuserlist
cache.mdblist
cache.simkl
cache.providers
context.umbrella.addtoLibrary
context.umbrella.addtoFavourite
context.umbrella.artworkCustomize
context.umbrella.libMdblistManager
context.umbrella.addLibtoFavourite
context.umbrella.playTrailer
context.umbrella.playTrailerSelect
context.umbrella.traktManager
context.umbrella.mdblistManager
context.umbrella.simklManager
context.umbrella.customManager
context.umbrella.floppyManager
context.umbrella.scrobManager
context.umbrella.punchplayManager
context.umbrella.tmdbListManager
context.umbrella.tmdbWatchlist
context.umbrella.clearProviders
context.umbrella.clearBookmark
context.umbrella.rescrape
context.umbrella.rescrape2
context.umbrella.rescrape3
context.umbrella.playFromHere
context.umbrella.autoPlay
context.umbrella.sourceSelect
context.umbrella.findSimilar
context.umbrella.browseSeries
context.umbrella.browseEpisodes
enable.umbrellawidgetcontext
context.useUmbrellaContext
""".split())

FORMAT = 'umbrella-preferences'
VERSION = 1
MAX_BACKUP_BYTES = 1024 * 1024


def preference_types(schema):
    root = ElementTree.fromstring(schema)
    return {node.get('id'): node.get('type') for node in root.iter('setting')
            if node.get('id') in ALLOWED_SETTINGS and node.get('type') in ('boolean', 'integer', 'number', 'string')}


def serialize_preferences(get_setting, types):
    values = {key: get_setting(key) for key in sorted(types) if key in ALLOWED_SETTINGS}
    return json.dumps({'format': FORMAT, 'version': VERSION, 'settings': values}, indent=2, ensure_ascii=False)


def parse_preferences(content, types):
    if len(content.encode('utf-8')) > MAX_BACKUP_BYTES:
        raise ValueError('Backup is too large')
    data = json.loads(content)
    if not isinstance(data, dict) or data.get('format') != FORMAT or type(data.get('version')) is not int or data['version'] != VERSION:
        raise ValueError('Unsupported preference backup')
    values = data.get('settings')
    if not isinstance(values, dict):
        raise ValueError('Invalid preference settings')
    result = {}
    for key, value in values.items():
        # Ignore account fields even if someone inserts them into a backup.
        if key not in ALLOWED_SETTINGS or key not in types: continue
        if not isinstance(value, str): raise ValueError('Invalid preference value')
        kind = types[key]
        if kind == 'boolean' and value not in ('true', 'false'):
            raise ValueError('Invalid boolean preference')
        if kind == 'integer': int(value)
        if kind == 'number' and not math.isfinite(float(value)):
            raise ValueError('Invalid numeric preference')
        result[key] = value
    if not result: raise ValueError('No supported preferences in backup')
    return result


def apply_preferences(values, get_setting, set_setting):
    if any(key not in ALLOWED_SETTINGS for key in values):
        raise ValueError('Unsupported preference')
    previous = {key: get_setting(key) for key in values}
    try:
        for key, value in values.items():
            if set_setting(key, value) is False: raise RuntimeError('Preference write failed')
    except Exception:
        for key, value in previous.items():
            set_setting(key, value)
        raise


def _read(control, path):
    handle = control.openFile(path)
    try:
        if handle.size() > MAX_BACKUP_BYTES: raise ValueError('Backup is too large')
        return handle.read()
    finally:
        handle.close()


def _write(control, path, content):
    handle = control.openFile(path, 'w')
    try:
        if handle.write(content) is False: raise IOError('Backup write failed')
    finally:
        handle.close()
    if _read(control, path) != content: raise IOError('Backup verification failed')


def _types(control):
    return preference_types(_read(control, control.SETTINGS_PATH))


def export_settings():
    from resources.lib.modules import control
    try:
        folder = control.dialog.browse(0, control.lang(40830), 'files')
        if not folder: return
        name = 'Umbrella-preferences-%s.json' % datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        path = control.joinPath(folder, name)
        _write(control, path, serialize_preferences(control.addon().getSetting, _types(control)))
        control.dialog.ok(control.lang(40830), control.lang(40832))
    except Exception:
        control.dialog.ok(control.lang(40830), control.lang(40835))


def import_settings():
    from resources.lib.modules import control
    try:
        path = control.dialog.browse(1, control.lang(40831), 'files', '.json')
        if not path: return
        types = _types(control)
        values = parse_preferences(_read(control, path), types)
        if not control.dialog.yesno(control.lang(40831), control.lang(40833)): return
        addon = control.addon()
        rollback = control.joinPath(control.dataPath, 'preferences-before-import.json')
        _write(control, rollback, serialize_preferences(addon.getSetting, types))
        apply_preferences(values, addon.getSetting, addon.setSetting)
        control.homeWindow.clearProperty('umbrella_settings')
        control.trigger_widget_refresh(force=True)
        control.dialog.ok(control.lang(40831), control.lang(40834))
    except Exception:
        control.dialog.ok(control.lang(40831), control.lang(40835))
