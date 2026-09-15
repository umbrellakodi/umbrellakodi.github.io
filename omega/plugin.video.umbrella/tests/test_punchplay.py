"""Offline contract and integration checks; no Kodi session or live account needed."""
import ast
from contextlib import closing
import importlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlsplit, parse_qs
from urllib.parse import parse_qsl, quote_plus
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SETTINGS = {}
TEMP = tempfile.TemporaryDirectory()
control = types.ModuleType('resources.lib.modules.control')
control.setting = lambda key: SETTINGS.get(key, '')
control.setSetting = lambda key, value: SETTINGS.__setitem__(key, str(value))
control.existsPath = os.path.exists
control.dataPath = TEMP.name
control.makeFile = lambda path: os.makedirs(path, exist_ok=True)
control.punchplaySyncFile = os.path.join(TEMP.name, 'punchplay.db')
control.joinPath = os.path.join
control.monitor = Mock()
control.monitor.abortRequested.return_value = False
control.monitor.waitForAbort.return_value = False
control.progressDialog = Mock()
control.progressDialog.iscanceled.return_value = False
control.addonInfo = lambda key: '1.0' if key == 'version' else 'Umbrella'
control.openSettings = Mock()
control.refresh = Mock()
control.trigger_widget_refresh = Mock()
control.notification = Mock()
control.okDialog = Mock()
control.yesnoDialog = Mock(return_value=False)
control.homeWindow = Mock()
control.infoLabel = Mock(return_value='plugin.video.umbrella')
control.hide = Mock()
control.selectDialog = Mock(return_value=-1)
sys.modules[control.__name__] = control
log = types.ModuleType('resources.lib.modules.log_utils')
log.LOGWARNING = 2
log.LOGINFO = 1
log.log = Mock()
log.error = Mock()
sys.modules[log.__name__] = log

provider = importlib.import_module('resources.lib.modules.punchplay')
db = importlib.import_module('resources.lib.database.punchplaysync')
CONTRACT = json.loads((ROOT / 'tests/fixtures/punchplay-contract.json').read_text())


def validate(value, schema):
    if '$ref' in schema:
        return validate(value, CONTRACT['components']['schemas'][schema['$ref'].split('/')[-1]])
    if 'anyOf' in schema:
        outcomes = []
        for candidate in schema['anyOf']:
            try:
                validate(value, candidate)
                outcomes.append(True)
            except AssertionError:
                pass
        assert outcomes, 'No anyOf alternative matched'
    kind = schema.get('type')
    if kind:
        kinds = kind if isinstance(kind, list) else [kind]
        matches = {'object': isinstance(value, dict), 'array': isinstance(value, list),
                   'string': isinstance(value, str), 'null': value is None,
                   'boolean': isinstance(value, bool),
                   'integer': isinstance(value, int) and not isinstance(value, bool),
                   'number': isinstance(value, (int, float)) and not isinstance(value, bool)}
        assert any(matches[k] for k in kinds), (value, kinds)
    if 'enum' in schema:
        assert value in schema['enum'], value
    if isinstance(value, dict):
        assert set(schema.get('required', [])) <= set(value), ('Missing fields', schema.get('required'), value)
        props = schema.get('properties', {})
        if schema.get('additionalProperties') is False:
            assert set(value) <= set(props), ('Unknown fields', set(value) - set(props))
        for key, child in value.items():
            if key in props:
                validate(child, props[key])
    if isinstance(value, list):
        assert len(value) >= schema.get('minItems', 0)
        assert len(value) <= schema.get('maxItems', float('inf'))
        for child in value:
            validate(child, schema.get('items', {}))
    if isinstance(value, str):
        assert len(value) >= schema.get('minLength', 0)
        assert len(value) <= schema.get('maxLength', float('inf'))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        assert value >= schema.get('minimum', float('-inf'))
        assert value <= schema.get('maximum', float('inf'))
        assert value > schema.get('exclusiveMinimum', float('-inf'))


def response(data, status=200, headers=None):
    result = Mock(status_code=status, headers=headers or {}, content=b'json')
    result.json.return_value = data
    return result


class PunchPlayTests(unittest.TestCase):
    def setUp(self):
        SETTINGS.clear()
        client_patch = patch.object(provider, 'CLIENT_ID', 'test-client')
        client_patch.start()
        self.addCleanup(client_patch.stop)
        secret_patch = patch.object(provider, 'CLIENT_SECRET', 'test-secret')
        secret_patch.start()
        self.addCleanup(secret_patch.stop)
        SETTINGS.update({'markwatched.percent': '85', 'indicators.alt': '7', 'scrobble.source': '7'})
        with closing(sqlite3.connect(control.punchplaySyncFile)) as con:
            with con:
                for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
                    con.execute('DROP TABLE ' + name)
        provider._sessions.clear()
        provider._server_clock = None
        provider._save_tokens({'access_token': 'initial-access', 'refresh_token': 'initial-refresh', 'expires_in': 3600})
        provider._session = Mock()
        provider._session.request.return_value = response({'ok': True})
        control.okDialog.reset_mock()
        control.notification.reset_mock()
        control.yesnoDialog.reset_mock()
        control.yesnoDialog.return_value = False
        control.infoLabel.return_value = 'plugin.video.umbrella'
        control.selectDialog.return_value = -1
        control.selectDialog.side_effect = None

    def test_playback_payloads_match_published_contract_and_keep_session(self):
        self.assertTrue(provider.scrobbleStart('episode', tvshowtitle='Test show', year='2026', tmdb='95396',
                                              imdb='tt123', season=0, episode=2, current_time=120, total_time=1000, watched_percent=12))
        self.assertTrue(provider.scrobbleEpisode('tt123', '95396', '', 0, 2, 20, 200, 1000))
        self.assertTrue(provider.scrobbleStart('episode', tvshowtitle='Test show', tmdb='95396', imdb='tt123',
                                              season=0, episode=2, resumed=True, current_time=250, total_time=1000, watched_percent=25))
        self.assertTrue(provider.scrobbleStopEpisode('tt123', '95396', '', 0, 2, 90, True, 900, 1000, True))
        calls = provider._session.request.call_args_list
        self.assertEqual([c.args[1].split('/')[-1] for c in calls], ['start', 'pause', 'resume', 'stop'])
        payloads = [c.kwargs['json'] for c in calls]
        for body in payloads:
            validate(body, CONTRACT['components']['schemas']['PlaybackInput'])
        self.assertEqual(len({i['playback_session_id'] for i in payloads}), 1)
        self.assertEqual(len({i['event_id'] for i in payloads}), 4)
        self.assertEqual(payloads[0]['progress'], 0.12)
        self.assertEqual(payloads[-1]['position_seconds'], 900)
        self.assertTrue(payloads[-1]['watched'])
        self.assertEqual(payloads[-1]['watched_threshold'], 0.85)
        self.assertEqual(payloads[-1]['season'], 0)
        self.assertEqual(sorted(i['event_created_at'] for i in payloads), [i['event_created_at'] for i in payloads])

    def test_late_heartbeat_and_duplicate_stop_do_not_reopen_completed_session(self):
        provider.scrobbleStart('movie', title='Test movie', tmdb='550')
        provider.scrobbleStopMovie('', '550', 100, True, 1000, 1000)
        count = provider._session.request.call_count
        provider.scrobbleProgress('movie', tmdb='550', watched_percent=90, current_time=900, total_time=1000)
        provider.scrobbleStopMovie('', '550', 100, True, 1000, 1000)
        self.assertEqual(provider._session.request.call_count, count)
        provider.scrobbleStart('movie', title='Test movie', tmdb='550')
        self.assertEqual(provider._session.request.call_count, count + 1)

    def test_incomplete_stop_saves_local_bookmark(self):
        provider.scrobbleStart('movie', title='Test movie', tmdb='550')
        provider.scrobbleStopMovie('', '550', 40, False, 400, 1000)
        self.assertFalse(provider._session.request.call_args.kwargs['json']['watched'])
        self.assertEqual(float(db.fetch_bookmarks('', '550')), 40)

    def test_retry_reuses_event_identity(self):
        provider._session.request.side_effect = [response({}, 500), response({'ok': True})]
        provider.scrobbleStart('movie', title='Test movie', tmdb='550')
        calls = provider._session.request.call_args_list
        self.assertEqual(calls[0].kwargs['json'], calls[1].kwargs['json'])

    def test_refresh_rotation_retries_401_with_new_access_token(self):
        provider._session.request.side_effect = [response({}, 401), response({'id': 'account'})]
        provider._session.post.return_value = response({'access_token': 'rotated-access', 'refresh_token': 'rotated-refresh', 'expires_in': 3600})
        self.assertEqual(provider._request('/me'), {'id': 'account'})
        self.assertEqual(SETTINGS['punchplay.refreshtoken'], 'rotated-refresh')
        self.assertEqual(provider._tokens()['refresh_token'], 'rotated-refresh')
        self.assertEqual(provider._session.request.call_args.kwargs['headers']['Authorization'], 'Bearer rotated-access')
        validate(provider._session.post.call_args.kwargs['json'], CONTRACT['components']['schemas']['RefreshTokenInput'])

    def test_concurrent_refreshes_rotate_once(self):
        provider._session.post.return_value = response({'access_token': 'rotated-access', 'refresh_token': 'rotated-refresh', 'expires_in': 3600})
        errors = []
        def run():
            try:
                provider._refresh('initial-access')
            except Exception as exc:
                errors.append(exc)
        threads = [threading.Thread(target=run) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(provider._session.post.call_count, 1)

    def test_changed_client_id_cannot_use_previous_tokens(self):
        provider.CLIENT_ID = 'another-client'
        self.assertFalse(provider.getPunchPlayCredentialsInfo())
        with self.assertRaises(provider.PunchPlayError):
            provider._request('/me')
        provider._session.request.assert_not_called()

    def test_authentication_uses_registered_app_and_device_flow(self):
        provider._session.request.return_value = response({'verification_uri': 'https://punchplay.tv/link',
                                                         'user_code': 'ABCD', 'device_code': 'device', 'expires_in': 600})
        provider._session.post.side_effect = [response({'error': 'authorization_pending'}, 400),
                                             response({'access_token': 'new-access', 'refresh_token': 'new-refresh', 'expires_in': 3600})]
        provider._session.get.return_value = response({'id': 'account', 'username': 'tester', 'scopes': provider.SCOPES.split()})
        with patch.object(provider, 'sync_account', return_value=True):
            provider.punchplayAuth()
        self.assertEqual(provider._state('account'), 'account')
        self.assertEqual(SETTINGS['punchplay.username'], 'tester')
        control.yesnoDialog.assert_called_once()
        code_call = provider._session.request.call_args
        self.assertEqual(code_call.args[1], provider.BASE_URL + '/auth/device/code')
        validate(code_call.kwargs['json'], CONTRACT['components']['schemas']['DeviceCodeInput'])
        validate(provider._session.post.call_args.kwargs['json'], CONTRACT['components']['schemas']['DeviceTokenInput'])
        self.assertNotIn('redirect_uri', code_call.kwargs['json'])

    def test_accepting_provider_selection_sets_both_services_and_labels(self):
        SETTINGS.update({'indicators.alt': '1', 'scrobble.source': '1'})
        control.yesnoDialog.return_value = True
        self.assertTrue(provider._offer_provider_selection())
        self.assertEqual(SETTINGS['indicators.alt'], '7')
        self.assertEqual(SETTINGS['scrobble.source'], '7')
        self.assertEqual(SETTINGS['indicators'], 'PunchPlay')
        self.assertEqual(SETTINGS['scrobble'], 'PunchPlay')

    def test_declining_provider_selection_keeps_existing_services(self):
        SETTINGS.update({'indicators.alt': '1', 'scrobble.source': '2'})
        self.assertFalse(provider._offer_provider_selection())
        self.assertEqual(SETTINGS['indicators.alt'], '1')
        self.assertEqual(SETTINGS['scrobble.source'], '2')

    def test_missing_scopes_leave_existing_account_intact(self):
        provider._session.request.return_value = response({'verification_uri': 'https://punchplay.tv/link',
                                                         'user_code': 'ABCD', 'device_code': 'device', 'expires_in': 600})
        provider._session.post.return_value = response({'access_token': 'wrong-scopes', 'refresh_token': 'refresh'})
        provider._session.get.return_value = response({'id': 'another-account', 'scopes': ['profile:read']})
        provider.punchplayAuth()
        self.assertEqual(provider._tokens()['access_token'], 'initial-access')
        self.assertIn('scopes', control.okDialog.call_args.kwargs['message'])

    def test_cursor_offset_and_page_number_pagination(self):
        for pages, expected in [([{'items': [1], 'nextCursor': 'opaque +/&'}, {'items': [2], 'nextCursor': None}], 'cursor=opaque+%2B%2F%26'),
                                ([{'items': [1], 'nextOffset': 100}, {'items': [2], 'nextOffset': None}], 'offset=100'),
                                ([{'items': [1], 'page': 1, 'hasMore': True}, {'items': [2], 'page': 2, 'hasMore': False}], 'page=2')]:
            with patch.object(provider, '_request', side_effect=pages) as request:
                self.assertEqual(provider._pages('/me/history?limit=100'), [1, 2])
                self.assertIn(expected, request.call_args.args[0])
                self.assertIn('limit=100', request.call_args.args[0])

    def test_exact_resume_adapter_handles_specials_and_uses_seconds(self):
        item = {'id': 1, 'type': 'episode', 'tmdbId': 999, 'showTmdbId': 123, 'title': 'Show', 'showTitle': 'Show',
                'season': 0, 'episode': 2, 'progressSeconds': 321.5, 'durationSeconds': 1000,
                'progressPercent': 32.15, 'updatedAt': '2026-09-15T00:00:00Z'}
        with patch.object(provider, '_pages', return_value=[item]):
            result = provider.get_resume_item('123', 0, 2)
            self.assertEqual(result['position_seconds'], 321.5)
            self.assertAlmostEqual(result['progress_percent'], .3215)
            self.assertIsNone(provider.get_resume_item('999', 0, 2))
            self.assertEqual(provider.get_resume_percent('123', 0, 2), 32.15)
        with patch.object(provider, '_pages', return_value=[item]), patch.object(provider, '_request') as request:
            provider.scrobbleReset('', '123', '', 0, 2, refresh=False)
            request.assert_called_once_with('/playback/in-progress/1', 'DELETE')

    def sync_fixture(self, history, cursor='new-cursor', fail=False):
        def request(path, *args, **kwargs):
            route = urlsplit(path).path
            if route == '/me/sync/changes':
                return {'resources': ['history', 'list', 'list_item', 'playback', 'collection', 'interaction'],
                        'resetRequired': True, 'changes': [], 'hasMore': False, 'nextCursor': cursor}
            if route == '/me/history':
                if fail:
                    raise provider.PunchPlayError('Offline')
                return {'items': history, 'nextCursor': None}
            if route == '/me/lists':
                return {'items': [{'id': 7, 'name': 'Watchlist'}], 'nextCursor': None}
            if route == '/lists/7':
                return {'items': [{'id': 1, 'tmdbId': 550, 'title': 'Movie', 'type': 'movie', 'releaseDate': '1999-01-01'}]}
            if route == '/playback/in-progress':
                return [{'id': 1, 'type': 'movie', 'tmdbId': 550, 'title': 'Movie', 'progressSeconds': 123,
                         'durationSeconds': 1000, 'progressPercent': 12.3, 'updatedAt': '2026-09-15T00:00:00Z'}]
            if route == '/me/collection':
                return {'items': [{'id': 2, 'tmdbId': 550, 'title': 'Movie', 'kind': 'movie', 'format': 'digital'}], 'nextCursor': None}
            if route == '/me/watch-status':
                return {'items': [{'id': 3, 'tmdbId': 123, 'title': 'Show', 'kind': 'show', 'showStatus': 'ON_HOLD'}], 'hasMore': False}
            raise AssertionError(path)
        return patch.object(provider, '_request', side_effect=request)

    def test_sync_atomically_publishes_history_lists_bookmarks_and_cursor(self):
        history = [{'id': 1, 'type': 'movie', 'tmdbId': 550, 'title': 'Movie', 'year': 1999, 'watchedAt': '2026-09-01T00:00:00Z'},
                   {'id': 2, 'type': 'movie', 'tmdbId': 550, 'title': 'Movie', 'year': 1999, 'watchedAt': '2026-09-10T00:00:00Z'},
                   {'id': 3, 'type': 'episode', 'tmdbId': 999, 'showTmdbId': 123, 'season': 0, 'episode': 2, 'watchedAt': '2026-09-10T00:00:00Z'}]
        with self.sync_fixture(history), patch.object(provider, '_resolve_movie_imdb', return_value='tt550'), patch.object(provider, '_resolve_tv_imdb', return_value='tt123'):
            self.assertTrue(provider.sync_account())
        self.assertEqual(db.get_watched_movies(), ['tt550'])
        self.assertEqual(db.get_watched_movies_full()[0][-1], '2026-09-10T00:00:00Z')
        self.assertEqual(db.get_watched_episodes(), [('tt123', '123', '', 0, 2)])
        self.assertEqual(db.fetch_user_lists('movie')[0]['name'], 'Watchlist')
        self.assertEqual(db.fetch_list_items('7', 'movie')[0]['tmdb'], '550')
        self.assertEqual(float(db.fetch_bookmarks('', '550')), 12.3)
        self.assertEqual(provider._state('cursor'), 'new-cursor')
        self.assertEqual(provider.get_library_items('hold', 'show')[0]['tmdb'], '123')
        self.assertEqual(provider.get_library_items('collection', 'movie')[0]['tmdb'], '550')

    def test_history_sync_refreshes_previously_cached_movie_indicators(self):
        db.upsert_watched_movie('ttold', '100', 'Old movie', '2000')
        self.assertEqual(provider.cachesyncMovies(), ['ttold'])
        history = [{'id': 1, 'type': 'movie', 'tmdbId': 550, 'title': 'Movie', 'year': 1999, 'watchedAt': '2026-09-10T00:00:00Z'}]
        with self.sync_fixture(history), patch.object(provider, '_resolve_movie_imdb', return_value='tt550'):
            provider.sync_account(True)
        self.assertEqual(provider.cachesyncMovies(), ['tt550'])

    def test_sync_failure_retains_watched_state_and_cursor(self):
        db.upsert_watched_movie('tt550', '550', 'Movie', '1999', '2026-09-01T00:00:00Z')
        with provider._connection() as con:
            provider._put(con, 'cursor', 'previous-cursor')
        con.close()
        with self.sync_fixture([], fail=True), self.assertRaises(provider.PunchPlayError):
            provider.sync_account(True)
        self.assertEqual(db.get_watched_movies(), ['tt550'])
        self.assertEqual(provider._state('cursor'), 'previous-cursor')

    def test_sync_deletion_clears_indicators(self):
        db.upsert_watched_movie('tt550', '550', 'Movie', '1999', '2026-09-01T00:00:00Z')
        self.assertEqual(provider.cachesyncMovies(), ['tt550'])
        with self.sync_fixture([]):
            provider.sync_account(True)
        self.assertEqual(db.get_watched_movies(), [])
        self.assertEqual(provider.cachesyncMovies(), [])

    def test_unchanged_feed_does_not_download_history(self):
        with provider._connection() as con:
            provider._put(con, 'cursor', 'previous-cursor')
        con.close()
        with patch.object(provider, '_request', return_value={'resources': ['history'], 'resetRequired': False,
                          'changes': [], 'hasMore': False, 'nextCursor': 'previous-cursor'}) as request:
            provider.sync_account()
        request.assert_called_once_with('/me/sync/changes?cursor=previous-cursor')

    def test_bodyless_delete_sends_empty_json_required_by_live_api(self):
        provider._request('/title/movie/1081003/history', 'DELETE')
        call = provider._session.request.call_args
        self.assertEqual(call.args[0], 'DELETE')
        self.assertEqual(call.kwargs['json'], {})

    def test_manual_history_sync_suppresses_competing_widget_update(self):
        control.trigger_widget_refresh.reset_mock()
        with self.sync_fixture([]):
            provider.sync_account(True, refresh_widgets=False)
        control.trigger_widget_refresh.assert_not_called()

    def test_manual_watch_refreshes_widgets_without_library_scan_then_container(self):
        calls = Mock()
        calls.attach_mock(control.trigger_widget_refresh, 'widgets')
        calls.attach_mock(control.refresh, 'container')
        with patch.object(provider, '_history_write', return_value=True):
            self.assertTrue(provider._watch('movie', 'Movie', 'tt123', '', None, None, True, False, '550'))
        self.assertEqual([c[0] for c in calls.mock_calls], ['widgets', 'container'])
        self.assertEqual(calls.mock_calls[0].kwargs, {'update_library': False, 'force': True})

    def test_manual_watch_notifications_report_success_and_failure_when_enabled(self):
        SETTINGS['punchplay.general.notifications'] = 'true'
        for remove in (False, True):
            control.notification.reset_mock()
            with patch.object(provider, '_history_write', return_value=True):
                provider._watch('movie', 'Supergirl', 'tt123', '', None, None, False, remove, '1081003')
            self.assertIn('marked as %s' % ('unwatched' if remove else 'watched'), control.notification.call_args.kwargs['message'])
            with patch.object(provider, '_history_write', side_effect=provider.PunchPlayError('Example error')):
                self.assertFalse(provider._watch('movie', 'Supergirl', 'tt123', '', None, None, False, remove, '1081003'))
            self.assertIn('Example error', control.notification.call_args.kwargs['message'])

    def test_manual_watch_notifications_are_suppressed_when_disabled(self):
        SETTINGS['punchplay.general.notifications'] = 'false'
        control.notification.reset_mock()
        with patch.object(provider, '_history_write', return_value=True):
            provider._watch('movie', 'Supergirl', 'tt123', '', None, None, False, False, '1081003')
        with patch.object(provider, '_history_write', side_effect=provider.PunchPlayError('Example error')):
            provider._watch('movie', 'Supergirl', 'tt123', '', None, None, False, False, '1081003')
        control.notification.assert_not_called()

    def test_widget_manual_watch_uses_library_notification_without_container_refresh(self):
        control.infoLabel.return_value = ''
        control.trigger_widget_refresh.reset_mock()
        control.refresh.reset_mock()
        with patch.object(provider, '_history_write', return_value=True):
            self.assertTrue(provider._watch('movie', 'Supergirl', 'tt123', '', None, None, True, False, '1081003'))
        control.trigger_widget_refresh.assert_called_once_with(update_library=True, force=True)
        control.refresh.assert_not_called()

    def test_manual_history_time_uses_server_clock_when_local_clock_is_ahead(self):
        provider._session.request.return_value = response({'ok': True}, headers={'Date': 'Tue, 15 Sep 2026 15:36:32 GMT'})
        with patch.object(provider.time, 'time', return_value=2000000000), patch.object(provider.time, 'monotonic', return_value=100):
            provider._request('/me', auth=False)
            self.assertEqual(provider._watch_time(), '2026-09-15T15:36:27.000Z')
        with patch.object(provider.time, 'monotonic', return_value=102):
            self.assertEqual(provider._watch_time(), '2026-09-15T15:36:29.000Z')

    def test_manual_history_batches_match_contract(self):
        with patch.object(provider, 'sync_account', return_value=True), patch.object(provider, '_title', return_value={'title': {'name': 'Test show', 'year': 2026, 'tmdbId': 123}}) as title:
            provider.markEpisodeAsWatched('tt123', '', 0, 2)
        body = provider._session.request.call_args.kwargs['json']
        validate(body, CONTRACT['components']['schemas']['BulkHistoryInput'])
        self.assertEqual(body['items'][0]['tmdb_id'], 123)
        self.assertEqual(body['items'][0]['season'], 0)
        self.assertEqual(body['items'][0]['title'], 'Test show')
        self.assertEqual(body['items'][0]['year'], 2026)
        title.assert_called_once_with('show', '', 'tt123', '')
        self.assertIn('Idempotency-Key', provider._session.request.call_args.kwargs['headers'])

    def test_rejected_manual_history_reports_server_reason_and_does_not_sync(self):
        provider._session.request.return_value = response({'invalid': 1, 'results': [
            {'index': 0, 'status': 'invalid', 'error': 'Example server validation reason'}]})
        with patch.object(provider, 'sync_account') as sync, patch.object(provider, '_title', return_value={'title': {'name': 'Movie', 'year': 2026}}):
            with self.assertRaisesRegex(provider.PunchPlayError, 'Example server validation reason'):
                provider.markMovieAsWatched('tt123', '550')
        sync.assert_not_called()

    def test_widget_imdb_only_movie_uses_canonical_tmdb_id(self):
        with patch.object(provider, 'sync_account', return_value=True), patch.object(provider, '_title', return_value={'title': {'name': 'Coyote vs. Acme', 'year': 2026, 'tmdbId': 1204680}}):
            provider._watch('movie', 'Coyote vs. Acme', 'tt1756855', '', '', '', True, False, '')
        item = provider._session.request.call_args.kwargs['json']['items'][0]
        self.assertEqual(item['tmdb_id'], 1204680)
        self.assertEqual(item['title'], 'Coyote vs. Acme')
        self.assertEqual(item['year'], 2026)

    def test_movie_rendering_uses_current_provider_after_module_reuse(self):
        tree = ast.parse((ROOT / 'resources/lib/modules/playcount.py').read_text())
        names = ('getMovieIndicators', 'getMovieOverlay')
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        namespace = dict(punchplay=provider, traktIndicators=True)
        exec(compile(ast.Module(body=functions, type_ignores=[]), 'playcount.py', 'exec'), namespace)
        db.upsert_watched_movie('tt1756855', '1204680')
        self.assertEqual(namespace['getMovieIndicators'](), ['tt1756855'])
        self.assertEqual(namespace['getMovieOverlay']([], 'tt1756855'), '5')
        self.assertEqual(namespace['getMovieOverlay']([], 'ttother'), '4')

    def test_manual_movie_history_includes_metadata_required_by_live_api(self):
        with patch.object(provider, 'sync_account', return_value=True), patch.object(provider, '_title', return_value={'title': {'name': 'Coyote vs. Acme', 'year': 2026}}):
            provider.markMovieAsWatched('tt123', '1204680')
        body = provider._session.request.call_args.kwargs['json']
        validate(body, CONTRACT['components']['schemas']['BulkHistoryInput'])
        self.assertEqual(body['items'][0]['title'], 'Coyote vs. Acme')
        self.assertEqual(body['items'][0]['year'], 2026)
        self.assertEqual(body['items'][0]['tmdb_id'], 1204680)

    def test_movie_change_refreshes_local_indicators_without_full_account_sync(self):
        db.upsert_watched_movie('tt1756855', '1204680', 'Coyote vs. Acme', '2026')
        self.assertEqual(provider.cachesyncMovies(), ['tt1756855'])
        with patch.object(provider, '_title', return_value={'title': {'name': 'Coyote vs. Acme', 'year': 2026, 'tmdbId': 1204680}}), patch.object(provider, 'sync_account') as sync:
            provider.markMovieAsNotWatched('tt1756855', '1204680')
            self.assertEqual(provider.cachesyncMovies(), [])
            provider.markMovieAsWatched('tt1756855', '1204680')
            self.assertEqual(provider.cachesyncMovies(), ['tt1756855'])
        sync.assert_not_called()
        self.assertEqual(provider._session.request.call_count, 2)

    def test_deferred_movie_write_does_not_mark_movie_locally(self):
        provider._session.request.return_value = response({'deferred': 1, 'results': [{'status': 'deferred'}]})
        with patch.object(provider, '_title', return_value={'title': {'name': 'Movie', 'year': 2026, 'tmdbId': 550}}):
            with self.assertRaisesRegex(provider.PunchPlayError, 'queued'):
                provider.markMovieAsWatched('tt550', '550')
        self.assertEqual(db.get_watched_movies(), [])

    def test_watchlist_manager_notifies_before_targeted_refresh_without_full_sync(self):
        SETTINGS['punchplay.general.notifications'] = 'true'
        control.selectDialog.return_value = 3
        calls = Mock()
        calls.attach_mock(control.notification, 'notify')
        with patch.object(provider, '_watchlist', return_value=True), patch.object(provider, '_refresh_watchlist_cache') as refresh, patch.object(provider, 'sync_account') as sync:
            calls.attach_mock(refresh, 'refresh')
            provider.manager('The Runner', imdb='tt123', tmdb='1386315')
        self.assertEqual([c[0] for c in calls.mock_calls], ['notify', 'refresh'])
        self.assertIn('added to PunchPlay Watchlist', calls.mock_calls[0].kwargs['message'])
        sync.assert_not_called()

    def test_rating_manager_notifies_immediately_without_account_sync(self):
        SETTINGS['punchplay.general.notifications'] = 'true'
        control.selectDialog.side_effect = [10, 8]
        with patch.object(provider, 'sync_account') as sync:
            provider.manager('The Runner', imdb='tt123', tmdb='1386315')
        request = provider._session.request.call_args
        self.assertEqual(request.args[0], 'PATCH')
        self.assertEqual(request.kwargs['json'], {'rating': 8})
        self.assertIn('rated 8/10', control.notification.call_args.kwargs['message'])
        sync.assert_not_called()

    def test_rating_manager_reports_failed_api_request(self):
        SETTINGS['punchplay.general.notifications'] = 'true'
        control.selectDialog.side_effect = [10, 8]
        provider._session.request.return_value = response({'error': 'invalid_request'}, 400)
        provider.manager('The Runner', imdb='tt123', tmdb='1386315')
        message = control.notification.call_args.kwargs['message']
        self.assertIn('failed', message)
        self.assertIn('invalid_request', message)

    def test_add_to_list_notifies_before_refreshing_only_selected_list(self):
        SETTINGS['punchplay.general.notifications'] = 'true'
        control.selectDialog.side_effect = [5, 1]
        calls = Mock()
        calls.attach_mock(control.notification, 'notify')
        with patch.object(provider, 'get_lists', return_value=[{'id': 8, 'name': 'Selected list'}]), patch.object(provider, 'add_to_list', return_value=True) as add, patch.object(provider, '_finish_list_action') as finish, patch.object(provider, 'sync_account') as sync:
            calls.attach_mock(finish, 'finish')
            provider.manager('The Runner', imdb='tt123', tmdb='1386315')
        add.assert_called_once_with(8, '1386315', 'movie', 'The Runner')
        self.assertEqual([c[0] for c in calls.mock_calls], ['notify', 'finish'])
        finish.assert_called_once_with(8, True)
        sync.assert_not_called()

    def test_watchlist_payload_has_title_identifier_and_client_item_id(self):
        with patch.object(provider, '_title', return_value={'title': {'name': 'The Runner', 'tmdbId': 1386315}}):
            provider._watchlist('1386315', 'movie')
        item = provider._session.request.call_args.kwargs['json']['items'][0]
        validate(item, CONTRACT['components']['schemas']['BulkWatchlistItem'])
        self.assertEqual(item['title'], 'The Runner')
        self.assertEqual(item['tmdb_id'], 1386315)
        self.assertTrue(item['client_item_id'].startswith('umbrella:watchlist:'))

    def test_watchlist_refresh_replaces_only_watchlist_rows(self):
        db.insert_user_lists([{'list_id': '8', 'list_name': 'Other list', 'item_id': '1', 'tmdb': '550', 'title': 'Movie', 'year': '1999', 'media_type': 'movie', 'listed_at': ''}])
        with patch.object(provider, 'get_lists', return_value=[{'id': 7, 'name': 'Watchlist', 'isWatchlist': True}]), patch.object(provider, 'get_list_items', return_value=[{'id': 2, 'tmdbId': 1386315, 'title': 'The Runner', 'type': 'movie'}]):
            provider._refresh_watchlist_cache()
        self.assertEqual(db.fetch_list_items('7', 'movie')[0]['title'], 'The Runner')
        self.assertEqual(db.fetch_list_items('8', 'movie')[0]['title'], 'Movie')

    def test_manual_history_with_missing_year_does_not_send_invalid_update(self):
        with patch.object(provider, '_title', return_value={'title': {'name': 'Movie', 'year': None}}):
            with self.assertRaisesRegex(provider.PunchPlayError, 'release year'):
                provider.markMovieAsWatched('tt123', '550')
        provider._session.request.assert_not_called()

    def test_rejected_bulk_without_reason_has_explicit_fallback(self):
        provider._session.request.return_value = response({'invalid': 1, 'results': []})
        with self.assertRaisesRegex(provider.PunchPlayError, 'without providing a reason'):
            provider._bulk('history', [{'kind': 'movie'}])

    def test_unwatch_episode_deletes_only_matching_history_including_rewatches(self):
        history = [{'id': 1, 'showTmdbId': 123, 'season': 0, 'episode': 2},
                   {'id': 2, 'showTmdbId': 123, 'season': 0, 'episode': 2},
                   {'id': 3, 'showTmdbId': 123, 'season': 0, 'episode': 3}]
        with patch.object(provider, '_pages', return_value=history), patch.object(provider, '_title', return_value={'title': {'tmdbId': 123}}), patch.object(provider, '_request') as request, patch.object(provider, 'sync_account'):
            provider.markEpisodeAsNotWatched('tt123', '', 0, 2)
        self.assertEqual([c.args for c in request.call_args_list], [('/watch-history/1', 'DELETE'), ('/watch-history/2', 'DELETE')])

    def test_cached_episode_unwatch_avoids_account_scan_and_sync_lock(self):
        con = provider._connection()
        provider._put(con, 'episode_history', [
            {'id': 1, 'showTmdbId': 123, 'season': 0, 'episode': 2},
            {'id': 2, 'showTmdbId': 123, 'season': 0, 'episode': 3}])
        con.commit()
        con.close()
        with patch.object(provider, '_pages') as pages, patch.object(provider, '_account_sync_lock') as lock, patch.object(provider, '_title', return_value={'title': {'tmdbId': 123}}), patch.object(provider, '_request') as request:
            provider.markEpisodeAsNotWatched('tt123', '', 0, 2, '123')
            pages.assert_not_called()
            lock.assert_not_called()
            request.assert_called_once_with('/watch-history/1', 'DELETE')
        self.assertEqual([i['id'] for i in provider._state('episode_history')], [2])

    def test_watch_then_unwatch_retains_new_id_without_history_download(self):
        con = provider._connection()
        provider._put(con, 'episode_history', [])
        con.commit()
        con.close()
        provider._session.request.return_value = response({'results': [
            {'index': 0, 'status': 'inserted', 'id': 77, 'resolved_tmdb_id': 123}]})
        with patch.object(provider, '_title', return_value={'title': {'tmdbId': 123, 'name': 'Show', 'year': 2020}}), patch.object(provider, '_pages') as pages:
            provider.markEpisodeAsWatched('tt123', '', 1, 2, '123')
            self.assertEqual(provider._state('episode_history')[0]['id'], 77)
            with patch.object(provider, '_request') as request:
                provider.markEpisodeAsNotWatched('tt123', '', 1, 2, '123')
                request.assert_called_once_with('/watch-history/77', 'DELETE')
            pages.assert_not_called()
        self.assertEqual(provider._state('episode_history'), [])

    def test_read_only_lists_reject_manual_item_changes(self):
        for detail in [{'externalSource': 'trakt', 'isOwner': True}, {'isDynamicList': True, 'isOwner': True}, {'isOwner': False, 'isCollaborator': False}]:
            with patch.object(provider, '_request', return_value=detail) as request:
                with self.assertRaises(provider.PunchPlayError):
                    provider.add_to_list(7, '550', 'movie', 'Movie')
                self.assertEqual(request.call_count, 1)

    def test_episode_manual_changes_update_only_selected_episode_without_sync(self):
        db.upsert_watched_episode('tt123', '123', '', 0, 3, '2026-09-01T00:00:00Z')
        metadata = {'title': {'tmdbId': 123, 'name': 'Show', 'year': 2020}}
        with patch.object(provider, '_title', return_value=metadata), patch.object(provider, '_bulk'), patch.object(provider, 'sync_account') as sync:
            provider.markEpisodeAsWatched('tt123', '', 0, 2, '123')
            sync.assert_not_called()
        con = provider._connection()
        self.assertEqual(con.execute('SELECT episode FROM punchplay_watched_episodes ORDER BY episode').fetchall(), [(2,), (3,)])
        con.close()
        with patch.object(provider, '_title', return_value=metadata), patch.object(provider, '_pages', return_value=[{'id': 1, 'showTmdbId': 123, 'season': 0, 'episode': 2}]), patch.object(provider, '_request'), patch.object(provider, 'sync_account') as sync:
            provider.markEpisodeAsNotWatched('tt123', '', 0, 2, '123')
            sync.assert_not_called()
        con = provider._connection()
        self.assertEqual(con.execute('SELECT episode FROM punchplay_watched_episodes').fetchall(), [(3,)])
        con.close()

    def test_collection_confirms_before_targeted_refresh_and_never_full_syncs(self):
        SETTINGS['punchplay.general.notifications'] = 'true'
        control.selectDialog.side_effect = [7, 0]
        def refresh_resource(key, path):
            self.assertTrue(control.notification.called)
            self.assertEqual((key, path), ('collection', '/me/collection?limit=200'))
        with patch.object(provider, '_request'), patch.object(provider, '_refresh_manager_resource', side_effect=refresh_resource), patch.object(provider, 'sync_account') as sync:
            provider.manager('Movie', imdb='tt550', tmdb='550')
            sync.assert_not_called()

    def test_revoke_clears_credentials_indicators_and_cached_history(self):
        db.upsert_watched_movie('tt550', '550')
        provider.punchplayRevoke()
        self.assertFalse(provider.getPunchPlayCredentialsInfo())
        self.assertEqual(SETTINGS['indicators.alt'], '0')
        self.assertEqual(SETTINGS['scrobble.source'], '0')
        self.assertEqual(db.get_watched_movies(), [])

    def test_bookmarks_separate_movie_show_ids_and_preserve_specials(self):
        db.upsert_bookmark(title='Movie', imdb='ttmovie', tmdb='550', percent_played='20')
        db.upsert_bookmark(tvshowtitle='Show', title='Special', imdb='ttshow', tmdb='550', season='0', episode='1', percent_played='40')
        self.assertEqual(db.fetch_bookmarks('ttmovie', '550'), '20')
        self.assertEqual(db.fetch_bookmarks('ttshow', '550', season=0, episode=1), '40')
        db.delete_bookmark('ttshow', tmdb='550', season=0, episode=1)
        self.assertEqual(db.fetch_bookmarks('ttshow', '550', season=0, episode=1), '0')
        self.assertEqual(db.fetch_bookmarks('ttmovie', '550'), '20')

    def test_manager_watches_titles_with_only_tmdb_identifiers(self):
        with patch.object(provider, '_history_write') as write:
            self.assertTrue(provider._watch('movie', 'Movie', None, None, None, None, False, False, '550'))
            write.assert_called_once_with('movie', imdb=None, tmdb='550', remove=False)

    def test_refresh_connection_failure_is_reported_as_provider_error(self):
        with patch.object(provider._session, 'post', side_effect=provider.requests.ConnectionError()):
            with self.assertRaises(provider.PunchPlayError):
                provider._refresh(failed_token=provider._tokens()['access_token'])

    def test_existing_provider_context_menu_conditions_include_punchplay_once(self):
        tree = ast.parse((ROOT / 'resources/lib/menus/episodes.py').read_text())
        conditions = []
        for n in ast.walk(tree):
            if isinstance(n, ast.If):
                names = {x.id for x in ast.walk(n.test) if isinstance(x, ast.Name)}
                if 'traktProgress' in names and 'scrobProgress' in names:
                    self.assertIn('punchplayProgress', names)
                    conditions.append(n)
                if 'traktProgress' in names and 'punchplayProgress' in names:
                    self.assertIn('scrobProgress', names)
        self.assertEqual(len(conditions), 2)

    def test_library_menus_render_last_page_without_continuation(self):
        SETTINGS['punchplay.paginate.lists'] = 'true'
        for name in ('movies', 'tvshows'):
            tree = ast.parse((ROOT / ('resources/lib/menus/%s.py' % name)).read_text())
            function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'punchplay_library')
            namespace = dict(punchplay=provider, getSetting=control.setting, parse_qsl=parse_qsl,
                             urlsplit=urlsplit, quote_plus=quote_plus, log_utils=log)
            exec(compile(ast.Module(body=[function], type_ignores=[]), name, 'exec'), namespace)
            menu = Mock()
            menu.page_limit = 2
            items = [{'tmdb': str(i), 'title': 'Title %s' % i, 'year': 2020} for i in range(4)]
            with patch.object(provider, 'get_library_items', return_value=items):
                result = namespace['punchplay_library'](menu, 'collection', url='library?page=2')
            self.assertEqual([i['tmdb'] for i in result], ['2', '3'])
            self.assertTrue(all(i['next'] == '' for i in result))

    def test_tv_indicators_read_local_records_with_reused_invoker(self):
        tree = ast.parse((ROOT / 'resources/lib/modules/playcount.py').read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'getTVShowIndicators')
        namespace = {'punchplay': provider, 'punchplayIndicators': False}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'playcount', 'exec'), namespace)
        with patch.object(provider, 'getPunchPlayIndicatorsInfo', return_value=True), patch.object(provider, 'syncTVShows', return_value=['fresh']) as local, patch.object(provider, 'cachesyncTVShows') as cached:
            self.assertEqual(namespace['getTVShowIndicators'](), ['fresh'])
            self.assertEqual(namespace['getTVShowIndicators'](refresh=True), ['fresh'])
            self.assertEqual(local.call_count, 2)
            cached.assert_not_called()

    def test_settings_menu_and_router_contracts(self):
        settings = ET.parse(ROOT / 'resources/settings.xml')
        ids = [n.attrib['id'] for n in settings.findall('.//setting')]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn('punchplay.clientid', ids)
        self.assertNotIn('punchplay.clientsecret', ids)
        username = next(n for n in settings.findall('.//setting') if n.attrib['id'] == 'punchplay.username')
        self.assertEqual(username.findtext('enable'), 'false')
        for name in ('indicators.alt', 'scrobble.source'):
            element = next(n for n in settings.findall('.//setting') if n.attrib['id'] == name)
            self.assertEqual([o.text for o in element.findall('.//option')], ['0','1','2','3','4','5','6','7'])
        module = importlib.import_module('resources.lib.database.menu')
        self.assertIn('mymovies_punchplay', module.MENU_DEFAULTS)
        self.assertIn('mytvshows_punchplay', module.MENU_DEFAULTS)
        router = (ROOT / 'resources/lib/modules/router.py').read_text()
        for row in module._MYMOVIES_PUNCHPLAY_DEFAULTS + module._MYTVSHOWS_PUNCHPLAY_DEFAULTS:
            self.assertIn("action == '%s'" % row[2].split('&')[0], router)
        self.assertIn("action == 'tools_forcePunchPlaySync'", router)
        functions = set(vars(provider))
        for p in (ROOT / 'resources/lib').rglob('*.py'):
            if 'punchplay' not in p.read_text(encoding='utf-8-sig'):
                continue
            tree = ast.parse(p.read_text(encoding='utf-8-sig'))
            for n in ast.walk(tree):
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == 'punchplay':
                    self.assertIn(n.attr, functions, (p, n.attr))


if __name__ == '__main__':
    unittest.main()
