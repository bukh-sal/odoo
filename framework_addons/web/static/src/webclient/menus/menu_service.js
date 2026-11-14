import { session } from "@web/session";
import { browser } from "../../core/browser/browser";
import { registry } from "../../core/registry";

const loadMenusUrl = `/web/webclient/load_menus`;

export const menuService = {
    dependencies: ["action"],
    async start(env) {
        let currentAppId;
        let menusData;

        const fetchMenus = async (reload) => {
            if (!reload && odoo.loadMenusPromise) {
                return odoo.loadMenusPromise;
            }
            const res = await browser.fetch(loadMenusUrl, { cache: "no-store" });
            if (!res.ok) {
                throw new Error("Error while fetching menus");
            }
            return res.json();
        };
        const source = registry.category("menu_sources").get("workspace", null);
        let sourceError = false;
        let sourceGeneration = 0;
        const readScopedMenus = async () => {
            try {
                const menus = await source();
                return { menus, error: false };
            } catch {
                return { menus: { root: { id: "root", children: [] } }, error: true };
            }
        };
        const storedMenus = browser.localStorage.getItem("webclient_menus");
        const storedMenusVersion = browser.localStorage.getItem("webclient_menus_version");

        if (source) {
            const initial = await readScopedMenus();
            menusData = initial.menus;
            sourceError = initial.error;
        } else if (storedMenus && storedMenusVersion === session.registry_hash) {
            fetchMenus().then((res) => {
                if (res) {
                    const fetchedMenus = JSON.stringify(res);
                    if (fetchedMenus !== storedMenus) {
                        try {
                            browser.localStorage.setItem("webclient_menus", fetchedMenus);
                        } catch (error) {
                            console.error("Error while storing menus in localStorage", error);
                        }
                        menusData = res;
                        env.bus.trigger("MENUS:APP-CHANGED");
                    }
                }
            });
            menusData = JSON.parse(storedMenus);
        } else {
            menusData = await fetchMenus();
            if (menusData) {
                try {
                    browser.localStorage.setItem("webclient_menus_version", session.registry_hash);
                    browser.localStorage.setItem("webclient_menus", JSON.stringify(menusData));
                } catch (error) {
                    console.error("Error while storing menus in localStorage", error);
                }
            }
        }

        function _getMenu(menuId) {
            return menusData[menuId];
        }
        async function refreshScopedMenus() {
            const generation = ++sourceGeneration;
            const next = await readScopedMenus();
            if (generation !== sourceGeneration) return false;
            menusData = next.menus;
            sourceError = next.error;
            env.bus.trigger("MENUS:APP-CHANGED");
            return true;
        }
        function setCurrentMenu(menu) {
            menu = typeof menu === "number" ? _getMenu(menu) : menu;
            if (menu && menu.appID !== currentAppId) {
                currentAppId = menu.appID;
                browser.sessionStorage.setItem("menu_id", currentAppId);
                env.bus.trigger("MENUS:APP-CHANGED");
            }
        }

        return {
            get unavailable() { return sourceError; },
            getAll() {
                return Object.values(menusData);
            },
            getApps() {
                return this.getMenu("root").children.map((mid) => this.getMenu(mid));
            },
            getMenu: _getMenu,
            getCurrentApp() {
                if (!currentAppId) {
                    return;
                }
                return this.getMenu(currentAppId);
            },
            getMenuAsTree(menuID) {
                const menu = this.getMenu(menuID);
                if (!menu.childrenTree) {
                    menu.childrenTree = menu.children.map((mid) => this.getMenuAsTree(mid));
                }
                return menu;
            },
            async selectMenu(menu) {
                const id = typeof menu === "number" ? menu : menu?.id;
                if (source) {
                    if (!await refreshScopedMenus()) return;
                }
                menu = this.getMenu(id);
                if (!menu?.actionID) {
                    return;
                }
                await env.services.action.doAction(menu.actionID, {
                    clearBreadcrumbs: true,
                    onActionReady: () => {
                        setCurrentMenu(menu);
                    },
                });
            },
            setCurrentMenu,
            async reload() {
                if (source) return refreshScopedMenus();
                if (fetchMenus) {
                    menusData = await fetchMenus(true);
                    env.bus.trigger("MENUS:APP-CHANGED");
                }
            },
        };
    },
};

registry.category("services").add("menu", menuService);
