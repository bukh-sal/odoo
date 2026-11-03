# ADR0049: project-local operator Python security maintenance

Date: 2026-11-04 (Asia/Riyadh). Status: selected after actual isolated interpreter,
232 operator checks, TypeScript, freeze and existing-key compatibility passed.

The current Windows operator uses Python3.12.15/Expat2.8.5, independently of
cryptography50's OpenSSL4.0.3. Official Python3.12.16 is an expedited security
release covering compromised eMudhra CA keys, bundled Expat2.9.0 and other
stdlib fixes: https://www.python.org/downloads/release/python-31216/ .
The actual Linux app/worker already use Python3.12.16. Separate actual native
component evidence is under G7/20261104-native-libraries-01.

Install exact Python3.12.16 using the existing trusted uv executable into an
explicit project-owned `.local/toolchain/python16` directory with `--no-bin`
and `--no-registry`. Create `.local/toolchain/operator-python16` from that
interpreter and install the unchanged tooling/operator hash locks with binary
wheels only. Do not change global Python, PATH, registry, existing uv-managed
shared interpreters or the old `.venv` checkpoint.

Re-run affected Windows schema/approval/store/token/publication/reconstruction
and deployment consumers with the new interpreter, old-key compatibility,
TypeScript and current freeze check. Verify the complete installed package
solution stays unchanged and record native library versions and interpreter
provenance before selecting the new local environment in host-toolchain.lock.

No SDK/native version, public schema, wire format, application/worker image,
endpoint, publication, keys or installation approval changes. The host toolchain
lock is outside frozen contract files; all101 current frozen files/eight rows
must remain exact. Existing Linux consumer evidence remains scoped to its
already-qualified Python3.12.16 environment, not newly claimed as re-executed.

This does not settle the newer Expat2.10.0/SQLite/native-library advisories.
Review actual functions/build options/vendor backports and supported input
paths separately. Do not convert a Python patch upgrade into a blanket security
or full G7 qualification claim.
