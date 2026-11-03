# Locked proxy build

The selected R1 proxy is recorded in `deploy/runtime.lock.json` and
`deploy/compose.yaml`. It retains the pinned official nginx binary/base and
updates four signed Alpine packages. This locally built image is not published.
Build/load it before starting a new deployment; Compose must not substitute a
moving public tag.

Use the retained APK archive from the local release kit. During G7 the staged
archive is `.local/g7-support-images-02/proxy-apks.tar`; final release-kit
packaging/qualification remains pending. Its exact file list, sizes and hashes
are in `deploy/proxy-packages.lock.json`. Cache the pinned official base first
or obtain it with the other immutable release images.

From the project root, using the isolated interpreter:

```powershell
.\.local\toolchain\operator-python16\Scripts\python.exe -X utf8 deploy/build_proxy.py --apk-archive .local/g7-support-images-02/proxy-apks.tar --output .local/proxy-build-new --tag modular-platform-proxy:r1-local
```

Choose a new output directory/tag for each build. `--prepare-only` validates
the inputs and writes a deterministic context without creating an image.
The builder rejects extra/missing/duplicate/changed APK inputs and recipe drift;
Docker installs with normal Alpine signature verification and no build-step
network. The output directory retains context, logs and build record. No runtime
volumes, credentials, databases or private operator stores enter this context.

Compare the actual new image/package inventory with the declared lock and
qualify ingress before independently selecting a different image digest.
Native recompilation/build metadata need not produce an identical image ID;
the retained selected image remains the exact byte-preserving recovery target.
Keep one current and the required checkpoint images. Retire exact failed or
superseded project-owned build targets after diagnostics, without global prune.
