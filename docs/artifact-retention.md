# Disposable runtime retention

Retire project-owned one-shot containers after their result and useful diagnostics
have been captured. A passing test does not require keeping its container forever.
Before removal, confirm exact ownership, terminal state and absence of a continuing
runtime role. Never use global Docker prune or remove unrelated assets.

Keep active application/database/proxy runtimes, database and filestore volumes,
current image locks, and image/configuration inputs needed by recorded recovery
checkpoints. Retire a worker's synthetic public-config volume after its last
container is removed and no integration or recovery step still needs it. Keep
issuer material outside worker mounts and outside tracked evidence.

For image retirement, preserve every remaining container image reference and all
current private state/target/checkpoint-manifest and worker image-lock references.
Only remove unused project-owned stage tags after that reference check. Preserve
source/dependency/license/build records; do not claim that tag removal necessarily
reclaims all shared layers or build-cache bytes.

Small metadata/diagnostic archives can replace retired containers. These archives
may contain private runtime configuration and remain under the protected, ignored
`.local/retired-docker-20261101` directory. Public evidence records counts and
ownership checks, never raw environment variables, tokens or request text.

Apply this retirement step as fixtures finish. Review retained deployments and
recovery inputs again at G7 so temporary qualification infrastructure does not
become permanent. A known per-container Docker operation that cannot complete is
recorded separately; do not restart the shared daemon to clean up one asset.
