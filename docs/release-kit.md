# Local R1 release kit rehearsal

G7 is in progress. The kit remains a draft until its operator setup and clean
application installation are actually qualified. [Status](implementation-status.md)
is authoritative; [ADR0053](architecture-decisions/0053-local-release-kit.md)
defines the artifact and trust boundaries.

The producer uses the selected Python3.12.16 operator, a committed source tree,
the exact qualified local images and an independently selected catalog/trust
file. For the current disposable qualification, create one fresh destination:

```powershell
.local/toolchain/operator-python16/Scripts/python.exe -X utf8 release/assemble.py --output .local/releases/r1-0.1.23 --catalog .local/g7-fresh-release-01/target21/operator/catalog --trust .local/g7-fresh-release-01/target21/operator/trust.json --receipt docs/evidence/G7/20261104-release-kit-01/assembly.json
```

The producer refuses an existing destination and records its phase/components.
On failure, inspect that record and the actual process/diagnostic before any
continuation. Do not rerun it hoping an existing partial directory will work.
No live application data or executor authority is copied. Native plugins and
same-origin pages are trusted; reference digest curation never grants execution
approval.

Once assembled, verify the kit before consuming its files:

```powershell
python release/verify.py .local/releases/r1-0.1.23
python .local/releases/r1-0.1.23/scripts/setup_operator.py .local/releases/r1-0.1.23 --workdir .local/release-kit-rehearsal
```

The initial `python` needs a trusted Python3.12-or-newer installation only for
standard-library verification/extraction. The selected Windows interpreter and
hash-locked binary wheels then create a fresh project-local operator without
global Python/PATH/registry changes or runtime pip dependencies. SDK private
directory checks run after setup. Existing workdirs are refused.

Checksums detect corruption against an operator-selected trusted inventory;
they do not authenticate a publisher against an attacker replacing the entire
kit. The source ZIP records its Git commit. Follow the documented native
code/permission review when importing reference archives into a new catalog.

Application initialization/install commands and the twelve operational
runbook cases in spec24.4 are the next qualification work. This document does
not yet claim that draft assembly or operator setup proves a clean application
installation. Standard record screens remain native Odoo; Canvas stays minimal.
