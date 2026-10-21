"""Subtitle selection regressions using Kodi track metadata."""
import ast
import json
from pathlib import Path
import re
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / 'resources/lib/modules/player.py'


class SubtitleSelectionTests(unittest.TestCase):
    def setUp(self):
        self.settings = {'subtitles.lang.1': 'English', 'subtitles.lang.2': 'English',
                         'subtitles.prefer.embedded': 'true',
                         'subtitles.prefer.hearing_impaired': 'true'}
        self.player = Mock()
        self.player.getSubtitles.return_value = 'eng'
        self.player.getAvailableSubtitleStreams.return_value = ['eng', 'eng']
        self.control = Mock()
        self.logs = Mock()
        self.opensubs = Mock()
        xbmc = Mock()
        xbmc.Player.return_value = self.player
        xbmc.convertLanguage.side_effect = lambda value, code: {'english': 'eng', 'french': 'fra'}.get(value, value)
        ns = dict(xbmc=xbmc, control=self.control, log_utils=self.logs, opensubs=self.opensubs,
                  getSetting=lambda key: self.settings.get(key, 'false'),
                  getLS=lambda key: 'subtitle %s', jsloads=json.loads, jsdumps=json.dumps, re=re)
        tree = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Subtitles')
        exec(compile(ast.Module(body=[cls], type_ignores=[]), str(SOURCE), 'exec'), ns)
        self.subs = ns['Subtitles']()

    def tracks(self, *tracks):
        self.control.jsonrpc.return_value = json.dumps({'result': {'subtitles': tracks}})

    def get(self):
        self.subs.get('Example', 2026, 'tt123', 1, 2)
        self.logs.error.assert_not_called()
        self.opensubs.Opensubs.assert_not_called()

    def test_existing_english_track_does_not_hide_sdh_flag(self):
        self.tracks({'index': 3, 'language': 'eng', 'name': ''},
                    {'index': 7, 'language': 'eng', 'name': '', 'isimpaired': True})
        self.get()
        self.player.setSubtitleStream.assert_called_once_with(7)

    def test_hi_preference_works_without_prefer_embedded(self):
        self.settings['subtitles.prefer.embedded'] = 'false'
        self.tracks({'index': 0, 'language': 'eng', 'name': ''},
                    {'index': 1, 'language': 'eng', 'name': 'English SDH'})
        self.get()
        self.player.setSubtitleStream.assert_called_once_with(1)

    def test_language_and_forced_preferences_are_respected(self):
        self.tracks({'index': 0, 'language': 'fra', 'isimpaired': True},
                    {'index': 1, 'language': 'eng', 'isimpaired': True, 'isforced': True},
                    {'index': 2, 'language': 'eng', 'isimpaired': True})
        self.get()
        self.player.setSubtitleStream.assert_called_once_with(2)

    def test_non_hi_preference_selects_regular_track(self):
        self.settings['subtitles.prefer.hearing_impaired'] = 'false'
        self.tracks({'index': 0, 'language': 'eng', 'isimpaired': True},
                    {'index': 1, 'language': 'eng'})
        self.get()
        self.player.setSubtitleStream.assert_called_once_with(1)

    def test_rpc_failure_falls_back_to_python_tracks(self):
        self.control.jsonrpc.side_effect = RuntimeError('unavailable')
        self.player.getAvailableSubtitleStreams.return_value = ['eng', 'eng SDH']
        self.get()
        self.player.setSubtitleStream.assert_called_once_with(1)

    def test_no_sdh_falls_back_to_first_language_match(self):
        self.tracks({'index': 0, 'language': 'eng'}, {'index': 1, 'language': 'eng'})
        self.get()
        self.player.setSubtitleStream.assert_called_once_with(0)

    def test_all_preferences_disabled_preserves_current_track(self):
        self.settings['subtitles.prefer.embedded'] = 'false'
        self.settings['subtitles.prefer.hearing_impaired'] = 'false'
        self.get()
        self.player.setSubtitleStream.assert_not_called()
        self.control.jsonrpc.assert_not_called()


if __name__ == '__main__':
    unittest.main()
