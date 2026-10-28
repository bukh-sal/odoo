import type { PluginPageModule, HostContext, BindingDescriptor } from '../src/index';

/** Compile-time example proves no dependency on Owl or private native env. */
export const page: PluginPageModule = {
    mount({element, host, route, signal}) {
        const context: Readonly<HostContext> = host.context();
        element.textContent = `${context.display_name}: ${route.page_id}`;
        const unsubscribe = host.events.subscribe('org.example.notes.changed', () => {});
        host.services.call<{items:unknown[]}>('documents','list',{limit:25},{signal}).then(result => {
            if (!signal.aborted) element.textContent = String(result.items.length);
        });
        // @ts-expect-error Generic SDK does not expose native ORM dispatch.
        host.orm;
        // @ts-expect-error Pages cannot substitute provider/binding/workspace.
        host.services.call('documents','get',{}, {workspace_id:'other'});
        // @ts-expect-error Context is immutable presentation data.
        context.workspace_id = 'other';
        return {canLeave:()=> 'allow', updateRoute(next) {element.dataset.page=next.page_id;}, dispose(){unsubscribe();element.replaceChildren();}};
    },
};
const binding: BindingDescriptor = {
    schema_version:1, binding_id:'fixture', site_id:'fixture',workspace_id:'fixture', consumer_installation_id:'fixture',
    alias:'documents',service_id:'org.example.notes.documents',contract_major:1,api_version:'1.0',provider_plugin_id:'org.example.notes',provider_installation_id:'fixture',generation:1,optional:false,
};
void binding;
