"""Check prepared/applied Nimbus XML and atomic helper publication."""
import ast
import copy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

SKIN = Path(__file__).resolve().parents[1]
HELPER = SKIN.parent / 'script.nimbus.helper'
STAGE = Path(__file__).parent / 'nimbus_fix_stage'


def source(path):
    return path.read_text(encoding='utf-8-sig')


class NimbusXMLTests(unittest.TestCase):
    def test_all_xml_parses_and_condition_brackets_balance(self):
        for path in SKIN.rglob('*.xml'):
            with self.subTest(path=path.name):
                root = ET.fromstring(source(path))
                for node in root.iter():
                    if node.tag in ('visible', 'enable', 'condition', 'expression'):
                        value = node.text or ''
                        self.assertEqual(value.count('['), value.count(']'), (path, value))

    def test_list_layouts_expand_only_supported_controls(self):
        roots = {p.name: ET.fromstring(source(p)) for p in (SKIN / 'xml').glob('*.xml')}
        definitions = {e.get('name'): e for root in roots.values() if root.tag == 'includes'
                       for e in root.findall('include') if e.get('name')}
        supported = {'image', 'label', 'textbox', 'group', 'multiimage', 'progress',
                     'game', 'gamewindow', 'gamecontroller', 'gamecontrollerlist'}
        def visit(node, active=()):
            if node.tag == 'control': self.assertIn(node.get('type'), supported)
            if node.tag == 'include' and not node.get('name'):
                name = node.get('content') or (node.text or '').strip()
                if name in definitions and name not in active:
                    target = definitions[name].find('definition')
                    visit(target if target is not None else definitions[name], active + (name,))
            for child in node: visit(child, active)
        for filename, root in roots.items():
            for layout in list(root.iter('focusedlayout')) + list(root.iter('itemlayout')):
                with self.subTest(file=filename): visit(layout)

    def test_focus_hooks_are_on_containers_and_scroll_timers_reset(self):
        root = ET.fromstring(source(SKIN / 'xml/Includes_Home.xml'))
        for name, action in [('WidgetListPoster', 'ClearProperty(LandscapeWidgetFocused,Home)'),
                             ('WidgetListLandscape', 'SetProperty(LandscapeWidgetFocused,true,Home)')]:
            container = root.find("include[@name='%s']/definition/control[@type='fixedlist']" % name)
            self.assertIsNotNone(container)
            self.assertIn(action, [e.text for e in container.findall('onfocus')])
        timers = ET.fromstring(source(SKIN / 'xml/Timers.xml'))
        for name in ('wall_scroll_timer', 'posterflow_scroll_timer', 'autoplay_trailer_timer'):
            timer = next(t for t in timers if t.findtext('name') == name)
            self.assertIn('OnNext', timer.findtext('reset'))

    @unittest.skipUnless(HELPER.exists(), 'Companion helper not installed')
    def test_placeholder_templates_have_a_real_child_for_kodi(self):
        parser = lambda: ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        path = HELPER / 'resources/lib/modules/xmls.py'
        ns = {}
        exec(compile(source(path), str(path), 'exec'), ns)
        for name in ('default_widget', 'default_main_menu', 'default_history'):
            root = ET.fromstring(ns[name].format(includes_type='TestInclude'), parser=parser())
            self.assertTrue(len(root.find('include')))
        for name in ('script-nimbus-main_menu_movies.xml', 'script-nimbus-widget_movies.xml'):
            root = ET.fromstring(source(SKIN / 'xml' / name), parser=parser())
            self.assertTrue(len(root.find('include')))


@unittest.skipUnless(HELPER.exists(), 'Companion helper not installed')
class NimbusAtomicWriteTests(unittest.TestCase):
    def setUp(self):
        path = HELPER / 'resources/lib/modules/cpath_maker.py'
        node = next(n for n in ast.parse(source(path)).body if isinstance(n, ast.FunctionDef) and n.name == 'write_skin_xml')
        self.ns = dict(ET=ET, os=os, tempfile=tempfile, xbmcvfs=SimpleNamespace(translatePath=lambda p: p))
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), self.ns)

    def test_success_replaces_complete_xml_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'menu.xml'
            path.write_text('<old/>')
            self.ns['write_skin_xml'](str(path), '<includes><include name="New"><!-- empty --></include></includes>')
            self.assertEqual(ET.parse(path).getroot().tag, 'includes')
            self.assertEqual(list(Path(folder).iterdir()), [path])

    def test_failed_replace_and_bad_xml_preserve_previous_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'menu.xml'
            path.write_text('<old/>')
            with patch.object(os, 'replace', side_effect=OSError('write failed')):
                with self.assertRaises(OSError): self.ns['write_skin_xml'](str(path), '<new/>')
            with self.assertRaises(ET.ParseError): self.ns['write_skin_xml'](str(path), '<broken>')
            self.assertEqual(path.read_text(), '<old/>')
            self.assertEqual(list(Path(folder).iterdir()), [path])


if __name__ == '__main__':
    unittest.main()
