# ADR0055: measure current shell/disposal through an owned browser

Date: 2026-11-04. Status: accepted measurement protocol; results pending.
G-01c4, spec24.1–24.3; shared evidence may support ID08/UI09/OPS03 only when
the corresponding behaviors are actually exercised.

Use installed Edge headless and Node24's existing CDP/WebSocket tooling, one
new owner-protected project profile, and the current managed reference realm.
Control no personal browser or prior protected profile. Reuse this profile
for100cycles and subsequent justified checks; keep exact PID/endpoint/exit
records. No new Docker fixture, image, plugin feature or Canvas polish.

Measure login request through real native Notes list readiness, including CDP
observation overhead, with production minified assets and a warm server. Record
the first cold-browser-cache sample and three warm-browser samples separately;
the required shell target remains under3seconds. DOM readiness includes visible
native records, resolved workspace/navigation and enabled shell controls, not
merely a root element. Verify the shell responds after timing it.

For disposal, close the timing tab and use one fresh tab in the same browser
profile, warm five Canvas→Settings cycles, then measure100additional cycles.
Click real navigation; do not call private component methods, replace app
functions or fabricate results. At each disposal the Canvas DOM must be absent.
Do not edit/save a board or Note. Pace transitions to respect existing admission
controls. Capture DOM/listener counts and post-GC heap at baseline and every20
cycles, using numeric CDP diagnostics, never a heap dump containing credentials.

Predeclared conservative checks: final retained heap increase no more than the
larger of4MiB or10%baseline; growth from60to100cycles no more than the larger
of1MiB or3%baseline; final document count unchanged and DOM/listener counts
within32ofbaseline. Capture the whole curve and all errors. A failing threshold
requires source/retention analysis, not repetition until it passes. Finite
measurements support “no unbounded growth observed in100cycles,” not a universal
memory guarantee. Source-bound bounded caches can be explained with actual
evidence if a threshold needs an explicit reviewed refinement.

Intercept the owned page's HTTP requests and refuse foreign origins. Record
only URL origin/path/type/status, never cookies, headers, authentication bodies
or document contents. One exact reserved-domain control request must be observed
and aborted to prove the interception actually works. Keep that control separate
from app-origin requests. Record WebSocket destinations as well. No firewall,
OS DNS or personal-browser configuration changes; any host-resolver rule is
limited to the owned browser's exact local fixture hostname.

Retain protected diagnostics/screenshots and compare actual business tables,
authority and runtime identity around the browser work. Publish only redacted
metrics and reviewed images. This is a local reference qualification, not
arbitrary browser/host containment, production deployment or full WCAG audit.
