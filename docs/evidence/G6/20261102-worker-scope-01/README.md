# Actual canonical worker duplicate and scoped-token qualification

Thirty real HTTP cases passed against the already-running approved worker05:
image1d, public config3, independent publication5, installed native profile18/88/BB1.
Product source commit `be3910ee`; exact verifier source digests in `qualification.json`.

The independent OS operator freshly selected the protected published authority
and signed short-lived RS256 credentials locally. Signing material was never
mounted in or sent to the worker/app. Only request-scoped invocation tokens crossed
stdin into a short-lived network probe in the existing app container. That probe
dialed the approved numeric IP with the configured Host header and called the real
worker HTTP endpoint. No Docker assets were created. Keys/tokens/request text are
absent from public evidence and diagnostics output.

| Cases | Observed result |
| --- | --- |
| First request, repeat/new transport ID, original after conflict |200, exact statistics and current correlation IDs |
| Same operation with changed input |409 CONFLICT |
| Eight concurrent same-operation requests |200, exact statistics/current correlation IDs for all |
| Payload-only site/workspace/installation/generation changes |401 UNAUTHENTICATED |
| Correctly signed matching foreign site/workspace/installation/generation |403 FORBIDDEN against fixed worker scope |
| Expired retry, future nbf, wrong audience/issuer/subject/method/lifetime |401 UNAUTHENTICATED |
| Wrong key ID/signature/algorithm |401 UNAUTHENTICATED |

Every row of all17 baseline tables, including22 terminal jobs, remained exact.
Fresh before/after worker image/identity/start/key/publication/network observations
were equal. The worker remains healthy. Only bounded pure computation/dedup state
inside the running reference worker changed; no Note/job/business mutation occurred.

Two initial harness validations failed before any signing/HTTP: first omitted the
required Note reference fields; second used a transport prefix instead of the
frozen UUID request ID. Reviewed the frozen example and actual schema, populated
all required fields and UUIDs, and added request validation for every constructed
case. Distinct read-only continuation labels preserved the original baseline and
proved no intervening data/worker change. The actual HTTP batch executed once.
No product source/contract changes or retry of a failed remote call occurred.

This completes SVC-03's payload scope requirement. It complements the separate
installed gateway/bridge positive and outage evidence; this direct verifier test
does not claim to exercise the host gateway or original-actor finalization.
No cache introspection/single-computation-count assertion is made. In-flight
authorization changes, external recovery, changed-image compatibility, degraded
browser rendering and the rest of G6/G7 remain required.
