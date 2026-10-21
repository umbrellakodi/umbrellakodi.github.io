"""EZTV API fixtures: pagination, filtering, packs, and failure isolation."""
import ast
import json
from pathlib import Path
import types
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse
from test_airdate_search import ROOT, utils, load_file

# Use real season-pack matching without Kodi imports.
tree = ast.parse((ROOT / 'modules/source_utils.py').read_text(encoding='utf-8'))
for name in ('release_title_format', 'filter_season_pack'):
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'source_utils.py', 'exec'), utils.__dict__)


class EztvApiTests(unittest.TestCase):
    data = dict(tvshowtitle='The Daily Show', title='Guest', year='1996',
                season='31', episode='123', imdb='tt1234567', aliases=[], premiered='2026-10-20')

    def scraper(self, pages):
        calls = []
        def request(url, **kwargs):
            calls.append((url, kwargs))
            params = parse_qs(urlparse(url).query)
            value = pages[int(params['page'][0]) - 1]
            if isinstance(value, Exception): raise value
            return json.dumps(value) if not isinstance(value, str) else value
        client = types.SimpleNamespace(request=request)
        modules = types.ModuleType('cocoscrapers.modules')
        modules.client, modules.source_utils = client, utils
        with patch.dict('sys.modules', {'cocoscrapers': types.ModuleType('cocoscrapers'), 'cocoscrapers.modules': modules}):
            module = load_file('eztv', ROOT / 'sources_cocoscrapers/torrents/eztv.py')
        scraper = module.source()
        scraper.page_limit = 2
        return scraper, calls, module

    def row(self, identifier, digit='a', **fields):
        return dict(hash=digit * 40, filename='The.Daily.Show.%s.1080p.mkv' % identifier,
                    seeds=20, size_bytes='1073741824', imdb_id='1234567', **fields)

    def page(self, rows, count=None):
        return dict(imdb_id='1234567', torrents_count=len(rows) if count is None else count, torrents=rows)

    def test_paginates_and_filters_numbered_and_date_releases(self):
        scraper, calls, _ = self.scraper([
            self.page([self.row('S31E123'), self.row('S31E124', 'b')], 4),
            self.page([self.row('2026.10.20', 'c'), self.row('2026.10.21', 'd')], 4)])
        results = scraper.sources(self.data, {})
        self.assertEqual([r['hash'] for r in results], ['a' * 40, 'c' * 40])
        self.assertEqual(len(calls), 2)
        self.assertEqual(parse_qs(urlparse(calls[0][0]).query)['imdb_id'], ['1234567'])
        self.assertTrue(all(r['provider'] == 'eztv' for r in results))
        self.assertTrue(all(r['url'].startswith('magnet:?xt=urn:btih:') for r in results))

    def test_missing_invalid_imdb_and_movie_do_not_request_global_feed(self):
        for data in ({}, dict(self.data, imdb=None), dict(self.data, imdb='0'),
                     dict(self.data, imdb='bad'), {'title': 'Movie', 'imdb': 'tt1234567'}):
            scraper, calls, _ = self.scraper([])
            self.assertEqual(scraper.sources(data, {}), [])
            self.assertEqual(calls, [])

    def test_legacy_numbered_results_without_airdate(self):
        scraper, _, _ = self.scraper([self.page([self.row('S31E123'), self.row('2026.10.20', 'b')])])
        data = {k: v for k, v in self.data.items() if k != 'premiered'}
        self.assertEqual([r['hash'] for r in scraper.sources(data, {})], ['a' * 40])

    def test_partial_page_failure_keeps_results(self):
        scraper, calls, _ = self.scraper([self.page([self.row('S31E123'), self.row('S31E124', 'b')], 4), RuntimeError('offline')])
        self.assertEqual(len(scraper.sources(self.data, {})), 1)
        self.assertEqual(len(calls), 2)

    def test_repeated_pages_stop_and_deduplicate(self):
        page = self.page([self.row('S31E123'), self.row('2026.10.20', 'b')], 10)
        scraper, calls, _ = self.scraper([page, page])
        self.assertEqual(len(scraper.sources(self.data, {})), 2)
        self.assertEqual(len(calls), 2)

    def test_malformed_payload_and_wrong_show_are_ignored(self):
        for page in ('not json', [], {'torrents': None}, dict(self.page([self.row('S31E123')]), imdb_id='999')):
            scraper, _, _ = self.scraper([page])
            self.assertEqual(scraper.sources(self.data, {}), [])
        row = self.row('S31E123'); row['imdb_id'] = '999'
        scraper, _, _ = self.scraper([self.page([row])])
        self.assertEqual(scraper.sources(self.data, {}), [])

    def test_season_packs_and_bypass(self):
        scraper, _, _ = self.scraper([self.page([self.row('S31.Complete'), self.row('S32.Complete', 'b')])])
        result = scraper.sources_packs(self.data, {})
        self.assertEqual([r['hash'] for r in result], ['a' * 40])
        self.assertEqual(result[0]['package'], 'season')
        scraper, _, _ = self.scraper([self.page([self.row('S31.Complete')])])
        self.assertEqual(len(scraper.sources_packs(self.data, {}, bypass_filter=True)), 1)
        scraper, calls, _ = self.scraper([])
        self.assertEqual(scraper.sources_packs(self.data, {}, search_series=True), [])
        self.assertEqual(calls, [])

    def test_request_budget_and_page_cap(self):
        scraper, calls, module = self.scraper([self.page([self.row('S31E123'), self.row('S31E124', 'b')], 200)])
        scraper.max_pages = 1
        self.assertEqual(len(scraper.sources(self.data, {})), 1)
        self.assertEqual(len(calls), 1)
        scraper, calls, module = self.scraper([])
        with patch.object(module, 'monotonic', side_effect=[0, 13]):
            self.assertEqual(scraper.sources(self.data, {}), [])
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
