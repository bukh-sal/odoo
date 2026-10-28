/** G1-only neutral root and concentrated native compatibility adapter. */
import { Component, xml, useState, useRef, onMounted, onWillDestroy } from '@odoo/owl';
import { startWebClient } from '@web/start';
import { rpc } from '@web/core/network/rpc';
import { View } from '@web/views/view';
import { MainComponentsContainer } from '@web/core/main_components_container';
import { mount } from './plain_page';

let activeWorkspace = null;
let generation = 0;
let staleDiscarded = 0;
const nativeRPC = rpc._rpc;
const abortError = () => new DOMException('Obsolete page context', 'AbortError');
// This bundle replaces only the root entrypoint. Native widgets retain their
// private transport; it carries the same validated workspace as the public SDK.
// Disable the native RPC cache in the proof rather than sharing unscoped keys.
rpc._rpc = function (url, params, settings = {}) {
    const captured = generation;
    const pending = nativeRPC.call(this, url, params, {
        ...settings, cache: false,
        headers: {...settings.headers, ...(activeWorkspace ? {'X-MP-Workspace': activeWorkspace} : {})},
    });
    const guarded = pending.then(value => {
        if (captured !== generation) { staleDiscarded++; throw abortError(); }
        return value;
    });
    guarded.abort = (...args) => pending.abort(...args);
    return guarded;
};

class FeasibilityHost extends Component {
    static components = { View, MainComponentsContainer };
    static props = {};
    static template = xml`
        <div class="mp_feas_root">
            <header><strong>Modular Platform</strong><span>Feasibility environment</span>
                <label>Workspace <select t-on-change="switchWorkspace" t-att-value="state.workspace">
                    <option value="">Select a workspace</option>
                    <option t-foreach="state.workspaces" t-as="space" t-key="space.public_id" t-att-value="space.public_id" t-esc="space.name"/>
                </select></label>
                <span t-esc="state.role"/>
            </header>
            <nav aria-label="Proof navigation">
                <a href="#" t-on-click.prevent="openCustom">Custom page</a>
                <a href="#" t-on-click.prevent="openNative">Native records</a>
                <a href="#" t-on-click.prevent="openDetail">Route detail</a>
            </nav>
            <div class="mp_proof" role="status" t-esc="state.diagnostic"/>
            <main>
                <p t-if="state.error" role="alert" t-esc="state.error"/>
                <div t-ref="custom" t-att-style="state.page === 'custom' ? '' : 'display:none'"/>
                <t t-if="state.page === 'native' and state.nativeProps"><View t-key="state.generation" t-props="state.nativeProps"/></t>
            </main>
            <MainComponentsContainer/>
        </div>`;

    setup() {
        this.state = useState({workspaces: [], workspace: '', page: '', role: '', nativeProps: null, generation: 0, diagnostic: '', error: ''});
        this.custom = useRef('custom');
        this.mountCount = 0;
        this.disposeCount = 0;
        this.onPop = () => this.activate().catch(error => this.showError(error));
        onMounted(async () => {
            window.addEventListener('popstate', this.onPop);
            this.state.workspaces = (await this.json('/mp/feas/workspaces')).data;
            await this.activate();
            this.authorityTimer = setInterval(() => this.refreshAuthority(), 5000);
        });
        onWillDestroy(() => {
            window.removeEventListener('popstate', this.onPop);
            clearInterval(this.authorityTimer);
            this.retire();
        });
    }

    async json(path, body, signal, workspace = activeWorkspace) {
        const response = await fetch(path, {method: body ? 'POST' : 'GET', cache: 'no-store', signal,
            headers: {...(workspace ? {'X-MP-Workspace': workspace} : {}), ...(body ? {'Content-Type':'application/json','X-CSRFToken':this.csrf} : {})},
            ...(body ? {body:JSON.stringify(body)} : {})});
        const result = await response.json();
        if (!response.ok) throw new Error(result.error?.code || `HTTP ${response.status}`);
        return result;
    }
    diagnostic() {
        this.state.diagnostic = `mounts=${this.mountCount} disposes=${this.disposeCount} active=${this.mounted ? 1 : 0} generation=${generation} stale_discarded=${staleDiscarded}`;
    }
    retire() {
        this.controller?.abort();
        if (this.mounted) { this.mounted.dispose(); this.mounted = null; this.disposeCount++; }
        this.state.nativeProps = null;
    }
    showError(error) { if (error.name !== 'AbortError') this.state.error = error.message; }
    async navigate(page, workspace = this.state.workspace, detail = '') {
        const url = new URL(`/app/org.example.feasibility/${page}`, location.origin);
        if (workspace) url.searchParams.set('workspace', workspace);
        if (detail) url.searchParams.set('detail', detail);
        history.pushState({}, '', url);
        await this.activate();
    }
    openCustom() { return this.navigate('custom'); }
    openNative() { return this.navigate('native'); }
    openDetail() { return this.navigate('custom', this.state.workspace, 'second'); }
    switchWorkspace(event) { return this.navigate(this.state.page || 'custom', event.target.value); }

    async refreshAuthority() {
        if (!activeWorkspace || this.state.error || this.checkingAuthority) return;
        this.checkingAuthority = true;
        const captured = generation;
        try {
            const context = (await this.json('/mp/feas/context', null, this.controller.signal)).data;
            if (captured === generation && context.policy_generation !== this.policyGeneration) await this.activate(true);
        } catch (error) {
            if (captured === generation && error.name !== 'AbortError') {
                this.retire(); generation++; this.state.role = ''; this.showError(error); this.diagnostic();
            }
        } finally { this.checkingAuthority = false; }
    }

    async activate(force = false) {
        const url = new URL(location.href);
        const workspace = url.searchParams.get('workspace');
        const page = url.pathname.split('/')[3];
        const route = Object.freeze({pageId:page, query:Object.freeze(Object.fromEntries(url.searchParams))});
        if (!force && workspace === activeWorkspace && page === 'custom' && this.mounted) {
            await this.mounted.updateRoute(route);
            return;
        }
        this.retire();
        generation++;
        const captured = generation;
        this.state.generation = generation;
        activeWorkspace = workspace;
        this.state.workspace = workspace || '';
        this.state.page = page;
        this.state.error = '';
        this.state.role = '';
        this.controller = new AbortController();
        const signal = this.controller.signal;
        try {
            if (!['custom','native'].includes(page)) throw new Error('Page unavailable');
            if (!workspace) throw new Error('Select an explicit workspace before mounting');
            const context = (await this.json('/mp/feas/context', null, signal)).data;
            if (captured !== generation) throw abortError();
            this.csrf = context.csrf_token;
            this.policyGeneration = context.policy_generation;
            this.state.role = context.role;
            if (page === 'native') {
                // Resolve the declared native action, then translate its list
                // descriptor into the upstream View component. No native env
                // crosses into the custom page's host object.
                const action = await rpc('/web/action/load', {action_id:'mp_feas.action_records'});
                if (captured !== generation) throw abortError();
                const list = action.views.find(view => view[1] === 'list');
                this.state.nativeProps = {resModel:action.res_model, type:'list', viewId:list[0] || false, domain:[], context:{}, display:{controlPanel:true}};
            } else {
                const hostContext = Object.freeze({principalId:context.principal_id, workspaceId:workspace, role:context.role, generation:captured});
                const host = Object.freeze({context:() => hostContext, services:Object.freeze({call: async (alias, method, input, options = {}) => {
                    if (alias !== 'fixture') throw new Error('BINDING_UNAVAILABLE');
                    const result = await this.json('/mp/feas/gateway', {operation:method, ...input}, signal, workspace);
                    // Deliberate G1 race fixture: transport completed before
                    // switching, callback delivered later; tests stale filtering.
                    if (options.proofDelay) await new Promise(resolve => setTimeout(resolve, options.proofDelay));
                    if (signal.aborted || captured !== generation) {
                        staleDiscarded++; this.diagnostic(); throw abortError();
                    }
                    return result.data;
                }})});
                this.mounted = mount({element:this.custom.el, host, route, signal});
                this.mountCount++;
            }
        } catch (error) { this.showError(error); }
        this.diagnostic();
    }
}

startWebClient(FeasibilityHost);
