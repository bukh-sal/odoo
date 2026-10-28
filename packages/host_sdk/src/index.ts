/** UI host major 1. Schema validation occurs at wire and mount boundaries. */
export type UUID = string;
export interface HostContext {
    readonly ui_api_major: 1;
    readonly principal_id: UUID;
    readonly display_name: string;
    readonly site_id: UUID;
    readonly workspace_id: UUID;
    readonly plugin_id: string;
    readonly installation_id: UUID;
    readonly locale: string;
    readonly direction: 'ltr' | 'rtl';
    readonly timezone: string;
    readonly generation: number;
    readonly policy_generation: number;
    readonly capabilities: readonly string[];
}
export interface RouteSnapshot {
    readonly plugin_id: string;
    readonly page_id: string;
    readonly path: string;
    readonly params: Readonly<Record<string, string>>;
    readonly query: Readonly<Record<string, string>>;
}
export interface BindingDescriptor {
    readonly schema_version: 1;
    readonly binding_id: UUID;
    readonly site_id: UUID;
    readonly workspace_id: UUID;
    readonly consumer_installation_id: UUID;
    readonly alias: string;
    readonly service_id: string;
    readonly contract_major: number;
    readonly api_version: string;
    readonly provider_plugin_id: string;
    readonly provider_installation_id: UUID;
    readonly generation: number;
    readonly optional: boolean;
}
export type ErrorCode = 'UNAUTHENTICATED' | 'FORBIDDEN' | 'NOT_FOUND' | 'VALIDATION_FAILED' | 'CONFLICT' | 'DEPENDENCY_UNAVAILABLE' | 'PLUGIN_SUSPENDED' | 'RATE_LIMITED' | 'DEADLINE_EXCEEDED' | 'CANCELLED' | 'INTERNAL_ERROR';
export interface HostError extends Error {
    readonly code: ErrorCode;
    readonly request_id: UUID;
    readonly retryable: boolean;
    readonly details: Readonly<{field?: string; operation_id?: UUID; outcome?: 'not_started' | 'committed' | 'unknown'}>;
}
export interface HostEvent { readonly id: UUID; readonly topic: string; readonly data: unknown; readonly generation: number }
export interface ThemeSnapshot { readonly mode: 'light' | 'dark'; readonly density: 'comfortable' | 'compact' }
export interface LocaleSnapshot { readonly language: string; readonly direction: 'ltr' | 'rtl'; readonly timezone: string }
export interface NavigationTarget { pluginId: string; pageId: string; params?: Record<string,string>; query?: Record<string,string> }
export interface PluginHost {
    context(): Readonly<HostContext>;
    navigate(target: NavigationTarget): Promise<void>;
    readonly services: {
        call<T>(bindingAlias: string, method: string, input: unknown, options?: {signal?: AbortSignal; idempotencyKey?: string}): Promise<T>;
    };
    readonly commands: { execute(commandId: string, input?: unknown): Promise<unknown> };
    readonly events: { subscribe(topic: string, callback: (event: HostEvent) => void): () => void };
    readonly notifications: { show(input: {severity:'info'|'success'|'warning'|'error'; message:string}): void };
    readonly dialogs: { confirm(input: {title:string; message:string; destructive?:boolean}): Promise<boolean> };
    readonly theme: { current(): ThemeSnapshot; subscribe(callback:(theme:ThemeSnapshot)=>void):()=>void };
    readonly locale: { current(): LocaleSnapshot; translate(key:string, values?:Record<string,unknown>):string };
}
export interface MountedPage {
    updateRoute?(route: RouteSnapshot): void | Promise<void>;
    canLeave?(): 'allow' | 'confirm' | Promise<'allow' | 'confirm'>;
    dispose(): void | Promise<void>;
}
export interface PluginPageModule {
    mount(input:{element:HTMLElement;host:PluginHost;route:RouteSnapshot;signal:AbortSignal}): MountedPage | Promise<MountedPage>;
}
