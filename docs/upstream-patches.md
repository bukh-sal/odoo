# Upstream patch ledger

No ORM, authentication, registry, loader or frontend substrate code patches made. Platform additions remain separate. Generated distribution metadata patches are included in the runtime inventory with original hashes.

| File | Reason | Rejected alternative | Verification | Merge risk | Removal condition |
| --- | --- | --- | --- | --- | --- |
| `.gitignore` | Ignore generated local secrets/state; allow tracked product Docker/Node configuration otherwise hidden by upstream global patterns | Force-add every future file and risk hidden dependency locks | `git check-ignore` plus clean staged-file inspection before commits | Low; append-only product packaging rules | Upstream patterns no longer hide required product configs |
| `odoo/addons/base/data/ir_module_category_data.xml` (generated distribution only) | Base bootstrap references categories normally generated when discovering excluded business addons; first curated boot failed on `base.module_category_services_timesheets` | Shipping ERP code just to create categories, deleting catalog records, or modifying ORM/loader behavior | `python -m unittest discover -s tests -p test_distribution_metadata.py`; fresh curated boot required | Low; static reference closure; builder fails if XML layout changes | Upstream base data becomes self-contained without full addon discovery |
