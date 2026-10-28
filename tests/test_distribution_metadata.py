"""Regression for real base bootstrap failure after removing addon discovery."""
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from tools.build_distribution import seed_category_metadata


class CategoryMetadataTest(unittest.TestCase):
    def test_retained_catalog_references_resolve_without_excluded_addons(self):
        source = Path(__file__).resolve().parents[1] / "odoo/addons/base/data"
        with tempfile.TemporaryDirectory() as directory:
            categories = Path(directory) / "categories.xml"
            original = (source / "ir_module_category_data.xml").read_text()
            categories.write_text(original)
            missing = seed_category_metadata(categories, source / "ir_module_module.xml")
            self.assertIn("module_category_services_timesheets", missing)
            known = {r.attrib["id"].removeprefix("base.") for r in ET.parse(categories).iter("record")}
            for field in ET.parse(source / "ir_module_module.xml").iter("field"):
                if field.attrib.get("name") == "category_id":
                    self.assertIn(field.attrib["ref"].removeprefix("base."), known)
            self.assertEqual(seed_category_metadata(categories, source / "ir_module_module.xml"), [])
            self.assertIn('<field name="name">Technical</field>', categories.read_text())


if __name__ == "__main__":
    unittest.main()
