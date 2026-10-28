# ADR 0004: contract v1 revision 2 validation correction

Status: accepted; G2 requalification required before further product qualification.

Trigger: implementation review found that the minimal jsonschema dependency set does not install its optional RFC3339 validator. Passing FormatChecker alone could therefore accept an invalid calendar date despite the frozen UTC requirement. Also, the role matrix used unqualified workspace-administration capability names, while cross-provider capabilities are specified as fully qualified.

Correction: explicitly register a strict UTC-Z date-time checker using Python's standard datetime calendar validation, including fractional seconds for note timestamps. Existing plan/approval schemas still require whole seconds. Replace the two workspace-administration entries with `org.modularplatform.identity:workspace.members.manage` and `org.modularplatform.identity:workspace.config.manage`. Their role authority is unchanged; ordinary Notes capabilities remain local to Notes. Add a compatibility test for impossible dates, offset timestamps and the core capability owner.

This is a contract-major-1 validation/metadata correction, inventory revision2. No valid previously specified canonical UTC message or valid authority interpretation changes, and no deployed/public consumer exists. Golden plan bytes/hash, DTO shapes, token protocol and G1 behavior remain unchanged. New code cannot rely on the overly permissive validator or ambiguous local names. G2 is invalidated during the edit, then requalified with the full small contract/type/digest suite. G3 remains open. No reason exists to repeat R0 lifecycle or G1 browser tests, whose loaded code does not use these G2 validators/role entries.
