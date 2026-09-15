"""Exercise Custom indicators without requiring Kodi or a live account."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_function(filename, name, namespace):
    tree = ast.parse((ROOT / filename).read_text(encoding='utf-8-sig'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), filename, 'exec'), namespace)
    return namespace[name]


class CustomIndicatorTests(unittest.TestCase):
    def overlay(self, progress, indicators):
        namespace = dict(customIndicators=True,
                         customtrakt=SimpleNamespace(getShowProgress=lambda imdb: progress))
        for name in ('trakt', 'simkl', 'mdblist', 'floppy', 'scrob', 'punchplay'):
            namespace[name + 'Indicators'] = False
        function = load_function('resources/lib/modules/playcount.py', 'getEpisodeOverlay', namespace)
        return function(indicators, 'tt0353049', '71862', '2', '12')

    def test_server_watched_overrides_missing_local_history(self):
        progress = {'seasons': [{'number': 2, 'episodes': [{'number': 12, 'completed': True}]}]}
        self.assertEqual(self.overlay(progress, []), '5')

    def test_server_unwatched_overrides_stale_local_history(self):
        progress = {'seasons': [{'number': 2, 'episodes': [{'number': 12, 'completed': False}]}]}
        local = [({'imdb': 'tt0353049'}, 1, {2: [(12, 12)]})]
        self.assertEqual(self.overlay(progress, local), '4')

    def test_local_fallback_when_progress_unavailable(self):
        local = [({'imdb': 'tt0353049'}, 1, {2: [(12, 12)]})]
        self.assertEqual(self.overlay(None, local), '5')

    def test_forced_history_reads_from_beginning_and_failure_keeps_cursor(self):
        from datetime import datetime
        requests, updates = [], []
        namespace = dict(datetime=datetime,
                         customtraktsync=SimpleNamespace(last_sync=lambda key: 1700000000,
                                                       update_last_watched_at=lambda key: updates.append(key)),
                         getActivity=lambda activities: 1700000100,
                         getCustomAsJson=lambda url: requests.append(url),
                         log_utils=SimpleNamespace(error=lambda: self.fail('Unexpected exception')))
        function = load_function('resources/lib/modules/customtrakt.py', 'sync_watchedProgress', namespace)
        function(forced=True)
        self.assertIn('since=1970-01-01T00:00:00Z', requests[0])
        self.assertEqual(updates, [])


if __name__ == '__main__':
    unittest.main()
