# Develop applications on the pinned foundation

The current adoption set is Tasks0.2.3, Projects0.1.1 and the optional
Projects–Tasks extension0.1.1, on foundation0.1.49. The three application sources
are independent Git repositories. The foundation stays a separate owned fork.
[Status](implementation-status.md),
[limitations](application-adoption-limitations.md) and
[operator commands](application-operations.md) define the qualified boundaries.

Create the isolated, hash-locked operator environment with the public
[selected local operator toolchain](operator-toolchain.md) recipe; do not modify
global Python or PATH. For release operations, use the exact interpreter and
source recorded by the selected kit's `operator-setup.json`.

## Prepare an isolated downstream workspace

The application-adoption kit contains `source.zip` for the updated independent
host operator/tools, three Git bundles, portable app-set recipes and archives,
selected images, source notices and an offline Windows Python/wheel toolchain.
Its manifest qualifies the AP-03 app set; the final AP-04 delivery receipt binds
the separate clean-workflow checks to the exact kit checksum. Checksums detect
changed bytes; they do not authenticate an unknown publisher.

Use the kit at `.local/releases/foundation49-application-adoption` in this
checkout. For a new workspace, copy that directory or use its absolute path.
Run these commands with an installed Python interpreter; they do not modify it:

```powershell
$adKit = (Resolve-Path '.local/releases/foundation49-application-adoption').Path
$adWork = Join-Path (Get-Location) '.local/adoption-operator'
python -I "$adKit/scripts/verify.py" $adKit
python -I "$adKit/scripts/setup_operator.py" $adKit --workdir $adWork
$adPython = Join-Path $adWork 'operator/Scripts/python.exe'
$adSource = Join-Path $adWork 'source'
```

Setup refuses an existing workdir. Inspect a partial attempt rather than deleting
it or rerunning it blindly. Keep the OS-owned `private` child outside application
container mounts. Use the **new kit's host source**, which contains ADR0079's
native-job restore correction; the sealed49 kit/operator remains unchanged.

Clone one of the application bundles into any chosen developer folder:

```powershell
git clone "$adKit/applications/aurora-projects/source.bundle" '.local/my-projects'
git -C '.local/my-projects' config core.autocrlf false
git -C '.local/my-projects' status --short
```

Compare HEAD with `application-sources.json`. Bundles preserve the qualified
baseline/successor history and notices. They contain no executor store, runtime
credentials or database. Create a `codex/` branch for new work. Never copy engine
or framework source into the app. Preserve the app's LF attributes/notices.

## Author, package and inspect

An app has `plugin.toml`, `application.toml`, its native addon, LICENSE and
COPYRIGHT. Native list/form/search views and native object/window actions remain
the default. Use a separate declared extension for cross-app fields/models;
declare both package versions and native addon dependencies. A custom page is
still available when the app needs it; the build does not require one.

Change package and native versions together. Same version with different bytes
is refused. Declare only supported upgrade transitions and checkpoint/recovery
requirements. Initial Projects/extension bounds deliberately select foundation49
and Tasks0.2.3; future versions require a new immutable compatibility declaration
and evidence. This is not an external Odoo compatibility promise.

```powershell
& $adPython -I "$adSource/tools/package_application.py" `
  --source '.local/my-projects' --recipe application.toml `
  --output '.local/dev.aurora.projects-NEW.mplug'
```

The output must be a new file in an existing directory. This validates archive,
manifest, native version, source layout and declared ownership without importing
native application code. It grants neither trust nor installation. Record the
returned digest with the app's reviewed commit. Do not rename changed bytes to
an old immutable version or bypass an archive rejection.

## Compose a system release

Start with the portable final recipe
`releases/projects-tasks-0.1.1-fixed/release.toml` in the kit. Copy its directory
to an owned working folder; put any successor archive in its `artifacts` child
and update only the selected path/digest. Each system has its own explicit recipe.
Projects-only and recovery-baseline recipes are included as separate profiles.
The historical integration0.1.0 is retained for recovery qualification; use0.1.1
for new development because it fixes hidden names in debug denial messages.

The original sealed49 kit is an explicit prerequisite for **recomposition**.
Use its unchanged manifest, image and inventory pins from the recipe. Loading
the adoption kit's `images.tar` is enough to run its already composed app set;
recomposition additionally needs the original foundation kit/image.

```powershell
$adFoundation = (Resolve-Path '.local/releases/foundation-r1-core49-tasks').Path
& $adPython -I "$adSource/release/compose_application_set.py" `
  --foundation-kit $adFoundation --recipe '.local/my-system/release.toml' `
  --output '.local/my-system-composition-01' `
  --receipt '.local/my-system-composition-01.json'
```

Outputs/receipt/tag must be fresh. The composer uses the exact base image, no
network build step or app import, and checks native/package closure, ownership,
versions and core/environment retention. Only selected app files/archives and
derived policy/inventory may change. A new native app version needs a new image;
unchanged foundation code/version does not imply an unchanged image. Build
success grants no trust, approval or database installation.

## Test the actual package

Static validation is a prerequisite, not complete native view/ACL qualification.
There is no standalone form RNG in this substrate. Perform a disposable,
independently approved actual installation to validate registry fields/methods,
inherited forms and server rights. Test ordinary and denied direct requests,
current revocation, search/count/group/display errors, native browser workflows,
and populated checkpoint/upgrade/restore/separate resume for persistent changes.
Assert real effects, not only queued jobs or running workers.

The delivered source retains generic authoring/packaging fixtures and regression
tests under `tests/`. Product-bound adoption and release qualification helpers
that require private application material are not included in the public tree and
are not supported public developer entry points. Any retained once-only scenario
inspects prior effects before continuation; never delete a marker to retry.

### Run the host checks

The reproducible host check entry point is `tests/run_host_regression.py`, run
with the isolated interpreter created by the public
[selected local operator toolchain](operator-toolchain.md) recipe (this
development checkout uses `.local/toolchain/operator-python16/Scripts/python.exe`).
Do not modify global Python or PATH. Use a project-owned temp directory so test
temporaries do not land in the checkout (some agent shells cannot write the OS temp
directory):

```powershell
$py = '.local/toolchain/operator-python16/Scripts/python.exe'
$tmp = Join-Path (Get-Location) '.local/tmp'
New-Item -ItemType Directory -Force $tmp | Out-Null
$env:TMPDIR = $tmp; $env:TEMP = $tmp; $env:TMP = $tmp
& $py -I tests/run_host_regression.py
```

Ripgrep is required for the real byte-scan assertion in
`tests/test_secret_scan.py`. Install `rg` on `PATH`, or set
`MP_SECRET_SCAN_RG` to a local executable; it is resolved as one argv element
(no shell). A missing or invalid executable fails the scan closed rather than
skipping it or substituting a text scan:

```powershell
$env:MP_SECRET_SCAN_RG = 'C:\path\to\rg.exe'
& $py -I tests/run_host_regression.py
```

These are bounded checks, not a release or qualification claim; remaining
failures stay explicit rather than being presented as a green baseline.

Human usability, long-term production load and real-data migration remain
separate work. Text edits use native last-save-wins. Application role rows restore
to checkpoint; current native authentication revocation has its own qualified
overlay. No generic post-checkpoint business-ACL overlay is claimed.
