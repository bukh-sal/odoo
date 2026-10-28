# R1 artifact and catalog workflow

Implemented E-01a; lifecycle execution and the release planner remain later G5 work. [Current status](implementation-status.md) is authoritative. Native Python and same-origin frontend code run with host trust after approval. Archive inspection never imports them or runs build tools.

R1 curated trust means an operator approves the **exact outer SHA-256 digest** in an independently owned JSON configuration. No signature verification is implemented or advertised. Package provenance describes claimed inputs; neither it nor a publisher key inside a package grants trust. Development accepts unsigned artifacts only with `mode: "development"` and `allow_unsigned_development: true`; every successful CLI result displays a warning. Open-marketplace policy is rejected.

Example curated operator configuration (save outside application-writable mounts):

```json
{
  "schema_version": 1,
  "mode": "curated",
  "approved_digests": [],
  "allow_unsigned_development": false,
  "generation": 1
}
```

Add reviewed `sha256:<64 lowercase hex>` identities to `approved_digests`. The operator controls this file; an upload cannot change it. Independent executor-store OS restrictions are qualified in E-01c rather than inferred from this CLI.

Run using the repository's locked environment:

```powershell
.venv/Scripts/python.exe tools/modular.py --config <operator.json> plugin validate <package.mplug> --digest sha256:<hex>
.venv/Scripts/python.exe tools/modular.py --config <operator.json> catalog --store <operator-catalog> add <package.mplug> --digest sha256:<hex>
.venv/Scripts/python.exe tools/modular.py --config <operator.json> catalog --store <operator-catalog> list
.venv/Scripts/python.exe tools/modular.py --config <operator.json> catalog --store <operator-catalog> quarantine sha256:<hex>
```

Catalog blobs are content addressed, published exclusively from a fully validated private copy, and never overwritten. The SQLite index uniquely binds `(plugin_id, version)` to one artifact. Re-adding identical bytes is idempotent; different bytes for an existing version fail. A crash between publishing a blob and committing its index can leave an unselected orphan; re-adding the same bytes reconciles it. Catalog reads recheck actual bytes and current trust. Quarantine excludes selection and re-addition. Removing trust invalidates selection immediately. Recover damaged storage from an independently verified copy through a future explicit repair procedure; `add` preserves corrupt existing bytes and reports failure.

The ZIP profile has one root exactly equal to the plugin ID. It accepts stored/deflated files with canonical NFC, portable POSIX paths and regular-file/directory metadata. ZIP64, multipart/encrypted archives, extra fields, comments, data descriptors, prefixes/trailers, links, special files, overlapping/unindexed data, case collisions and ambiguous paths are unsupported and rejected. Central-directory counts/bytes are bounded before constructing ZIP entry objects. Declared and actual decompressed sizes, CRCs and file hashes are checked. Private extraction uses exclusive writes and rehashes written bytes; it never extracts onto an installed release.

Defaults: 100 MiB compressed, 500 MiB expanded, 10,000 entries, 64 MiB per file, compression ratio at most 200:1 and 4 MiB per inspected metadata file. Operators may supply a `limits` object containing positive integer `compressed`, `expanded`, `entries`, `per_file`, `ratio`, and `metadata` values. Archive requests cannot supply limits.

`inventory.json` has exactly `schema_version: 1`, `files: {relative_path: lowercase_sha256}`, and `excluded: ["inventory.json"]`. It hashes every other payload file, including provenance. `provenance.json` has `schema_version: 1`, a bounded `builder` string and `source_files` hashing every file except provenance/inventory. Optional `trusted_inputs_only` and `upstream_commit` are informational. Unsupported signature envelopes and other root metadata are rejected by this profile.

Native packages have only their declared addon under `backend/odoo_addons/<addon>/`, prebuilt assets, JSON schemas, locales and notices. Native manifests are static Python literals: verified version mapping, explicit data/assets, a supported license mapping and no implicit activation or executable hooks. Every migration payload must be declared with its exact digest and full native target/phase path. Dependency mapping across packages is the planner's responsibility. Service/page/slot/command schemas and entry assets must exist. Schema references are local fragments; validation cannot retrieve remote code or schemas.

External-service artifacts contain only manifest, JSON schemas, text notices, inventory and provenance. They cannot carry native source, frontend bundles, installers, images, deployment templates or migrations. Registering metadata never launches a service. The separately operated reference worker remains G6.

Supplementary lint rejects recognizable private keys/credential literals and literal remote browser imports/scripts/credential URLs. It does not prove arbitrary trusted code is safe or detect every secret or constructed remote URL. Review remains required.

Qualification: `tools/qualify_artifacts.py --output docs/evidence/G5/<fresh-run>` runs the same hostile-byte/catalog/CLI checks on the host and a non-root, read-only, network-disabled Linux container. It streams current test inputs into private disposable tmpfs, records image/source identities and checks the unchanged G2 freeze. This is validation qualification, not a new release build or G5 exit.
