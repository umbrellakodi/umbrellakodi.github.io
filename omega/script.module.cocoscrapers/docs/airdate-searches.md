# Air-date episode searches

All 25 TV-capable providers now accept filenames identified by the selected
episode's exact air date, in addition to their existing numbered matching.
No provider API change is required in consuming addons.

Text-search providers perform their original numbered search followed by a
YYYY.MM.DD search, preserving pagination and provider-specific parsing:
1337x, BitSearch, Kickass, Knaben, LimeTorrents, Nyaa, Pirate Bay,
Prowlarr (torrent and usenet), Rutor, Torlock, TorrentDownload, TorrentGalaxy,
TorrentProject2, and Torrentz2. Rutor now supports single TV episodes in
addition to its existing movies and packs.

ID-based providers keep their existing upstream requests and accept matching
date-named releases in the returned results: AIOStreams, Bitmagnet, Comet,
DMM, MediaFusion, Meteor, Torrentio, TorrentsDB, Torz, and Zilean. EZTV now
uses its IMDb-based JSON API instead of website searches (see below). These APIs
must return the release for the requested show/episode or season; local
matching cannot recover a result omitted by an upstream service. No unsupported
text-search or air-date API endpoints are invented. YTS is movie-only.

The date comes from `data['premiered']` and must be a valid YYYY-MM-DD or
YYYY.MM.DD string. Missing or invalid dates retain numbered-only behavior.
Results must match the show title (or alias) and either the numbered identifier
or the exact date; dot, hyphen, and space date separators are recognized.
Duplicate hashes are merged across the two text searches. The caller's metadata
is not mutated, and a failed date search retains numbered results. The extra
search pass can increase duration, especially when providers time out. Pack
searches and movie queries retain their existing behavior.

## Compatibility with external addons

The external provider interface is unchanged: `sources(data, hostDict)` and
`sources_packs(data, hostDict, search_series=False, total_seasons=None,
bypass_filter=False)`. No additional positional argument is required. EZTV now requires the existing
`imdb` metadata field to contain a valid show IMDb ID; other providers retain
their existing metadata requirements.
The returned source dictionaries keep the existing schema. The private
`_coco_airdate_query` value is created only in a copy of the caller's data.

Without `premiered`, or with a null, empty, or invalid date, all providers keep
numbered-only episode behavior. Addons already supplying a valid episode date
receive date-named matches too. Their own playback resolvers may need date
matching to play those additional results; ordinary numbered results remain
available. The optional date arguments added to shared helpers are trailing
arguments with defaults, so existing positional calls remain valid. The new
Umbrella resolver parameters belong to Umbrella, not the CocoScrapers API.

Regression tests cover absent/null/empty/invalid dates across all 25 TV
providers, all provider entry-point signatures, legacy positional helper calls,
and the result schema of EZTV and Knaben. These are offline checks, not an
end-to-end certification of every third-party addon.

## EZTV API replacement

The existing `eztv` provider and `provider.eztv` setting now use
`https://eztvx.to/api/get-torrents` exclusively. Website search/parsing has been
removed. The API is documented at https://eztvx.to/api/ and accepts the show's
numeric IMDb ID plus `limit` and `page`. Both `tt1234567` and `1234567` metadata
values are accepted. Missing/invalid IDs return no EZTV results without querying
the global torrent feed. Umbrella already supplies the IMDb ID.

The provider requests up to 100 items per page, within a 12-second request
budget and the documented 100-page cap. Results fetched before a subsequent
failure are retained. Very large catalogs or slow responses can exhaust this
budget before older releases are reached. Returned files go through existing
title, numbered/air-date, language, undesirable, and season-pack matching.
Series packs remain unsupported. No extra provider setting was introduced.

Eight API regression checks cover pagination, missing IDs, legacy numbered
matching, exact air dates, duplicate pages, malformed payloads, failures,
request limits, and season packs. All 18 CocoScrapers checks pass. A live API
probe returned HTTP 403 in this environment, so live provider verification is
still outstanding.

## Umbrella integration

The installed Umbrella already includes `premiered` in the episode data in
both `getSources_silent` and `getSources_dialog` in
`resources/lib/modules/sources.py`. No search-payload change is needed.
Use the selected episode's air date, not the show's original premiere date.

Umbrella playback support has also been implemented in the sibling
`plugin.video.umbrella` project:

- `Sources.sourcesResolve` passes the selected episode's `premiered` (or
  `firstaired`) to the debrid resolver. Existing show/episode coordinates stay
  unchanged, including episode-mapping support.
- Real-Debrid, Premiumize, AllDebrid, Offcloud, TorBox, and EasyDebrid accept an
  optional trailing date argument and forward it to file matching. Existing
  callers remain compatible.
- `seas_ep_filter` validates dates and accepts exact date-named files, including
  its `split=True` path used for extras filtering. Numbered releases continue
  to use numbered matching. A dated parent folder cannot select an unrelated
  file, and wrong-day files are rejected.
- Real-Debrid, Premiumize, AllDebrid, Offcloud, and TorBox cloud scrapers add the
  episode date to their query patterns and reject conflicting dated files.
- Subtitle lookup and subtitle-based playback timing receive the current
  episode's date. Pack browsing also passes the selected episode's date.

Seven new Umbrella regression checks cover matching, cloud query construction,
resolver forwarding, metadata wiring, and mocked Offcloud file selection.
The existing subtitle and source-preparation suites also pass (20 Umbrella
checks total), alongside the seven CocoScrapers checks.

After installing the scraper update, use Umbrella's rescrape action to avoid
reusing cached provider results. Live provider and debrid playback validation
is still required; the regression suites use offline fixtures and mocks.

## Offline checks

Run `python -m unittest discover -s tests -v` from the addon directory.
The suite exercises production matching functions, query generation for all 14
text providers, and result handling for all 10 ID providers, with Kodi
dependencies and HTTP results stubbed. It also checks invalid dates, wrong-day
releases, aliases, duplicates, ordinary episodes/movies, and date-query failure.
