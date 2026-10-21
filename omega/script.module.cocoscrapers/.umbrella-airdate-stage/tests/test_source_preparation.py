import ast
from pathlib import Path
from threading import Event, Thread
from time import sleep, time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

TREE = ast.parse(Path('resources/lib/modules/sources.py').read_text(encoding='utf-8'))


class SourcePreparationTests(unittest.TestCase):
    def setUp(self):
        method = next(n for n in ast.walk(TREE) if isinstance(n, ast.FunctionDef) and n.name == 'prepareSources_dialog')
        self.control = SimpleNamespace(monitor=Mock(), sleep=lambda ms: sleep(ms / 1000))
        self.control.monitor.abortRequested.return_value = False
        self.log = Mock()
        ns = dict(Thread=Thread, time=time, control=self.control, log_utils=self.log)
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<preparation>', 'exec'), ns)
        self.prepare = ns['prepareSources_dialog']
        self.dialog = Mock()
        self.dialog.iscanceled.return_value = False
        self.source = SimpleNamespace(prepareSources=Mock(), getAliasTitles=Mock(return_value=[{'title': 'Alias'}]))

    def test_success_keeps_aliases(self):
        self.assertEqual(self.prepare(self.source, self.dialog, 'tt123', 'movie'), [{'title': 'Alias'}])
        self.source.prepareSources.assert_called_once()
        self.source.getAliasTitles.assert_called_once_with('tt123', 'movie')

    def stalled(self, cancelled=False, abort=False):
        entered, release, finished = Event(), Event(), Event()
        def lookup(*args):
            entered.set()
            release.wait(2)
            finished.set()
            return [{'title': 'Late'}]
        self.source.getAliasTitles.side_effect = lookup
        self.dialog.iscanceled.side_effect = lambda: entered.is_set() and cancelled
        self.control.monitor.abortRequested.side_effect = lambda: entered.is_set() and abort
        try:
            result = self.prepare(self.source, self.dialog, 'tt123', 'episode', timeout=.1)
            self.assertTrue(entered.is_set())
            self.assertFalse(finished.is_set())
            self.assertEqual(result, None if cancelled or abort else [])
        finally:
            release.set()
            self.assertTrue(finished.wait(1))

    def test_stalled_alias_lookup_can_be_cancelled(self): self.stalled(cancelled=True)
    def test_stalled_alias_lookup_honors_kodi_shutdown(self): self.stalled(abort=True)
    def test_stalled_alias_lookup_times_out(self): self.stalled()

    def test_cache_workers_do_not_publish_to_active_source_list(self):
        method = next(n for n in ast.walk(TREE) if isinstance(n, ast.FunctionDef) and n.name == 'checkStatus')
        entered, release = Event(), Event()
        source = SimpleNamespace(filter=[], sources=[])
        ns = dict(deepcopy_sources=[{'hash': 'abc'}], hashList=['abc'], deepcopy=__import__('copy').deepcopy,
                  hoster_sources=[], cache_results=[], log_utils=Mock(), self=source)
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<cache-check>', 'exec'), ns)
        def check(items, hashes):
            entered.set()
            release.wait(2)
            return items
        worker = Thread(target=ns['checkStatus'], args=(check, 'TorBox', []))
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            source.filter = [{'name': 'new search'}]
        finally:
            release.set()
            worker.join(1)
        self.assertEqual(source.filter, [{'name': 'new search'}])
        self.assertEqual(ns['cache_results'][0][0]['debrid'], 'TorBox')

    def test_provider_check_wait_is_cancellable_and_bounded(self):
        method = next(n for n in ast.walk(TREE) if isinstance(n, ast.FunctionDef) and n.name == 'sourcesFilter')
        wait = next(n for n in method.body if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == 'threads')
        # Run the real wait loop without unrelated sorting/UI setup.
        wrapper = ast.FunctionDef(name='wait_for_checks', args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                                  body=[wait], decorator_list=[])
        for cancelled in (False, True):
            with self.subTest(cancelled=cancelled):
                release = Event()
                worker = Thread(target=lambda: release.wait(2))
                source = SimpleNamespace(sources=[{'name': 'old'}])
                clock = iter([0, 61])
                self.dialog.iscanceled.return_value = cancelled
                window = Mock()
                ns = dict(threads=[worker], time=lambda: next(clock), control=self.control,
                          progressDialog=self.dialog, self=source, homeWindow=window, log_utils=self.log)
                module = ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[]))
                exec(compile(module, '<provider-wait>', 'exec'), ns)
                try:
                    ns['wait_for_checks']()
                    self.assertTrue(worker.is_alive())
                    if cancelled:
                        self.assertEqual(source.sources, [])
                        window.clearProperty.assert_called_with('umbrella.window_keep_alive')
                    else:
                        self.assertEqual(source.sources, [{'name': 'old'}])
                        self.log.log.assert_called()
                finally:
                    release.set()
                    worker.join(1)


if __name__ == '__main__': unittest.main()
