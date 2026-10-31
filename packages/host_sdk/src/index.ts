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
    /** Synchronous JSON-only snapshot; host binds ownership and keeps it in RAM. */
    snapshotDraft?(): {readonly filename:string;readonly data:unknown} | null;
    dispose(): void | Promise<void>;
}
export interface PluginPageModule {
    mount(input:{element:HTMLElement;host:PluginHost;route:RouteSnapshot;signal:AbortSignal}): MountedPage | Promise<MountedPage>;
}

/** Additive event wire contract; existing HostEvent/facade remain UI major1. */
export type EventJSON = null | boolean | number | string | readonly EventJSON[] | {readonly [key:string]:EventJSON};
export interface DomainEventEnvelope {
    readonly id:UUID; readonly topic:string; readonly schema_version:number;
    readonly owner_plugin_id:string; readonly aggregate_id:UUID; readonly aggregate_sequence:number|null;
    readonly site_id:UUID; readonly workspace_id:UUID; readonly occurred_at:string;
    readonly correlation_id:UUID; readonly causation_id:UUID|null;
    readonly payload:Readonly<Record<string,EventJSON>>;
}
export interface EventReceipt {readonly delivery_id:UUID;readonly receipt:UUID;readonly generation:number}
export interface EventDelivery {
    readonly id:UUID;readonly receipt:UUID;readonly generation:number;readonly attempt:number;
    readonly lease_expires_at:string;readonly event:DomainEventEnvelope;
}
export interface EventDeliveryStatus {
    readonly id:UUID;readonly event_id:UUID;readonly state:'pending'|'leased'|'acknowledged'|'dead_letter';
    readonly attempts:number;readonly replays:number;readonly error_code:null|'ACK_EXPIRED'|'CONSUMER_FAILED';
}
type EventRequestBase={readonly protocol:1;readonly request_id:UUID};
type EventSubscriptionRequest=EventRequestBase & {readonly subscription_id:UUID};
type EventResultBase={readonly protocol:1;readonly subscription_id:UUID};
export type EventTransportRequest =
    | EventRequestBase & {readonly kind:'subscribe_request';readonly topic:string;readonly idempotency_key:UUID}
    | EventSubscriptionRequest & {readonly kind:'poll_request';readonly limit:number}
    | EventSubscriptionRequest & {readonly kind:'ack_request';readonly receipts:readonly EventReceipt[]}
    | EventSubscriptionRequest & {readonly kind:'status_request'}
    | EventSubscriptionRequest & {readonly kind:'replay_request';readonly event_ids:readonly UUID[]}
    | EventSubscriptionRequest & {readonly kind:'close_request'};
export type EventTransportResult =
    | EventResultBase & {readonly kind:'subscribe_result';readonly topic:string;readonly expires_at:string;readonly replay_window_seconds:604800;readonly ack_lease_seconds:15;readonly max_attempts:5;readonly max_replays:3}
    | EventResultBase & {readonly kind:'poll_result';readonly deliveries:readonly EventDelivery[];readonly has_more:boolean;readonly dead_letter_count:number;readonly next_poll_ms:number}
    | EventResultBase & {readonly kind:'ack_result';readonly acknowledged:readonly UUID[]}
    | EventResultBase & {readonly kind:'status_result';readonly state:'active'|'closed'|'expired';readonly deliveries:readonly EventDeliveryStatus[];readonly truncated:boolean}
    | EventResultBase & {readonly kind:'replay_result';readonly replayed:readonly UUID[]}
    | EventResultBase & {readonly kind:'close_result';readonly closed:true};
