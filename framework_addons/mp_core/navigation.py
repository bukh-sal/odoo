"""Current workspace navigation projected onto accessible native menu actions."""
from copy import deepcopy


def native_menus(menus, installations, capabilities, resolve_action):
    """Keep installed app trees after feature, page permission and native ACL checks."""
    result = {"root": {**menus["root"], "children": []}}
    for plugin, manifest in installations:
        ui = manifest["ui"]
        allowed = set(capabilities(plugin, manifest))
        pages = [page for page in ui["pages"]
                 if page.get("kind") == "native_view"
                 and (page["permission"] in allowed or plugin + ":" + page["permission"] in allowed)]
        actions = {resolve_action(page["action_ref"]) for page in pages}
        actions.discard(None)
        addon = manifest["runtime"].get("addon_name")
        if not addon or not actions:
            continue
        blocked = {resolve_action(page["action_ref"]) for page in ui["pages"]
                   if page.get("kind") == "native_view" and page not in pages}
        blocked.discard(None)
        for root_id in menus["root"]["children"]:
            root = menus.get(root_id, menus.get(str(root_id)))
            if not root or not root["xmlid"].startswith(addon + ".") or root["actionID"] not in actions:
                continue
            def keep(ident, seen):
                row = menus.get(ident, menus.get(str(ident)))
                if (not row or ident in seen or row["appID"] != root_id
                        or not row["xmlid"].startswith(addon + ".") or row["actionID"] in blocked):
                    return
                seen.add(ident)
                result[ident] = deepcopy(row)
                result[ident]["children"] = []
                for child in row["children"]:
                    if child in seen:
                        continue
                    keep(child, seen)
                    if child in result:
                        result[ident]["children"].append(child)
            keep(root_id, set())
            if root_id in result:
                result["root"]["children"].append(root_id)
                result[root_id]["pluginID"] = plugin
                result[root_id]["appIcon"] = next(
                    (item["icon"] for item in ui["navigation"] if item.get("icon")), "cube")
    return result
