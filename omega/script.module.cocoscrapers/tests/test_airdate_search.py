"""Offline regression checks; Kodi and provider HTTP calls are stubbed."""
import ast
import importlib.util
import re
import json
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / 'lib/cocoscrapers'


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Exercise the production matching functions without importing the Kodi runtime.
utils = types.ModuleType('source_utils')
utils.re = re
utils.cleantitle = load_file('cleantitle', ROOT / 'modules/cleantitle.py')
tree = ast.parse((ROOT / 'modules/source_utils.py').read_text(encoding='utf-8'))
names = {'aliases_to_array', 'check_title', 'episode_airdate', 'check_episode_title', 'info_from_name', 'airdate_sources', 'episode_identifier'}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[]), 'source_utils.py', 'exec'), utils.__dict__)
utils.clean_name = lambda name: name.replace(' ', '.')
utils.get_undesirables = lambda: []
utils.check_foreign_audio = lambda: False
utils.remove_lang = lambda *args: False
utils.get_release_quality = lambda *args: ('1080p', [])
utils.convert_size = utils._size = lambda value: (1, '1 GB')
utils.scraper_error = lambda *args: None


class AirdateTests(unittest.TestCase):
    def test_dates(self):
        for value in ('2026-10-20', '2026.10.20'):
            self.assertEqual(utils.episode_airdate({'premiered': value}), '2026.10.20')
        for value in (None, '', '0', '2026', '2026-02-30', '2026-1-2', 20261020):
            self.assertIsNone(utils.episode_airdate({'premiered': value}))
        self.assertIsNone(utils.episode_airdate({}))

    def test_matching(self):
        def match(name, date='2026.10.20', aliases=[]):
            return utils.check_episode_title('The Daily Show', aliases, name, 'S31E123', '1996', date)
        self.assertEqual(match('The.Daily.Show.S31E123.1080p'), 'S31E123')
        for separator in ('.', '-', ' '):
            self.assertEqual(match('The.Daily.Show.2026%s10%s20.1080p' % (separator, separator)), '2026.10.20')
        for name in ('Other.Show.2026.10.20.1080p', 'The.Daily.Show.2026.10.21.1080p', 'The.Daily.Show.2026.10.200.1080p', 'The.Daily.Show.S31E124.1080p'):
            self.assertIsNone(match(name))
        self.assertIsNone(match('The.Daily.Show.2026.10.20.1080p', None))
        self.assertEqual(match('Daily.Show.2026.10.20.1080p', aliases=[{'title': 'Daily Show'}]), '2026.10.20')

    def provider(self, provider, data, releases, fail_date=False):
        client = types.ModuleType('client')
        urls = []
        def request(url, **kwargs):
            urls.append(url)
            if fail_date and '2026.10.20' in url:
                raise RuntimeError('date query failed')
            if provider == 'eztv':
                return json.dumps({'imdb_id': '1234567', 'torrents_count': len(releases), 'torrents': [dict(hash=h, filename=name, seeds=10, size_bytes=1000000000) for h, name in releases]})
            return 'response'
        client.request = request
        client.replaceHTMLCodes = lambda value: value
        client.parseDOM = lambda *args: [
            '<td class="x">x</td><td class="x">x</td><td class="x"><a href="magnet:?xt=urn:btih:%s" title="%s Torrent: Magnet Link">magnet:</a></td><td class="x">1 GB</td><td class="x">x</td><td class="x">10</td>' % (h, name)
            for h, name in releases]
        modules = types.ModuleType('cocoscrapers.modules')
        modules.client = modules.coco_client = client
        modules.source_utils = modules.coco_compat = utils
        with patch.dict('sys.modules', {'cocoscrapers': types.ModuleType('cocoscrapers'), 'cocoscrapers.modules': modules}):
            scraper = load_file(provider, ROOT / ('sources_cocoscrapers/torrents/%s.py' % provider)).source()
        if provider == 'knaben':
            def get_sources(url, files):
                try:
                    request(url)
                except RuntimeError:
                    return
                files.extend({'hash': h, 'title': name, 'seeders': 10, 'bytes': 1000000000} for h, name in releases)
            scraper.get_sources = get_sources
        return scraper.sources(data, {}), urls

    def test_providers(self):
        data = dict(tvshowtitle='The Daily Show', title='Guest', year='1996', season='31', episode='123', aliases=[], imdb='tt1234567', premiered='2026-10-20')
        releases = [('a' * 40, 'The.Daily.Show.S31E123.1080p'), ('b' * 40, 'The.Daily.Show.2026.10.20.1080p'), ('c' * 40, 'The.Daily.Show.2026.10.21.1080p')]
        for provider in ('eztv', 'knaben'):
            with self.subTest(provider=provider):
                results, urls = self.provider(provider, data, releases)
                self.assertEqual(len(urls), 1 if provider == 'eztv' else 2)
                if provider != 'eztv':
                    self.assertIn('S31E123', urls[0])
                    self.assertIn('2026.10.20', urls[1])
                self.assertEqual({r['hash'] for r in results}, {'a' * 40, 'b' * 40})
                self.assertEqual(len(results), 2)  # Deduplicate repeated HTTP results.
                results, urls = self.provider(provider, dict(data, premiered='bad'), releases)
                self.assertEqual(len(urls), 1)
                self.assertEqual([r['hash'] for r in results], ['a' * 40])
                results, urls = self.provider(provider, data, releases[:1], fail_date=True)
                self.assertEqual([r['hash'] for r in results], ['a' * 40])

    def test_movie_search_unchanged(self):
        data = dict(title='Example', year='2026', aliases=[], premiered='2026-10-20')
        results, urls = self.provider('knaben', data, [('a' * 40, 'Example.2026.1080p')])
        self.assertEqual(len(urls), 1)
        self.assertEqual(len(results), 1)
        self.assertIn('3000000', urls[0])


TEXT_PROVIDERS = {
    '1337x', 'bitsearch', 'kickass2', 'knaben', 'limetorrents',
    'nyaa', 'piratebay', 'prowlarr', 'rutor', 'torlock', 'torrentdownload',
    'torrentgalaxy', 'torrentproject2', 'torrentz2',
}
ID_PROVIDERS = {
    'aiostreams', 'bitmagnet', 'comet', 'dmm', 'mediafusion', 'meteor',
    'torrentio', 'torrentsdb', 'torz', 'zilean',
}


class AllProviderTests(unittest.TestCase):
    data = dict(tvshowtitle='The Daily Show', title='Guest', year='1996',
                season='31', episode='123', imdb='tt1234567', aliases=[],
                premiered='2026-10-20')

    def test_all_text_provider_queries(self):
        from urllib.parse import unquote_plus
        class Thread:
            def __init__(self, target, *args):
                self.target, self.args = target, args
            def start(self): self.target(*self.args)
            def join(self): pass
        utils.Thread = Thread
        for provider in sorted(TEXT_PROVIDERS):
            with self.subTest(provider=provider):
                urls = []
                def request(*args, **kwargs):
                    url = args[-1]
                    urls.append(unquote_plus(url + ' ' + str(kwargs.get('params', ''))))
                    return types.SimpleNamespace(text='', json=lambda: [])
                client = types.SimpleNamespace(randomagent=lambda: 'test',
                    request=lambda *args, **kwargs: (request(*args, **kwargs) and ''),
                    session=types.SimpleNamespace(request=request), parseDOM=lambda *args, **kwargs: [])
                control = types.ModuleType('cocoscrapers.modules.control')
                control.setting = lambda *args: 'test'
                control.addonInfo = lambda *args: 'test'
                modules = types.ModuleType('cocoscrapers.modules')
                modules.client = modules.coco_client = client
                modules.source_utils = modules.coco_compat = utils
                modules.workers = types.SimpleNamespace(Thread=Thread)
                modules.log_utils = types.SimpleNamespace(log=lambda *args, **kwargs: None)
                modules.cfscrape = types.SimpleNamespace(create_scraper=lambda: types.SimpleNamespace(get=request))
                with patch.dict('sys.modules', {
                    'cocoscrapers': types.ModuleType('cocoscrapers'),
                    'cocoscrapers.modules': modules,
                    'cocoscrapers.modules.control': control,
                    'requests': types.SimpleNamespace(get=request),
                }):
                    cls = load_file(provider, ROOT / ('sources_cocoscrapers/torrents/%s.py' % provider)).source
                    scraper = cls()
                    original = dict(self.data)
                    self.assertEqual(cls.sources(scraper, self.data, {}), [])
                    self.assertEqual(self.data, original)
                    self.assertTrue(any('S31E123' in url for url in urls), urls)
                    self.assertTrue(any('2026.10.20' in url for url in urls), urls)
                    for missing_date in ({}, {'premiered': None}, {'premiered': ''}, {'premiered': 'bad'}):
                        urls.clear()
                        legacy_data = {k: v for k, v in self.data.items() if k != 'premiered'}
                        legacy_data.update(missing_date)
                        self.assertEqual(cls.sources(cls(), legacy_data, {}), [])
                        self.assertFalse(any('2026.10.20' in url for url in urls))
                        self.assertTrue(any('S31E123' in url for url in urls), urls)

    def test_id_providers_accept_dated_releases(self):
        import json
        from concurrent.futures import Future
        for provider in sorted(ID_PROVIDERS):
            with self.subTest(provider=provider):
                path = ROOT / ('sources_cocoscrapers/torrents/%s.py' % provider)
                tree = ast.parse(path.read_text(encoding='utf-8'))
                cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
                method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'sources')
                # Use each provider's real information-line regex in its stream fixture.
                # Find the first re.compile argument (the info-line marker).
                markers = [n.args[0].value for n in ast.walk(method)
                           if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                           and n.func.attr == 'compile' and n.args and isinstance(n.args[0], ast.Constant)]
                marker = markers[0].replace('.*', '') if markers else ''
                records = []
                for index, identifier in enumerate(('S31E123', '2026.10.20', '2026.10.21')):
                    name = 'The.Daily.Show.' + identifier + '.1080p'
                    records.append(dict(hash=str(index + 1) * 40, infoHash=str(index + 1) * 40,
                        infohash=str(index + 1) * 40, info_hash=str(index + 1) * 40,
                        title=name + ('\n' + marker + ' 1 GB' if marker else ''),
                        name=name, raw_title=name, folderName=name, filename=name,
                        fileSize=1000, size=1000, seeders=10))
                payload = records if provider == 'zilean' else (
                    {'results': records} if provider == 'dmm' else
                    {'data': {'items': records}} if provider == 'torz' else {'streams': records})
                requests_seen = []
                def request(*args, **kwargs):
                    requests_seen.append((args, kwargs))
                    body = {'token': 'x', 'hash': 'y'} if 'challenge' in args[-1] else payload
                    return types.SimpleNamespace(text=json.dumps(body))
                response = types.SimpleNamespace(json=lambda: {'data': {'results': records}},
                    elapsed=types.SimpleNamespace(total_seconds=lambda: 0))
                env = dict(source_utils=utils, re=re, jsloads=json.loads,
                           client=types.SimpleNamespace(randomagent=lambda: 'test', session=types.SimpleNamespace(request=request)),
                           requests=types.SimpleNamespace(get=lambda *args, **kwargs: response),
                           log_utils=types.SimpleNamespace(log=lambda *args, **kwargs: None, LOGDEBUG=0, LOGWARNING=1))
                exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), env)
                scraper = types.SimpleNamespace(base_link='https://example.invalid',
                    tvSearch_link='/%s/%s/%s', timeout=7, min_seeders=0,
                    get_future=lambda key: Future(), _headers=lambda: {}, headers={}, auth=None, _token=lambda: 'test',
                    get_sources=lambda url, files: files.extend(records))
                if provider == 'dmm': scraper.tvSearch_link = '/%s/%s'
                if provider == 'mediafusion': scraper.tvSearch_link = '/%s/%s/%s/%s'
                result = env['sources'](scraper, self.data, {})
                self.assertEqual({r['hash'] for r in result}, {'1' * 40, '2' * 40})
                for r in result:
                    self.assertNotIn('2026.10.20', r['name_info'])
                for missing_date in ({}, {'premiered': None}, {'premiered': ''}, {'premiered': 'bad'}):
                    legacy_data = {k: v for k, v in self.data.items() if k != 'premiered'}
                    legacy_data.update(missing_date)
                    result = env['sources'](scraper, legacy_data, {})
                    self.assertEqual([r['hash'] for r in result], ['1' * 40])

    def test_wrapper_preserves_numbered_results_on_failure(self):
        calls = []
        @utils.airdate_sources
        def method(self, data, hostDict):
            calls.append(dict(data))
            self.sources = []
            if data.get('_coco_airdate_query'): raise RuntimeError('offline')
            self.sources.append({'hash': 'A' * 40})
            return self.sources
        result = method(types.SimpleNamespace(), self.data, {})
        self.assertEqual(result, [{'hash': 'A' * 40}])
        self.assertEqual(len(calls), 2)
        self.assertNotIn('_coco_airdate_query', self.data)


class ExternalAddonCompatibilityTests(unittest.TestCase):
    def test_provider_entry_points_keep_legacy_parameters(self):
        providers = ROOT / 'sources_cocoscrapers/torrents'
        for path in providers.glob('*.py'):
            if path.stem == '__init__': continue
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
            cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'source')
            methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
            with self.subTest(provider=path.stem):
                self.assertEqual([a.arg for a in methods['sources'].args.args], ['self', 'data', 'hostDict'])
                self.assertFalse(methods['sources'].args.kwonlyargs)
                if 'sources_packs' in methods:
                    args = methods['sources_packs'].args
                    self.assertEqual([a.arg for a in args.args],
                                     ['self', 'data', 'hostDict', 'search_series', 'total_seasons', 'bypass_filter'])
                    self.assertEqual(len(args.defaults), 3)

    def test_shared_helpers_accept_old_positional_calls(self):
        import inspect
        inspect.signature(utils.check_title).bind('Show', [], 'Show.S01E02', 'S01E02', '2000')
        inspect.signature(utils.check_title).bind('Movie', [], 'Movie.2025', '2025', '2025', ['2024', '2025', '2026'])
        self.assertTrue(utils.check_title('Show', [], 'Show.S01E02.1080p', 'S01E02', '2000'))
        self.assertTrue(utils.check_title('Movie', [], 'Movie.2025.1080p', '2025', '2025', ['2024', '2025', '2026']))
        self.assertEqual(utils.info_from_name('Show.S01E02.1080p', 'Show', '2000', 'S01E02', 'Guest'), '.1080p.')
        self.assertEqual(utils.info_from_name('Show.S01.1080p', 'Show', '2000', None, None, '1', 'season'), '.1080p.')

    def test_numbered_results_keep_the_existing_result_schema(self):
        data = dict(tvshowtitle='The Daily Show', title='Guest', year='1996',
                    season='31', episode='123', aliases=[], imdb='tt1234567')
        expected = {'provider', 'source', 'seeders', 'hash', 'name', 'name_info',
                    'quality', 'language', 'url', 'info', 'direct', 'debridonly', 'size'}
        for provider in ('eztv', 'knaben'):
            with self.subTest(provider=provider):
                result, urls = AirdateTests().provider(provider, data, [('a' * 40, 'The.Daily.Show.S31E123.1080p')])
                self.assertEqual(len(urls), 1)
                self.assertEqual(len(result), 1)
                self.assertEqual(set(result[0]), expected)
                self.assertNotIn('_coco_airdate_query', data)


if __name__ == '__main__':
    unittest.main()
