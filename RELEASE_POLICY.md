# Release and versioning policy

Use immutable research snapshot tags such as `research-YYYY-MM-DD` (add a suffix for multiple snapshots). Record source revisions, data provenance, environment, parameters, tests and limitations. Do not treat synthetic tests as experimental validation.

## Release checklist

- Identify the exact commit and review the intended changes.
- Preserve existing version files, changelogs and release automation; update them only when applicable.
- Run the project's relevant checks and document failures or unavailable checks explicitly.
- Record scope, verification evidence, known limitations and rollback or recovery instructions.
- Do not publish a release, deploy, or claim successful validation solely because documentation changed.

Existing tags and historical versions remain authoritative. This policy does not itself create a release or change a version.
