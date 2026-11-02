# F-01d worker-image transition: source prerequisites

ADR0038 implements a narrowly reviewed transition between different reference
worker images while all provider workspace features are suspended. Read-only
projection reports the actual new endpoint; independent plan reconstruction
selects a matching target package. Private maintenance derives its transition
proof from the protected operation store. Native inspection rechecks the actual
old artifact/manifest and complete suspended scope map. Default maintenance still
refuses a mismatched image. Recovery can preserve later independent revocations
and key rotation without restoring old endpoint authority.

`source_checks.py` ran 98 source tests successfully across the ten modules listed
in `source-checks.json`; `tests.log` contains the result. `freeze.log` verifies
all 97 existing frozen files/eight contract rows unchanged. Tests substitute
independent IO; they do not establish actual deployment, remote upgrade or
recovery behavior. No acceptance count/progress credit or SVC05 pass is claimed.

The first new-test run exposed shared mutable test fixtures and a target-list
reset bug. Deep-copying the site and saving the original target list corrected
the tests; no live mutation or repeated external effect occurred. A subsequent
ordering review found projection rejected changed images before planning; the
new real-projection/independent-reconstruction case verifies the inert planning
path and rejects an enabled second scope. Health must name the approved image.

Owned core/platform version is advanced to 19.0.0.1.17/0.1.17 before building.
The existing deployed BB1/core16 profile remains the qualified installed profile;
source changes await immutable rollout and changed-image qualification. Browser
checks remain deferred at the user's request. Native Odoo record views and the
minimal Canvas fixture are unchanged.
