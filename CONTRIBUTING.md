# Shared Montara development

`main` is the shared working baseline. Fernando, Codex and Claude work in their
own branches and integrate changes through pull requests into `main`.

Current branches:

- Fernando: `fernando/continuacion-montara`
- Codex: `codex/montara-038-handoff`
- Claude: `claude/montara-scaffold`

## Start or resume work

Commit or stash your pending work first. Then, from your own branch:

```sh
git fetch origin
git merge origin/main
git submodule update --init --recursive
```

Keep collaborators' commits and resolve conflicts explicitly. Do not force-push
shared history or overwrite another person's branch. For a new task, create a
new branch from current `origin/main` rather than reusing an already merged PR.

## Integrate into main

1. Update your branch from `origin/main`, then make and commit the change.
2. Run `python -m pytest tests -q` and the checks relevant to the change.
3. Push your branch and open a PR targeting `main`.
4. Wait for Linux E2E, inspect its screenshots and render evidence, and merge
   with a merge commit so collaborators retain the shared history.
5. Everyone updates their own branch from `origin/main` before continuing.

Keep engine and mixer code in their own repositories; Montara pins published
submodule commits. Do not commit local credentials, environments or generated
working data. Publishing to Vercel is separate from merging source into `main`.
