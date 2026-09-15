"""Verify the properties that expose Kodi widget context actions."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class WidgetContextTests(unittest.TestCase):
    def test_manager_properties_follow_settings_at_startup_and_after_changes(self):
        tree = ast.parse((ROOT / 'service.py').read_text(encoding='utf-8-sig'))
        properties = ast.literal_eval(next(n.value for n in tree.body if isinstance(n, ast.Assign)
                                          and any(isinstance(t, ast.Name) and t.id == 'properties' for t in n.targets)))
        managers = ['custom', 'floppy', 'scrob', 'punchplay']
        expected = ['context.umbrella.%sManager' % name for name in managers]
        for name in expected:
            self.assertIn(name, properties)
        manifest = ET.parse(ROOT / 'addon.xml')
        for manager, prop in zip(managers, expected):
            item = next(n for n in manifest.findall('.//item')
                        if n.get('library', '').endswith('%sManager.py' % manager))
            self.assertIn('Property(%s)' % prop, item.findtext('visible'))
        monitor = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SettingsMonitor')
        for method_name in ('__init__', 'onSettingsChanged'):
            method = next(n for n in monitor.body if isinstance(n, ast.FunctionDef) and n.name == method_name)
            loop = next(n for n in ast.walk(method) if isinstance(n, ast.For)
                        and isinstance(n.iter, ast.Name) and n.iter.id == 'properties')
            state = {}
            settings = {prop: 'true' for prop in expected}
            window = SimpleNamespace(setProperty=lambda key, value: state.__setitem__(key, value),
                                     clearProperty=lambda key: state.pop(key, None))
            namespace = dict(properties=properties, window=window,
                             control=SimpleNamespace(setting=lambda key: settings.get(key, 'false')))
            code = compile(ast.Module(body=[loop], type_ignores=[]), 'service.py', 'exec')
            exec(code, namespace)
            self.assertTrue(all(state[prop] == 'true' for prop in expected))
            settings.update({prop: 'false' for prop in expected})
            exec(code, namespace)
            self.assertTrue(all(prop not in state for prop in expected))


if __name__ == '__main__':
    unittest.main()
