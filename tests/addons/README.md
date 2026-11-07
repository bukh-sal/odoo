# Native regression fixtures

These are explicit test inputs, excluded from production discovery and images.
Select this root with `--addons-path` when running native source regressions.
Twenty-two inherited ORM/access/HTTP/assets/conversion/uninstall fixtures remain.
The former merchant/Enterprise main-flow suite required five removed business
apps; `test_foundation_flow` covers an owned identity/record/native-view flow.
`mp_feas` retains the original feasibility fixture.

`rpc` is a test-only legacy transport helper for `test_rpc`, `test_http` and
historical authentication regressions. It is not auto-installed or included in
the runtime distribution. Keeping a regression helper does not offer legacy
wire protocols or external Odoo compatibility as a platform feature.
