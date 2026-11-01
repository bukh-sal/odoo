# Document statistics metadata reference

This is the metadata-only `org.example.document_stats` provider package. It declares
analysis API1.0, the `analysis.run` capability, an independent endpoint configuration
reference and the actual locked worker image digest. Assembly includes only TOML,
the unchanged frozen worker DTO schemas, notices, provenance and inventory.

There is no native addon, frontend page/code, Python dependency list, executable
deployment template, URL, credential, mount or launch command. Native connector code
belongs to `org.example.notes_stats`. Both unpublished reference packages now require
platform0.1.12, which fixes cancelled bridge claims and preserves service failure codes.

The operator separately provisions the scope/public key and starts the pinned
Compose worker, then independently approves its endpoint/image generation. Package
validation does not do any of that, and metadata suspension/unregister must not be
presented as stopping the process or erasing remote data. The normal native install
materializer explicitly rejects this artifact rather than fabricating an addon.

Actual metadata registration/lifecycle and current endpoint/binding integration are
the next G6 deliverables. The assembler/validator proof is not their acceptance.
