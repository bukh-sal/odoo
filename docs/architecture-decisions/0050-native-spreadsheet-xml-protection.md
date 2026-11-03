# ADR0050: reuse openpyxl's optional XML protection

Date: 2026-11-04 (Asia/Riyadh). Status: accepted; installed core22 maintenance qualified on the existing fresh
qualification realm. Original working realm retains its previous image.

G7 native-library inspection found Python3.12.16/Expat2.9.0 in the app/worker
and Python3.12.15/Expat2.8.5 in the former Windows operator. Expat2.10.0's
upstream change log records four newer security fixes:
https://github.com/libexpat/libexpat/blob/R_2_10_0/expat/Changes . This requires
native-library review beyond the clean Python-package advisory query.

The actual app has openpyxl3.1.2 with LXML=true but DEFUSEDXML=false. Its streaming
reader uses `xml.etree.ElementTree.iterparse`, including the standard native
spreadsheet import path. In an isolated no-network/no-config helper, a tiny
benign entity declaration expanded. Adding the exact defusedxml0.7.1 pure wheel
only in that disposable helper makes openpyxl select its existing defused
reader, reject the declaration with EntitiesForbidden and still read/write
an ordinary workbook. See G7/20261104-native-libraries-01/defused-experiment.json
for exact source URL/hash, both observed modes and limits.

Stage defusedxml0.7.1 as an explicit application dependency, preserving unrelated
package versions and recording PSFL notice/source provenance. Keep Odoo's native
record import and openpyxl; no custom parser, new frontend or replacement CRUD.
The current image's absent optional dependency is insufficient to demonstrate
the desired entity-input refusal. A package/query inventory alone is insufficient.

Use the existing independent Python-maintenance plan/review and versioned core
release path. Inspect its version/source compatibility conditions before any
version change; do not bypass them, overlay code into running workers or silently
install a wheel in an active application. Require complete static dependency
solution/metadata/hash review, actual immutable-image parser tests, native import
and normal CRUD regression, then the normal reviewed deployment/preservation.
Keep current/checkpoint roles and use one candidate image.

This is a specific supported-input mitigation, not proof all Expat/SQLite/native
advisories are fixed or every optional XML feature is safe. Review CVE-specific
functions, parser settings, bounds, vendor backports and transitive input paths.
The worker reference accepts bounded JSON and gets no implicit XML feature.
G7 final risk/security and reproducibility remain pending; do not mark them
passed based on the helper experiment or merely adding a requirement line.

Implemented evidence: `../evidence/G7/20261104-defused-staging-01/static-resolution.json`,
`../evidence/G7/20261104-core22-defused-image-01/candidate-admission.json` and
`../evidence/G7/20261104-core22-maintenance-01/qualification.json`.
Baseline66/R174 retain all earlier pins/hash blocks. Only platform/core version
constants advance to0.1.22/19.0.0.1.22, as required by the existing maintenance
guard. No public contract, native model, UI or worker source changes.
Actual Odoo `base_import.import._read_xlsx` accepts ordinary workbook values;
scoped native ORM import succeeds; entity input is rejected with openpyxl's
existing ValueError wrapping EntitiesForbidden. Normal approved eight-scope
maintenance and subsequent HTTP/native views preserve the working dataset.
Eight terminal containers were archived and retired. The separate original demo
and benchmark have not been upgraded, and this does not close final G7 audits.
