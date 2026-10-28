# ADR0007: optional custom-page draft snapshot

Accepted, compatible UI major1 / freeze revision6, before custom session-loss integration.

G4 demonstrates a contract gap: canLeave handles normal navigation, but an expired session or authority remount must tear down the page immediately. The shell cannot recover a custom draft through the original mount interface. Inferring plugin DOM values or persisting sensitive drafts indiscriminately is inappropriate.

MountedPage gains optional synchronous snapshotDraft(), returning null or a strict JSON-only {filename,data} snapshot. Existing pages/types stay compatible. Filename is a bounded safe JSON basename; the encoded UTF-8 snapshot is at most65536 bytes. The host copies it before abort/dispose, binds it to the current principal/site/workspace itself, and keeps it only in page-process memory. Plugin-supplied identity, target paths, HTML, credentials and storage instructions are not accepted. The host offers an explicit download on recoverable session/network loss or same-actor authority refresh. It verifies any newly authenticated principal before download. Known membership/plugin denial or actor/site changes clear the snapshot. No automatic persistent storage or automatic download; signing in/reloading can discard memory, so the recovery action is offered before that navigation.

The reference Canvas supplies its exact revision/name/cards snapshot. Explicit successful save/discard removes its old conflict download control. Cancellation remains best effort; a dispatched mutation reports unknown and retains its idempotency key for a safe retry. Native draft behavior remains compatible. This is a supported trusted-page lifecycle contract, not containment against malicious same-origin code.
