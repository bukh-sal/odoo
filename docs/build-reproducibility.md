# Measured build reproducibility

PP04 C qualifies the following boundary at source `9ceef0ae28b`, provisional
core0.2.4/native19.0.0.2.4, on the recorded Linux amd64 Docker Desktop toolchain.
It changes no deployment or app support promise. See the
[measurement record](evidence/G7/20261113-pp04-reproducibility-native-01/qualification.json)
and [build commands](clean-candidate-build.md).

Two independent public application assemblies produced the same23,464-byte
private app archive and matched its previously admitted digest. Application
sources and admission were unchanged.

Four clean eight-addon builds used the same3,964 curated source inputs: two normal
builds, followed by two explicit `--recompile-dependencies` builds. Actual logs
show apt/pip and native wheel compilation in both forced builds. RTL and final
runtime stages could reuse content caches; shared caches were never pruned.
The first normal build also compiled dependencies; the second reused them.

All four delivered images have identical declared file bytes, modes, symlink
targets and observed mtimes:3,690 project files,9,215 virtual-environment files
(including3,237 bytecode files and every installed native extension),1,013 selected
OS-library files,138 stock-RTL files and three selected executables. Directories
and symlinks were compared separately. Package versions, Python build configuration,
both diagnosed native ELF section maps and all14 runtime layer diffIDs also match.
The unchanged runtime manifest is
`sha256:467401251ffbdd9a22d7425475f0701b23c52cea3eb912dd9c76f9a7ddf5bff2`.

The earlier native-library differences were temporary source roots in debug data
and the resulting build IDs. A builder-only compiler front-end maps the measured
pinned-pip roots to a stable per-distribution debug path. It retains debug data,
optimization/security flags and the fixed GCC12.2.0 toolchain. Unknown source-root
shapes refuse instead of silently weakening the measurement. No compiler wrapper
or `CC` setting is shipped in the clean runtime.

| Artifact | Measured result | Practical boundary |
| --- | --- | --- |
| Private app archive | Exact repeated bytes and admitted digest | Same reviewed source/recipe; no universal recipe claim |
| Installed project and declared dependency files | Exact across cached and forced recompilation builds | This architecture, pinned inputs and toolchain; not a clean-room host reproduction |
| Intermediate pip wheel ZIP containers | Logged ZIP hashes differ; members were not retained for ZIP comparison | No wheel-container identity or proven timestamp-cause claim; installed files and RECORD bytes are compared |
| OCI runtime manifest/config/layers | Equal | Final stages may reuse verified content caches |
| Top-level OCI image index | Different | Accurate provenance includes unique invocation IDs/times/tags and the requested builder-cache policy |

Keep provenance accurate. Do not disable it, relabel an older image, rewrite a
lock or weaken independent staging merely to obtain an equal top-level digest.
[Docker documents provenance as separate attached build metadata](https://docs.docker.com/build/metadata/attestations/).

Observed end-to-end build times were87.547s and9.328s for normal builds,
131.688s and95.031s for forced recompilation. These are observations with the
recorded network/cache/hardware, not accepted performance budgets. All four exact
images/tags and evidence are retained; measurement children were removed by their
own exact lifecycle. No site, catalog, approval, authority or existing image changed.

Packaging owns the remaining boundary. Before distributing intermediate binary
wheels, retain and compare their ZIP members and metadata. A new architecture,
backend, compiler, dependency lock or build-root shape requires fresh qualification.
New candidates still require normal immutable-image review/approval and installed
qualification; none of these four was admitted or deployed by this measurement.
