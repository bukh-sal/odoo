# Core change ledger

Record general requirements before implementation and retain the supported
security, lifecycle and recovery contracts. A proposed fix is not qualified
until its tests and review are recorded. App-specific core changes are refused.

| ID | Date | Requesting work item | Requirement | Change | Class | General? | Contract | Tests | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CR-0001 | 2026-11-10 | Host operator initialization | Create a private store beneath a Python-created private parent on Windows | Normalize the OWNER RIGHTS grant only on a freshly created, empty control directory before writing control data; retain the original verifier and existing-directory refusal | defect | yes | Existing OS-identity and exact operator-directory permission policy; no trust/approval change | Independent Windows operator/store/approval/concurrency/recovery:33 passed,0 skips;affected implementation run:124 passed;actual exact ACL,existing-path no-mutation,command-failure and process-lock checks pass | Accepted for the existing Windows permission contract;verifier/identity/lock nodes unchanged;POSIX branch unchanged but not executed in this qualification |
This entry qualifies the directory-initialization repair, not the entire host baseline. The full host run still has separately recorded private-fixture and intermittent worker-transport failures; no full-suite pass is claimed.
