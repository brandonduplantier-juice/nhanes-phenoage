# Engineering guide

## 1. Project orientation

`src/`: analysis code; `data/`: input data; `results/`: outputs; `run_all.py`: pipeline; `app.py`: interface; requirements.txt: dependencies. Read README.md; preserve provenance and evaluation limitations.

## 2. Development workflow

1. Read the README (if present) and applicable project-specific instructions; inspect current status and open work.
2. Start from the appropriate current integration branch. Use feature/, fix/, docs/, refactor/ or release/ branches as appropriate.
3. Define acceptance criteria; implement focused changes and corresponding tests.
4. Run documented formatting, tests, build and security checks applicable to the change. Record actual results and blockers.
5. Open a pull request with scope, test evidence, risks and rollback notes. Review before merging; retain history.
6. Update relevant documentation and release notes. Follow existing deployment procedures; never deploy by assumption.

## 3. Documentation conventions

README is the entry point where available. Prefer linked architecture, status, roadmap, testing, deployment and handoff documents where useful. Reuse existing equivalents rather than duplicating them. Keep project-native paths and existing naming conventions until a tested migration is warranted.

## 4. Quality and security

Never commit secrets, personal data or local credentials. Use existing dependency and environment conventions. Do not fabricate test results, feature completion or deployment status. Avoid destructive changes and preserve production interfaces. Existing project-specific rules take precedence.

## 5. Pull request checklist

- [ ] Scope and acceptance criteria documented.
- [ ] Relevant tests added or updated; actual results recorded.
- [ ] Security, privacy and compatibility considered.
- [ ] Documentation updated when needed.
- [ ] Deployment and rollback implications recorded.
