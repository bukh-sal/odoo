# Upstream patch ledger

No ORM, authentication, registry, loader or frontend substrate patches made. Platform additions remain separate.

| File | Reason | Rejected alternative | Verification | Merge risk | Removal condition |
| --- | --- | --- | --- | --- | --- |
| `.gitignore` | Ignore generated local secrets/state; allow tracked product Docker/Node configuration otherwise hidden by upstream global patterns | Force-add every future file and risk hidden dependency locks | `git check-ignore` plus clean staged-file inspection before commits | Low; append-only product packaging rules | Upstream patterns no longer hide required product configs |
