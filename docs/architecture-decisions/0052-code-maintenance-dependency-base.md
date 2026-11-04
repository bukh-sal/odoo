# ADR0052: preserve the immutable dependency environment during code maintenance

Date: 2026-11-04. Status: accepted; actual candidate qualification pending.

The first core23 build was refused by the existing staging guard: unchanged
dependency lock/versions, but different actual psycopg2 and python-ldap native
binaries. A prior independent no-cache build had refreshed Docker's builder
cache; the next normal cached build reused those independently compiled wheels.
Their actual distribution digests differ from the deployed core22. Do not hide
this difference, alter the lock merely to pass, or weaken the guard. Retain the
rejected inventory and build record; do not deploy it.

For code-only maintenance, optionally build from an operator-selected exact
qualified application image using `deploy/Dockerfile.core-maintenance` and
`tools/build_candidate.py --dependency-base-image sha256:...`. The build requires
the identical dependency lock and an intact inventoried base. Materialize the
complete current allowlisted distribution afresh; replace the image's source
directory, preserving its dependency environment. No running container is patched.
Reinspect actual Python/interpreter/architecture/markers/lock/distribution hashes
after build and refuse any difference. Normal independent source delta, version,
catalog, staged approval, drain/checkpoint and client-release gates still apply.

The ordinary Dockerfile remains the fresh dependency-install build path. This
choice does not claim byte-identical independently compiled native wheels, remove
fresh-build qualification, or allow a code maintenance build to change dependencies.
Record and retain the exact dependency base as a release build input, including its
source/lock/notices/provenance. An unavailable base requires an explicit dependency
requalification, not a fallback to another tag or a guard bypass. Retire rejected
owned candidate images only after capturing diagnostics and proving no container
references them. No public contract or worker image change.
