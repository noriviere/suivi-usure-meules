# AGENTS.md

## Agent skills

### Issue tracker

Issues live in GitHub Issues on `noriviere/suivi-usure-meules`; tickets are created by `/to-tickets`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Workflow

Adding or changing an application function: one thread per change, running these skills in order, none skipped: `grill-with-docs` → `to-spec` → `to-tickets` → `implement` → `code-review` → `retro`. Size each ticket to fit one agent session comfortably; use as few tickets as that allows. Agent context and tooling changes (this file, CI checks, hooks) need no thread of their own.

Every pull request body is written with the `pr` skill (`.claude/skills/pr`), followed by the « Vérifications » checklist of `.github/pull_request_template.md`.

## Where things are

- Coding rules: `CONTRIBUTING.md` (two are enforced by `tests/test_regles_code.py`).
- Domain vocabulary: `CONTEXT.md`.
- Writing an entry to the workbook: `backend/services/ecriture.py` (`ajouter_ligne`), with adapters `classeur_excel.py` (production) and `classeur_openpyxl.py` (demo, tests). Reading it: `donnees.py`, `listes.py`, `reglages.py`.
- Checks before committing: `.githooks/pre-commit` (pyflakes + tests). Cloud sessions enable it automatically (`.claude/hooks/session-start.sh`); elsewhere run `git config core.hooksPath .githooks` once per clone.
