# ADR0074. Native application jobs retain native authority

Accepted8 November2026 after AT-01 feasibility. Native API v1 and selected app
behavior are frozen by [the application contract](../aurora-tasks-contract.md).
This is not release qualification.

Aurora's native list/task access rules are independent of platform workspaces.
The durable workspace adapter cannot currently schedule work for this application
without adding unrelated membership and service bindings. Converting the app to
workspace tenancy would change its stored-data and permission model. A hidden
scheduler user would obscure the originating human's authority; a separate cron
queue would duplicate leases, fencing, retries and lifecycle controls.

Probe a second, explicit native application authority adapter over the existing
durable queue. Retain original human principal and real installed application;
leave workspace NULL for native work. A principal mapping grants no membership,
role or resource access. Existing workspace submission remains strictly scoped;
it cannot select this adapter. Native definitions register an exact owning addon,
with no serialized service binding or caller-selected user. Reconstruct the user
from the immutable stored principal; require active internal human, current
installed native artifact/addon and current release at enqueue, preparation and
fenced apply. Application handlers check current native ACLs/rules and resources
under that user. Only private metadata/effect storage can use constrained SQL.

NULL workspace needs real NULL-safe deduplication and separate native-installation
execution partitions; do not use a fake workspace ID. PostgreSQL16 supports UNIQUE
NULLS NOT DISTINCT. Workspace partitions and native application partitions must
have distinct claim/compute locks and bounded fair selection. Native jobs use the
same managed urgent/bulk process limits, transaction fences, control generation,
shutdown and checkpoint/recovery; no new worker product or broker. Native queue
history must not leak through workspace projections. A native private projection
must authorize its original actor and current application/resource independently.

The [first feasibility proof](../evidence/post-r1/aurora-tasks/at01-native.json)
executed a native task effect, refused an outsider,
detected revoked actor/resource permissions between prepare and apply, suppressed a
stale task occurrence, and proved duplicate identity and paused dispatch behavior
without creating a workspace. It does not establish production throughput,
supervisor fairness, upgrade compatibility or the final application reminder UI.
The new schema/source requires a new owned foundation release and explicit
populated upgrade/recovery qualification. Sealed core47 and core46 stay immutable.
Technical service submissions remain under the existing credential-bound workspace
API; native v1 initially admits human-origin jobs only.
