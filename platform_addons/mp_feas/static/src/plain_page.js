/** Plain JavaScript page: no Owl, native environment, ORM, or credentials. */
export function mount({ element, host, route, signal }) {
    let disposed = false;
    const title = document.createElement('h2');
    title.textContent = 'Custom workspace page';
    const identity = document.createElement('p');
    identity.textContent = `Role: ${host.context().role} · Generation: ${host.context().generation}`;
    const output = document.createElement('pre');
    output.setAttribute('aria-live', 'polite');
    const refresh = document.createElement('button');
    refresh.textContent = 'Refresh records';
    const write = document.createElement('button');
    write.textContent = 'Try attributed write';
    const delayed = document.createElement('button');
    delayed.textContent = 'Start delayed result';
    const routeInfo = document.createElement('p');
    function updateRoute(next) { routeInfo.textContent = `Page: ${next.pageId} · Detail: ${next.query.detail || 'overview'}`; }
    async function load() {
        try {
            const records = await host.services.call('fixture', 'list', {});
            if (!disposed) output.textContent = JSON.stringify(records, null, 2);
        } catch (error) { if (!disposed && error.name !== 'AbortError') output.textContent = error.message; }
    }
    async function attempt() {
        try {
            const records = await host.services.call('fixture', 'list', {});
            await host.services.call('fixture', 'provider_chain_write', {object_id: records[0].public_id, input: {amount: 27}, actor_id: 'administrator', plugin_id: 'privileged-provider'});
            if (!disposed) output.textContent = 'Write accepted';
        } catch (error) { if (!disposed && error.name !== 'AbortError') output.textContent = error.message; }
    }
    async function delay() {
        try {
            await host.services.call('fixture', 'list', {}, {proofDelay: 1800});
            if (!disposed) output.textContent = 'Delayed result delivered to current generation';
        } catch (error) { if (!disposed && error.name !== 'AbortError') output.textContent = error.message; }
    }
    refresh.addEventListener('click', load);
    write.addEventListener('click', attempt);
    delayed.addEventListener('click', delay);
    element.append(title, identity, routeInfo, refresh, write, delayed, output);
    updateRoute(route);
    load();
    return { updateRoute, canLeave: () => 'allow', dispose() {
        disposed = true;
        refresh.removeEventListener('click', load);
        write.removeEventListener('click', attempt);
        delayed.removeEventListener('click', delay);
        element.replaceChildren();
    }};
}
