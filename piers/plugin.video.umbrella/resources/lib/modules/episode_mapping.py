"""Explicit anthology identities. Never infer a story from a shared IMDb/TVDB ID.

Catalog checked 2026-09-28: TMDB and Trakt split Monster into four shows;
SIMKL 1446614 / TVDB 389492 combine them. Specials have no verified mapping.
"""

MONSTER = {'113988': (1, 10), '225634': (2, 9), '286801': (3, 8), '299939': (4, 8)}
MONSTER_TVDB = '389492'
MONSTER_IMDB = 'tt13207736'
MONSTER_SIMKL = '1446614'
STORY_TITLES = {'113988': 'DAHMER - Monster: The Jeffrey Dahmer Story',
                '225634': 'Monsters: The Lyle and Erik Menendez Story',
                '286801': 'Monster: The Ed Gein Story',
                '299939': 'Monster: The Lizzie Borden Story'}


def supported(tmdb):
    return str(tmdb) in MONSTER


def coordinates(provider, tmdb, season=1):
    """Return unambiguous provider IDs and season; reject unmapped specials."""
    story = MONSTER[str(tmdb)]
    if int(1 if season in (None, '') else season) != 1:
        raise ValueError('This Monster season has no verified tracking mapping')
    if provider == 'simkl':
        return {'simkl': int(MONSTER_SIMKL), 'tvdb': int(MONSTER_TVDB)}, story[0]
    return {'tmdb': int(tmdb)}, 1


def history_payload(provider, tmdb, season=None, episode=None):
    ids, sn = coordinates(provider, tmdb, season)
    # Always scope a show-wide action to its story, never the whole anthology.
    section = {'number': sn}
    if episode is not None:
        en = int(episode)
        if not 1 <= en <= MONSTER[str(tmdb)][1]:
            raise ValueError('Episode outside the mapped Monster story')
        section['episodes'] = [{'number': en}]
    return {'shows': [{'ids': ids, 'seasons': [section]}]}


def scrobble_payload(body, provider, tmdb):
    if not supported(tmdb) or 'show' not in body:
        return body
    result = dict(body)
    episode = dict(body['episode'])
    ids, episode['season'] = coordinates(provider, tmdb, episode['season'])
    history_payload(provider, tmdb, body['episode']['season'], episode['number'])
    result.update(show={'ids': ids}, episode=episode)
    return result


def bookmark(cursor, provider, tmdb, season, episode, ret_type):
    """Read only the exact story's bookmark, never a shared-ID fallback."""
    try:
        ids, sn = coordinates(provider, tmdb, season)
    except ValueError:
        return '0'
    if provider == 'simkl':
        match = cursor.execute("SELECT * FROM bookmarks WHERE (tvdb=? OR imdb=? OR tmdb=?) AND season=? AND episode=?",
                               (MONSTER_TVDB, MONSTER_IMDB, '113988', str(sn), str(episode))).fetchone()
    else:
        match = cursor.execute('SELECT * FROM bookmarks WHERE tmdb=? AND season=? AND episode=?',
                               (str(tmdb), str(sn), str(episode))).fetchone()
    if not match: return '0'
    return (match[0], match[2]) if ret_type == 'resume_info' else match[12]


def combined(ids):
    return (str(ids.get('tvdb')) == MONSTER_TVDB or
            str(ids.get('simkl')) == MONSTER_SIMKL or ids.get('imdb') == MONSTER_IMDB)


def watched_episodes(indicators, provider, tmdb):
    """Project raw cached provider history onto one TMDB story, without I/O."""
    sn = MONSTER[str(tmdb)][0] if provider == 'simkl' else 1
    found = set()
    for ids, total, episodes in indicators or []:
        matches = combined(ids) if provider == 'simkl' else str(ids.get('tmdb')) == str(tmdb)
        if not matches:
            continue
        if isinstance(episodes, dict):
            for first, last in episodes.get(sn, episodes.get(str(sn), [])):
                found.update(range(int(first), int(last) + 1))
        else:
            found.update(int(e) for s, e in episodes if int(s) == sn)
    return {e for e in found if 1 <= e <= MONSTER[str(tmdb)][1]}


def season_indicators(indicators, provider, tmdb):
    total = MONSTER[str(tmdb)][1]
    watched = len(watched_episodes(indicators, provider, tmdb))
    return [['1'] if watched == total else [],
            {1: {'total': total, 'watched': watched, 'unwatched': total - watched}}]


def display_episode(row):
    """Translate a SIMKL bookmark/calendar episode to its TMDB story."""
    if not combined(row):
        return row
    try:
        tmdb = next(k for k, v in MONSTER.items() if v[0] == int(row['season']))
    except (StopIteration, KeyError, TypeError, ValueError):
        return row
    result = dict(row, tmdb=tmdb, season=1, imdb='', tvdb='', tvshowtitle=STORY_TITLES[tmdb])
    return result


def progress_stories(item):
    """Split SIMKL progress into independent stories, preserving watched gaps."""
    if not combined(item.get('show', {}).get('ids', {})):
        return None
    result = []
    last_started = 0
    for section in item.get('seasons', []):
        try:
            tmdb = next(k for k, v in MONSTER.items() if v[0] == int(section['number']))
        except (StopIteration, KeyError, TypeError, ValueError):
            continue
        watched = {int(e['number']) for e in section.get('episodes', []) if e.get('number')}
        if watched: last_started = max(last_started, int(section['number']))
        missing = next((e for e in range(1, MONSTER[tmdb][1] + 1) if e not in watched), None)
        if not watched or missing is None:
            continue
        result.append({'tmdb': tmdb, 'imdb': '', 'tvdb': '', 'snum': 1, 'enum': missing - 1,
                       'tvshowtitle': STORY_TITLES[tmdb],
                       'lastplayed': item.get('last_watched_at', ''), 'duration': '', 'anthology_mapping': 1})
    # A combined provider can report "watching" between stories. Continue at
    # the next story instead of trying to find season 2 on the Dahmer TMDB entry.
    if not result and 0 < last_started < 4:
        tmdb = next(k for k, v in MONSTER.items() if v[0] == last_started + 1)
        result.append({'tmdb': tmdb, 'imdb': '', 'tvdb': '', 'snum': 1, 'enum': 0,
                       'tvshowtitle': STORY_TITLES[tmdb], 'lastplayed': item.get('last_watched_at', ''), 'duration': '', 'anthology_mapping': 1})
    return result


def display_shows(rows):
    """Expand SIMKL show lists before TMDB enrichment/pagination."""
    result = []
    for row in rows or []:
        if not combined(row) and str(row.get('tmdb')) != '113988':
            result.append(row)
            continue
        for tmdb in MONSTER:
            result.append(dict(row, tmdb=tmdb, imdb='', tvdb='', title=STORY_TITLES[tmdb],
                               tvshowtitle=STORY_TITLES[tmdb], metacache=False))
    return result


def scrape_variants(tmdb, data):
    """Search both release-numbering conventions without changing playback meta."""
    if not supported(tmdb) or str(data.get('season')) != '1':
        return [data]
    season = MONSTER[str(tmdb)][0]
    # Generic Monster + shared IMDb finds anthology-numbered releases. Keep the
    # story name as an alias; the split query must not use generic/shared IDs.
    anthology = dict(data, imdb=MONSTER_IMDB, tvdb=MONSTER_TVDB, season=str(season),
                     tvshowtitle='Monster', year='2022', aliases=[{'title': STORY_TITLES[str(tmdb)], 'country': 'us'}],
                     _scrape_tmdb=str(tmdb), _scrape_convention='anthology', _scrape_total_seasons=4)
    split = dict(data, imdb='', tvdb='', tvshowtitle=STORY_TITLES[str(tmdb)],
                 _scrape_tmdb=str(tmdb), _scrape_convention='split', _scrape_total_seasons=1)
    # Do not allow shared aliases such as "Monster" to match Dahmer S01 when
    # looking for Menendez S01. Its explicit full title is the safe alternative.
    split['aliases'] = []
    return [anthology, split]


def tag_sources(sources, data):
    if not data.get('_scrape_tmdb'):
        return sources
    return [dict(row, scrape_tmdb=data['_scrape_tmdb'], scrape_season=str(data['season']),
                 scrape_episode=str(data['episode']), scrape_convention=data['_scrape_convention']) for row in sources]


def source_coordinates(item, meta, season, episode):
    """Use the selected release's numbering when choosing a file in a pack."""
    if item.get('scrape_tmdb') and str(item['scrape_tmdb']) == str((meta or {}).get('tmdb')):
        return item.get('scrape_season', season), str(episode)
    return season, episode


def preresolved_matches(imdb, tmdb, season, episode, saved_imdb, saved_tmdb, saved_season, saved_episode):
    same_show = str(tmdb) == saved_tmdb if saved_tmdb else bool(imdb) and str(imdb) == saved_imdb
    # Old pre-resolved URLs cannot disambiguate these split shows by IMDb.
    if supported(tmdb) and not saved_tmdb: return False
    return same_show and str(season) == saved_season and str(episode) == saved_episode
