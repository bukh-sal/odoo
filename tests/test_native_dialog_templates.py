from pathlib import Path
import json,unittest
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT
BASE=Path('framework_addons/web/static/src')
SVG='{http://www.w3.org/2000/svg}'
class DialogTemplate(unittest.TestCase):
 def test_shared_controls_use_exact_existing_pinned_svg_geometry_and_names(self):
  text=(ROOT/BASE/'interface/icons/lucide.js').read_text(encoding='utf8');nodes=json.loads(text.split('export const ICON_NODES = ',1)[1].strip().removesuffix(';'))
  seen=[]
  for filename in ['core/dialog/dialog.xml','core/errors/error_dialogs.xml']:
   tree=ET.parse(TARGET/BASE/filename)
   for icon in tree.findall('.//'+SVG+'svg'):
    name=icon.get('data-mp-dialog-icon')
    if name is None:continue
    seen.append(name);actual=[dict(tag=child.tag.removeprefix(SVG),attrs=child.attrib) for child in icon];expected=[dict(tag=row['tag'],attrs=row['attrs']) for row in nodes[name]];self.assertEqual(actual,expected,name);self.assertEqual(icon.get('aria-hidden'),'true');self.assertEqual(icon.get('focusable'),'false');self.assertEqual(icon.get('viewBox'),'0 0 24 24');self.assertEqual(icon.get('stroke'),'currentColor');self.assertEqual(icon.get('stroke-width'),'1.8')
  self.assertCountEqual(seen,['arrow-left','maximize-2','x','copy'])
 def test_header_keeps_legacy_native_slot_callers_and_actual_callbacks_without_component_lookup(self):
  tree=ET.parse(TARGET/BASE/'core/dialog/dialog.xml');header=tree.find(".//t[@t-name='web.Dialog.header']");self.assertIsNotNone(header);self.assertIsNotNone(header.find(".//h4[@t-att-id=\"id + '_title'\"]"))
  buttons=header.findall('.//button');self.assertEqual([b.get('aria-label') for b in buttons],['Close','Expand','Close']);self.assertEqual([b.get('t-on-click') for b in buttons],['dismiss','onExpand','dismiss']);self.assertTrue(all(b.get('tabindex')=='-1' for b in buttons));self.assertIn('btn-close',buttons[-1].get('class'));self.assertIn('background-image: none',buttons[-1].get('style'));self.assertFalse(header.findall('.//Icon'))
  for filename in ['views/view_dialogs/select_create_dialog.xml','webclient/actions/action_dialog.xml']:
   text=(ROOT/BASE/filename).read_text(encoding='utf8');self.assertIn('web.Dialog.header',text)
  self.assertIsNotNone(tree.find(".//t[@t-slot='header']"));self.assertIsNotNone(tree.find(".//t[@t-slot='footer']"));self.assertIn('filter: none',buttons[-1].get('style'));self.assertIn('color: inherit',buttons[-1].get('style'))
 def test_copy_action_has_a_name_and_generic_fault_does_not_offer_blind_retry(self):
  tree=ET.parse(TARGET/BASE/'core/errors/error_dialogs.xml');copy=tree.find(".//button[@t-ref='copyButton']");self.assertEqual(copy.get('aria-label'),'Copy technical details');self.assertEqual(copy.get('t-on-click'),'onClickClipboard');self.assertFalse(copy.findall('.//span[@class="fa fa-clipboard"]'))
  generic=tree.find(".//t[@t-name='web.ErrorDialog']");text=' '.join(generic.itertext());self.assertIn('unsaved changes',text);self.assertNotIn('try again',text.lower());self.assertNotIn('retry',text.lower());self.assertIsNotNone(generic.find(".//div[@t-if='state.showTraceback']"))
if __name__=='__main__':unittest.main()
