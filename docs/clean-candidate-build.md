# Clean-core candidate build

The default `deploy/distribution-r1-core.json` selects the owner-approved eight
framework addons, SDK and stock WebClient, with no reference or application
packages. Support remains provisional and covers only exact qualified combinations;
see [candidate support](candidate-support.md). Source candidate0.2.4 has passed
[bounded rebuild measurements](build-reproducibility.md); it is not a deployed
or newly installed-qualified cohort.
The earlier `distribution-r1-clean-probe.json` remains an explicit TEST policy.

Build into a fresh owned evidence directory:

```powershell
& '.\.local\toolchain\operator-python16\Scripts\python.exe' -I tools/build_candidate.py `
  --output docs/evidence/G7/<fresh-core-build> --gate G7
```

Omitting `--policy` selects the clean core. Optional application compositions
require an explicit reviewed policy and normal catalog/staging/approval before
deployment; a successful build alone changes no site.

The builder creates or verifies its private checkout-level control and lock
directories before acquiring the build lock. It does not require a previously
initialized site/operator policy. Existing directories with unsafe ownership or
permissions refuse; the tool never resets their ACLs to continue.

The clean materialization path (`tools/build_distribution.py` with
`"runtime_surface": "clean"`) copies only `packages/contracts/v1`, the selected
engine/addons, SDK, licenses/notices/requirements and the fixed
`tools/start_worker.py` entrypoint. It excludes host tools, reference operator,
project tests/fixtures and app/example/plugin/service source trees.

`deploy/Dockerfile` has a separate `clean-runtime` target. It starts from the
pinned Python image, copies only the builder `/venv` and `/release`, and adds the
existing pinned Node24.22.2/rtlcss4.3.0 compiler closure from
`deploy/stock-rtl` for stock WebClient. The legacy `runtime` stage remains the
default last stage. The clean target is selected explicitly; it does not inherit
a historical full runtime or remove source guards.

A future reviewed build must use the normal pinned Python/OS/npm
network-or-cache prerequisites. `--reproduction` and
`--dependency-base-image` are code-only maintenance modes and are rejected for
the clean policy. The build record identifies the clean target, source hashes,
RTL package-lock digest and expected Node/rtlcss versions; a successful image
build additionally verifies those versions and the locked stock-RTL notice
closure. Materialization and record tests do not prove all-layer image purity,
installed removal, native/UI qualification or deployment; those require a later
actual artifact/layer audit and separate qualification.

## Deliberately recompile native dependencies

Normal builds can reuse Docker's dependency layer. To exercise the actual pinned
builder again without pruning shared cache, use a fresh output and the explicit
clean-only flag:

```powershell
& '.\.local\toolchain\operator-python16\Scripts\python.exe' -I tools/build_candidate.py `
  --output docs/evidence/G7/<fresh-native-recompile> --gate G7 --recompile-dependencies
```

It passes only the fixed `--no-cache-filter builder` and records
`build_cache_policy=recompile_builder_stage`. Builder apt/pip/materialization
steps reexecute; unrelated clean-runtime/RTL cache may remain. Locked dependency
network access remains enabled; this is distinct from code-only maintenance
`--reproduction`. Non-clean or incompatible modes refuse before creating output.
Verify the actual build log, not just the flag, before claiming recompilation.
[Docker's cache rules](https://docs.docker.com/build/cache/invalidation/).

The builder-only compiler front-end normalizes recognized pinned-pip temporary
source roots to stable per-distribution debug paths, retaining debug information
and existing compiler flags. It invokes the fixed Debian GCC by argv; it is not
a native-code sandbox. Unknown build-root shapes require explicit packaging
review. This affects new builds using the shared builder, not retained images or
the separate maintenance Dockerfile. No wrapper or `CC` environment is added to
the clean final stage. The recorded paired measurements establish the declared
installed-file/runtime-layer boundary, with distinct provenance indices and no
intermediate wheel-ZIP identity claim. Source tests alone establish none of this.

## Build an exact source-removal image

After normal database uninstall, build the source-removal candidate from the
exact currently selected clean image and its successful build record:

```powershell
& '.\.local\toolchain\operator-python16\Scripts\python.exe' -I tools/build_clean_removal.py `
  --image-id 'sha256:<current-image-id>' `
  --source-build-record docs/evidence/G7/<source-build>/candidate-build.json `
  --remove-package org.example.notes `
  --output docs/evidence/G7/<fresh-removal-build> --gate G7 --plan
```

Review the derived subtraction, then run the same command without `--plan` to
build. Planning inspects the image through the ordinary disposable read-only
inspector; it creates no build output, persistent resources or site changes.
Repeat `--remove-package` to select several packages in one build.

The builder preserves the original dependency bytes instead of recompiling
native Python wheels. It copies only the inventoried project payload, subtracts
the selected native addon directories and exact archives, and derives the
remaining policy and ownership metadata. It preserves descriptive profile text
as original provenance; the effective addon/artifact sets describe the result.
It checks the derived and actual images with the existing strict removal
validator, including every surviving file, manifest and Python fingerprint.

The final stage starts from the pinned Python base and the existing clean OS
recipe. The source image is a build input for `/venv` and the fixed Node/RTL
closure; its application layers are not final ancestors. The command saves and
audits every final layer, binds compressed/uncompressed digests and image
configuration, rejects hidden project source/whiteouts, and requires all project
bytes to match the expected inventory. `image-audit.json`, `candidate-build.json`
and the build log are recorded in the fresh evidence directory. Private build
intent, extracted context and image export remain under `.local/operator/builds`.

The source must have a successful normal `clean-runtime` build record matching
the current pinned dependency/OS/compiler inputs. This command supports the
`reference_packages`, ordinary `application_packages`, and mixed compositions.
Source entries can only be subtracted within their original kind; order,
surviving archives, model/field ownership and every unrelated policy field are
preserved. Partial subtraction requires the original manifest files and, for an
application, the recipe itself to match their recorded hashes. It identifies
surviving source entries without importing application code or guessing paths.
It never rebuilds source from a changed checkout or silently applies a new host
SDK fix to the image. Host-tool and historical payload provenance are recorded
separately. A built image is neither an admitted package nor an authorized
deployment.

Use normal `stage-image`/`plan-staged` with operation type `remove`, independent
exact-hash approval, and apply afterward. Complete sharing-database observation,
prior uninstall, current authority, checkpoint and source-removal guards remain
mandatory. A retained failed database can still block that operation. This build
command does not touch databases, delete history or perform lifecycle mutation.
Do not rerun a failed build using the same name; inspect its recorded phase,
image and any exact retained input-container identity first.

Actual [recorded clean-removal qualification](evidence/G7/20261111-recorded-clean-removal-01/qualification.json) passed the strict observed-image delta and every final-layer check. This replaces the prior private subtraction build for the reference-package composition. Ordinary and mixed recipe handling subsequently passed actual-archive/materialization and independent-reconstruction source tests. An independently packaged ordinary application then completed normal install/use/native uninstall/source removal on core0.2:14deleted source/archive files,8addons,0artifacts,7historical events retained,11final layers audited. [Scoped result and later reinstall defect](evidence/G7/20261111-core020-independent-app-01/qualification.json) distinguish that completed removal from the separate CR-0019 binding-incarnation repair. Installation/removal approval remains unchanged.
