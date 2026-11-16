# GitHub publication checklist

## Before staging

- [ ] Run the full Python regression suite inside `.venv`; confirm final `OK`.
- [ ] Run `npm run build` inside `frontend/`.
- [ ] Review the root `README.md` for stale version/status claims; link to `docs/GITHUB_RELEASE_GUIDE.md`.
- [ ] Review the tracked file list for `.env`, API keys, prompts, traces, private code, generated output, archives, and local artifacts.
- [ ] Decide which synthetic benchmark fixtures are safe and appropriate to publish.
- [ ] Keep existing incomplete benchmark results as historical artifacts **outside** the public commit unless reviewed and intentionally published with clear caveats.
- [ ] Review licensing and attribution before publishing.

## Safe, non-destructive inspection commands

```bash
git status --short
git ls-files | grep -Ei '(\.env|secret|token|key|trace|result|checkpoint|node_modules|\.venv|__pycache__|\.zip$)' || true
git diff --stat
git diff --cached --stat
```

If a sensitive file is **already tracked**, `.gitignore` alone will not remove it from Git history. Inspect it and decide on `git rm --cached <path>` before committing; rotate exposed credentials. Do not delete local files or rewrite history without reviewing the consequences.

## Suggested staging workflow

```bash
git add .gitignore docs/GITHUB_RELEASE_GUIDE.md docs/PUBLICATION_CHECKLIST.md
git diff --cached --check
git diff --cached --stat
```

Do **not** run `git add .` blindly, force-push, or publish until the tracked files have been inspected. Commit/push only after reviewing the staged diff.
