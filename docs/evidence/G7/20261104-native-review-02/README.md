# Native dependency review, 4 November 2026

`native-dispositions.json` records 72 component-scoped decisions, with evidence,
rationale, review by 11 November and earlier review on the listed changes.
This complements the 159 Debian OS decisions; it does not transfer Debian
revision/backport classifications to embedded libraries.

The actual core23 image was observed in one offline, read-only, unprivileged
helper, without mounts or credentials. It exited and auto-removed. The selected
Python wrappers expose no Reset call; external-subparser creation remains
exposed. openpyxl uses defusedxml with entity/external protection. Existing
actual native ordinary-import/entity-refusal evidence is reused; no dangerous
parser payload or repeated installation/recovery was run.

The four newer Expat findings have separate decisions. Reset is excluded for
the selected wrapper paths, rather than arbitrary trusted C/ctypes code. Entity
expansion has a qualified supported-input mitigation. External subparser use
and attribute/namespace counter overflow remain explicit residuals. Defusedxml
is not called a fix for all four issues.

The lxml wheel embeds libxml2 2.14.6 and libxslt 1.1.43. All 17 retained 2026
libxml2 records were considered, including four whose Debian Bookworm status
is not affected. That status cannot be inherited by this newer embedded library.
The exact lxml build mapping, vendor release notes and retained patch establish
the documented libxslt backports; the other XML memory-safety/availability
findings are not silently called fixed. Arbitrary uploaded XSD, catalog,
stylesheet and XPointer execution are distinct from standard record inputs.
XML/HTML parsing still carries explicit residual risks.

The review maps all 15 retained 2026 candidates for the seven named Pillow
codec sources to the actual embedded versions. It distinguishes decoder/library
input from separate CLI tools and direct upstream ranges from Debian revisions.
Odoo's image size verification is conditional on the caller; it is not claimed
to protect every malformed image or every native decoder. Node c-ares/nghttp2
ranges and the documented Brotli backport use actual selected component/binary
evidence. Private operator and unused Node SQLite paths are separately scoped.
Crypto/libpq/Alpine vendor checks retain their existing dated records.

The selected proxy includes optional XML/image modules, but the qualified
generated profile does not load/configure those pipelines. Enabling them
requires a fresh review; application-wheel backports do not apply to the proxy.
The nginx diagnostic log limitation remains accepted with a review date.

The native candidate method is explicitly bounded: retained tracker records,
selected vendor release/build material and actual package/component inventories.
It is not an exhaustive historical native CVE database or a promise that all
transitive native calls are safe. Potential parser/codec memory corruption,
resource exhaustion and diagnostic handling limitations remain release caveats.
No runtime patch, new package/image, service change or production approval was
introduced by this review. OPS-03 and G7 remain open for the other release checks.

Next: current Git/history/served-assets/diagnostic privacy delta, reproducibility
and release kit. Do not repeat the completed OS/native decision queues unless
inputs change or a new finding appears.
