"""Offline checks for air-date playback, cloud, and resolver integration."""
import ast
import importlib.util
from pathlib import Path
import re
import sys
from types import SimpleNamespace, ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'resources/lib'
spec = importlib.util.spec_from_file_location('airdate_source_utils', LIB / 'modules/source_utils.py')
utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utils)


def method(path, name):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    return next(n for c in tree.body if isinstance(c, ast.ClassDef)
                for n in c.body if isinstance(n, ast.FunctionDef) and n.name == name)


class AirdatePlaybackTests(unittest.TestCase):
    def match(self, filename, date='2026-10-20', split=False):
        return utils.seas_ep_filter('31', '123', filename, split=split, premiered=date)

    def test_date_variants_and_boundaries(self):
        for separator in ('.', '-', ' '):
            filename = 'The.Daily.Show.2026%s10%s20.1080p.mkv' % (separator, separator)
            self.assertTrue(self.match(filename))
            self.assertEqual(self.match(filename, split=True), '.1080p.mkv')
        self.assertFalse(self.match('The.Daily.Show.2026.10.21.mkv'))
        self.assertFalse(self.match('The.Daily.Show.2026.10.200.mkv'))
        self.assertFalse(self.match('The.Daily.Show.2026.10.20.mkv', None))
        self.assertFalse(self.match('The.Daily.Show.2026.10.20.mkv', 'bad'))
        self.assertTrue(self.match('The.Daily.Show.2026.10.20.mkv', '2026.10.20'))
        self.assertIsNone(utils.episode_airdate_pattern('2026-02-30'))

    def test_numbered_compatibility(self):
        for filename in ('The.Daily.Show.S31E123.1080p.mkv', 'The.Daily.Show.31x123.1080p.mkv'):
            self.assertTrue(self.match(filename))
            self.assertTrue(self.match(filename, None))
        self.assertFalse(self.match('The.Daily.Show.S31E124.1080p.mkv'))
        self.assertFalse(self.match('Show.S31E124.2026.10.20.mkv'))
        self.assertTrue(self.match('Show.S31E123.2026.10.21.mkv'))
        self.assertEqual(utils.seas_ep_filter('31', '123', 'Show.S31E123.extra.mkv', True), 'extra.mkv')

    def test_parent_folder_date_cannot_select_wrong_file(self):
        for prefix in ('/Show.2026.10.20/', 'C:\\Show.2026.10.20\\'):
            self.assertFalse(self.match(prefix + 'Wrong.Episode.mkv'))
            self.assertFalse(self.match(prefix + 'Show.2026.10.21.mkv'))
            self.assertTrue(self.match(prefix + 'Show.2026.10.20.mkv'))
        self.assertFalse(utils.seas_ep_filter('31', '20', '/Show.2026.10.20/Wrong.mkv', premiered='2026-10-20'))
        # Day numbers must not accidentally satisfy legacy episode-only patterns.
        self.assertFalse(utils.seas_ep_filter('31', '20', 'Show.2026.10.20.mkv', premiered='2026-10-21'))

    def test_all_resolvers_forward_date(self):
        for provider in ('realdebrid', 'premiumize', 'alldebrid', 'offcloud', 'torbox', 'easydebrid'):
            with self.subTest(provider=provider):
                node = method(LIB / ('debrid/%s.py' % provider), 'resolve_magnet')
                self.assertEqual(node.args.args[-1].arg, 'premiered')
                self.assertIsNone(node.args.defaults[-1].value)
                calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)
                         and isinstance(n.func, ast.Name) and n.func.id == 'seas_ep_filter']
                self.assertTrue(calls)
                for call in calls:
                    self.assertTrue(any(k.arg == 'premiered' and isinstance(k.value, ast.Name)
                                        and k.value.id == 'premiered' for k in call.keywords))

    def test_cloud_query_dates(self):
        for provider in ('rd', 'pm', 'ad', 'oc', 'tb'):
            with self.subTest(provider=provider):
                path = LIB / ('cloud_scrapers/%s_cloud.py' % provider)
                tree = ast.parse(path.read_text(encoding='utf-8-sig'))
                self.assertTrue(any(isinstance(n, ast.ImportFrom) and any(a.name == 'episode_airdate_pattern' for a in n.names) for n in tree.body))
                node = method(path, 'sources')
                # Execute setup up to query construction, before any cloud API calls.
                setup = []
                block = next(n for n in node.body if isinstance(n, ast.Try))
                for n in block.body:
                    setup.append(n)
                    if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == 'date_pattern': break
                env = dict(data=dict(tvshowtitle='Show', title='Guest', year='1996', season='31', episode='123', aliases=[], premiered='2026-10-20'),
                           self=SimpleNamespace(episode_query_list=lambda: ['s31e123']),
                           episode_airdate_pattern=utils.episode_airdate_pattern)
                exec(compile(ast.Module(body=setup, type_ignores=[]), str(path), 'exec'), env)
                self.assertTrue(any(re.search(p, '.show.2026.10.20.mkv.') for p in env['query_list']))
                self.assertFalse(any(re.search(p, '.show.2026.10.21.mkv.') for p in env['query_list']))

    def test_sources_and_subtitles_forward_episode_metadata(self):
        node = method(LIB / 'modules/sources.py', 'sourcesResolve')
        calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr == 'resolve_magnet']
        self.assertEqual(len(calls), 1)
        self.assertTrue(any(k.arg == 'premiered' for k in calls[0].keywords))
        player = ast.parse((LIB / 'modules/player.py').read_text(encoding='utf-8-sig'))
        calls = [n for n in ast.walk(player) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == 'seas_ep_filter']
        self.assertEqual(len(calls), 4)
        for call in calls:
            self.assertTrue(any(k.arg == 'premiered' for k in call.keywords))
        for name in ('get', 'downloadForPlayNext'):
            subtitles = next(n for n in player.body if isinstance(n, ast.ClassDef) and n.name == 'Subtitles')
            func = next(n for n in subtitles.body if isinstance(n, ast.FunctionDef) and n.name == name)
            self.assertEqual(func.args.args[-1].arg, 'premiered')

    def test_offcloud_selects_correct_date_and_excludes_samples(self):
        path = LIB / 'debrid/offcloud.py'
        node = method(path, 'resolve_magnet')
        # Imports are supplied by a stub package, while the real matcher is used.
        mod = ModuleType('resources.lib.modules.source_utils')
        mod.seas_ep_filter = utils.seas_ep_filter
        mod.extras_filter = lambda: ('sample', 'extra')
        env = dict(supported_video_extensions=lambda: ('.mkv',), log_utils=SimpleNamespace(error=lambda *a: None))
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), env)
        rows = [dict(filename='Show.2026.10.21.mkv', url='wrong'),
                dict(filename='Show.2026.10.20.sample.mkv', url='sample'),
                dict(filename='Show.2026.10.20.mkv', url='correct')]
        obj = SimpleNamespace(check_cache=lambda hashes: {'cachedItems': ['abc']},
                              _POST=lambda *args, **kwargs: rows, cache_download='test')
        with patch.dict(sys.modules, {'resources.lib.modules.source_utils': mod}):
            self.assertEqual(env['resolve_magnet'](obj, 'magnet:test', 'abc', '31', '123', 'Show', premiered='2026-10-20'), 'correct')
            self.assertIsNone(env['resolve_magnet'](obj, 'magnet:test', 'abc', '31', '123', 'Show', premiered='2026-10-22'))


if __name__ == '__main__':
    unittest.main()
