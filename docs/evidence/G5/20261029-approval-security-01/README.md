# G5 SEC-07 independent approval qualification

The 17-case CLI matrix reads the current owned HTTP deployment's actual immutable image and PostgreSQL state. It uses a new owner-protected control store and copies of the independent target/catalog/trust inputs. Existing deployment configuration, approval stores and application data are untouched. No install, suspension, native child or restore is executed.

Cases cover wrong exact hash, default 900-second start lifetime, idempotent review without extending expiry, cross-operation/workspace hash replay, unapproved apply, changed policy/authorization/allowlist/worker/image/generation/site/trust/artifact, real wall-clock expiry, revocation after reservation but before mutation, revoked apply and final revocation. All four test operations end revoked, with mutation false and no execution stage. Full observed state, business data and schema equal their before snapshots.

`source-Windows.json` combines 41 unchanged passing checks from the initial 44-test run with the three corrected new tests. Only those three were rerun after diagnosing fixture setup/cleanup errors; the unchanged product and existing test sources have exact matching hashes. `source-Linux.json` records all 24 store/plan/new-boundary tests on UID10001 with read-only current source, no network and no live/private mounts. The existing Windows contract checks cover canonicalization/golden fixtures. The 87 frozen contract files remain unchanged.

The new tests establish exact expiry after reservation, full base/security/catalog/binding/endpoint/policy/target revalidation before mutation, and rejection of a valid approval transplanted onto another operation. Existing store checks establish expiry during already-started work does not kill the migration, final revocation, consumption and recovery retirement. Positive actual native lifecycle/completion/recovery evidence remains at its qualified G5 paths; no native operation was replayed for this matrix.

Retained diagnoses:

- Initial changed ZIP footer was correctly rejected by strict preflight before the expected digest error. `attempt-archive-footer.json` records this harness expectation mismatch. After reconciling both prepared journals and restoring exact inputs, a changed payload byte confirmed outer digest rejection.
- Three new test fixtures initially used an inconsistent catalog digest. Corrected it to the actual release plugin digest.
- Their snapshot helper initially left SQLite readers open: connection context management does not close the handle. Explicit `contextlib.closing` fixes Windows cleanup, with no product code change.
- First Linux runner omitted the readonly tools import dependency and failed before tests ran. The failed named container is retained; the corrected runner adds only the required readonly source mount.

`matrix.py` is the original once-only attempt; `resume_matrix.py` is the reconciled continuation, not a fresh setup. Both now refuse repetition. Preserve `.local/g5-approval-security`, its four revoked operations, failed diagnostics and named source-test containers. Inspect markers/journals before any continuation. Reproduction uses fresh separately named targets, never resets these records.

SEC-08 application identity/privileged filesystem access remains a separate criterion. No contract, backend runtime, native CRUD screen or Canvas feature changes are included here.
