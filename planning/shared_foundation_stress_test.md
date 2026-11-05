# Shared foundation stress test

The test is whether two independent systems can adopt the same versioned foundation update while keeping their own installed apps, records and access rules. Use stock Odoo navigation, actions and declarative views. A framework-neutral page remains available where an app needs one. UI redesign can follow the foundation test.

| System | First workflow | What it tests |
| --- | --- | --- |
| Maintenance | Register a piece of equipment, open and advance a maintenance request, and check an authorized user and a denied user | Carry an existing upstream Odoo app and its dependencies through the foundation build and upgrade |
| Aurora Tasks | Create a list and stages, add and assign a task, and check owner, member and outsider permissions | Package an application-specific workflow on the shared foundation with standard Odoo screens |

The Aurora slice comes from the committed `bedrock-2.2` Tasks models. Its list owner manages membership and archive/delete actions. Members can see and edit the list. Task access also considers its creator and assignee. Start with synthetic lists, members, stages and tasks. Record the rules selected for the slice before implementing them. Accounting references, reminders, notifications, attachments and historic data migration belong to later slices.

## Execution and evidence

1. **Qualify upstream app admission.** Compute Maintenance's manifest closure and test its actual imports offline. Record any dependency absent from the manifests and distinguish packaging a helper from activating a hosted integration. Exercise registry initialization, native views and access rules before admitting the app.
2. **Prove both native workflows.** Package the selected Aurora slice and install it and Maintenance in separate disposable deployments. Verify the standard Odoo WebClient, app menus and record actions. Carry explicit workspace and release context for platform records and verify viewer denial and two-tab isolation. Verify any upstream app with its actual Odoo record rules. Workspace and Odoo company are separate authorization concepts.
3. **Apply the shared foundation update.** Pin one baseline and one successor foundation artifact across both deployments. Give each deployment its own release lock, database, approval and checkpoint. Verify both adopt the same successor while preserving their different app sets. Compare persisted records, assignments, membership, access denials and the everyday workflow before and after.
4. **Prove independent recovery.** Inject a bounded update failure in one disposable deployment. Recover it from its checkpoint and verify that the other deployment continues on the successor. Record each project-specific change or manual step.

The pass requires both real workflows and the shared update. Import smoke, copied source trees and the earlier single-workspace Notes relay are inputs to this test. See the [R1 handoff](../docs/r1-handoff.md) and [native WebClient preview](../docs/evidence/G7/native-webclient-preview/README.md).

## Current checkpoint

**Upstream admission preflight passed.** The manifest closure added `html_editor`, `mail` and `maintenance`. That set failed to import because the editor imports IAP directly. Including the pinned IAP addon let a fresh database install all four addons without a network path beyond its own local PostgreSQL connection. A Maintenance manager created equipment and advanced a request, an unrelated user was denied on search and direct read, and Odoo returned the stock list and form definitions. The temporary database, containers and probe image were retired. [Probe evidence](../docs/evidence/post-r1/shared-foundation/maintenance-admission.json)

**Aurora source** is the committed `bedrock-2.2` snapshot at `e48e04ed4cf155a83e66e08dfb33a669ebb5c228`. The local checkout was inspected read-only. The selected slice is still at workflow definition.

**Active item** is the Aurora native workflow and the stock WebClient integration needed to exercise it. Implement the list-bound Tasks slice first. Use an explicit test matrix for list owners, list members, assignees and outsiders. Keep standalone personal tasks outside this slice. In the Maintenance deployment, verify the stock WebClient and platform coexistence before the common update. The database probe establishes native ORM behavior. Browser behavior, the shared update and independent recovery are pending.

To repeat the native database probe from this repository:

```powershell
& .local/toolchain/operator-python16/Scripts/python.exe -I docs/evidence/post-r1/shared-foundation/maintenance_import_probe.py --registry --receipt .local/foundation-stress/maintenance-registry-next.json
```
