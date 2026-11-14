"""Workspace projection over actual native menu producer shapes."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "navigation_projection", Path(__file__).parents[1] / "framework_addons/mp_core/navigation.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NavigationProjection(unittest.TestCase):
    def setUp(self):
        def row(ident, parent, action, xmlid, children=()):
            return dict(id=ident, appID=parent, actionID=action, xmlid=xmlid, children=list(children), name=xmlid)
        self.menus = {
            "root": dict(id="root", children=[1, 4]),
            1: row(1, 1, 10, "owned.home", [2, 3]),
            2: row(2, 1, 11, "owned.people"),
            3: row(3, 1, 12, "foreign.injected"),
            4: row(4, 4, 20, "other.home"),
        }
        self.manifest = dict(runtime=dict(addon_name="owned"), ui=dict(
            pages=[dict(id="home", kind="native_view", permission="work.read", action_ref="owned.action")],
            navigation=[dict(icon="tasks")]))

    def project(self, capabilities=("app:work.read",), installations=None):
        return module.native_menus(self.menus, installations if installations is not None else [("app", self.manifest)],
                                   lambda *_: capabilities, lambda ref: {"owned.action": 10, "owned.people": 11}.get(ref))

    def test_allowed_tree_keeps_native_identity_and_input(self):
        before = copy.deepcopy((self.menus, self.manifest))
        result = self.project()
        self.assertEqual(result["root"]["children"], [1])
        self.assertEqual(result[1]["children"], [2])
        self.assertEqual(result[1]["pluginID"], "app")
        self.assertEqual(result[1]["appIcon"], "tasks")
        self.assertEqual(result[2], self.menus[2])
        self.assertEqual((self.menus, self.manifest), before)

    def test_absent_or_unpermitted_installation_is_empty(self):
        self.assertEqual(self.project(installations=[])["root"]["children"], [])
        self.assertEqual(self.project(capabilities=[])["root"]["children"], [])

    def test_unresolved_entry_does_not_guess_an_action(self):
        self.manifest["ui"]["pages"][0]["action_ref"] = "missing.action"
        self.assertEqual(self.project()["root"]["children"], [])

    def test_declared_child_permission_cannot_inherit_root_read(self):
        self.manifest["ui"]["pages"].append(dict(
            id="people", kind="native_view", permission="work.admin", action_ref="owned.people"))
        self.assertEqual(self.project()[1]["children"], [])

    def test_cached_string_keys_and_cycles_do_not_expand_scope(self):
        self.menus[2]["children"] = [1]
        self.menus = {str(key): value for key, value in self.menus.items()}
        self.assertEqual(self.project()[2]["children"], [])


if __name__ == "__main__":
    unittest.main()
