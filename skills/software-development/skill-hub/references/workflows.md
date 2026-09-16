# Hub workflows

## Install a skill — download the .zip and unpack it (default)

The files do not have to travel through the conversation to reach the disk, and
when they do you pay for them twice: once emitting them, then again in every
later turn that carries the transcript. A 40-file skill is the same one command
per skill as a 2-file one.

1. `download_skill_zip({ id, runtime })` →
   `{ install_dir, downloads: [ { skill, folder, version, command, url, dependency }, … ], lock, expires_in_seconds }`.
2. Run each `command`, **in the order returned** — dependencies come first:
   ```bash
   curl -fsSL "<url>" -o appmagic.zip && unzip -oq appmagic.zip -d .claude/skills/ && rm appmagic.zip
   ```
   Each archive already contains its own `<folder>/` at the root, so unpacking
   into `install_dir` puts `SKILL.md` exactly where the runtime looks for it.
3. Windows PowerShell, if `curl`/`unzip` are not there:
   ```powershell
   Invoke-WebRequest <url> -OutFile x.zip; Expand-Archive x.zip -DestinationPath .claude/skills/ -Force; Remove-Item x.zip
   ```
4. Run them **now**. Each URL is a one-shot ticket that expires in ~15 minutes
   and carries no token — that is what lets a plain `curl` work at all. A link
   that is spent or stale answers `401`; call `download_skill_zip` again rather
   than trying to repair it.
5. `lock` pins each node `{ full_name, version, digest }` — persist it (e.g.
   `skillhub.lock`) so the install is reproducible.
6. Nothing else is needed to record the install: fetching the file is the
   install. (`record_skill_usage` is separate — send it after you RUN the skill.)

### When to use `install_skill` instead

When you need the contents **in the conversation**: reviewing a skill's files
before trusting it, or rewriting one on the way in. To look at a single file,
`list_skill_files` + `read_skill_file` is cheaper than either.

1. `install_skill({ id, runtime })`.
2. Pick the base dir: `dir = result.place[runtime]` (default `.claude/skills/`).
3. For each `node` in `result.nodes`:
   - `installName` = the node's name (part after `/`); on a name clash the hub
     already mangled it — use the name as returned.
   - Write every `path: content` in `node.files` to `dir + installName + "/" + path`.
4. Dependency nodes have `hidden: true` — still write them; the parent needs them.
5. `result.lock` pins each node `{ full_name, version, digest }` — persist it
   (e.g. `skillhub.lock`) so the install is reproducible.

## Author + upload a skill

### The folder you have on disk, and a shell — POST it (fastest)

Nothing is retyped, so cost does not scale with the skill. Two routes, same
service as `upload_skill_folder`, same `ash_` token, same response:

```bash
HUB=https://skillhub.pixon.cc     # connector URL minus /mcp

# Token in a curl config file, not on the command line — out of shell history,
# out of `ps`, and it does not trip the hub's own credential-exfil gate.
printf 'header = "Authorization: Bearer ash_YOUR_TOKEN"
' > auth.conf && chmod 600 auth.conf

# a) archive. Keep it beside the folder — on Windows the shell's /tmp and
#    python's /tmp are different directories, and the upload reads an empty path.
zip -qr my-skill.zip my-skill
#    without a `zip` binary:
#    python -c "import shutil;shutil.make_archive('my-skill','zip','.','my-skill')"
curl -s -K auth.conf -X POST "$HUB/api/skills/folder/zip" \
  -F "file=@my-skill.zip" -F "changelog=what changed"

# b) JSON: {namespace, name, version, changelog, files{path:content}} built
#    from `os.walk` — use when you want the fields set explicitly.
curl -s -K auth.conf -X POST "$HUB/api/skills/folder" \
  -H "Content-Type: application/json" --data-binary @body.json
```

The archive may be rooted either way (at the skill folder, or at its parent); an
archive holding several skills is refused rather than guessed at, and `name`
picks which one. There is no `file_count` on these routes — the guard exists for
a payload typed from memory, and a glob has already said what whole means.

Round-trip check, because a 201 is not a diff:
```bash
curl -fsSL -K auth.conf "$HUB/api/skills/you/my-skill/zip" -o check.zip
unzip -q check.zip -d check && diff -r check/my-skill my-skill
```
`Only in my-skill: .git` and friends are expected — that is the junk the hub
dropped, and it matches what came back in `skipped`. Anything else missing is a
real short upload.

### No shell — `upload_skill_folder`

A hosted connector has no terminal, and files you generated in-conversation are
not on disk. Then the tool is right, and the payload is your own output:

```
ls -R my-skill/            → 7 files → file_count: 7
read each one              → files: { "SKILL.md": …, "references/guide.md": … }

upload_skill_folder({ file_count: 7, files: { … } })
```
`SKILL.md`'s frontmatter *is* the manifest — `name` (kebab-case) and
`description` are required there, `version` optional (else the patch bumps).
Paths are relative to the folder holding SKILL.md; a `my-skill/` prefix is
trimmed for you. Nothing else to declare: deletions are worked out against the
previous version and returned in `removed`, junk and binaries in `skipped`.

`file_count` is the entire truncation guard, and it only guards if it comes from
the **directory listing**. `file_count: Object.keys(files).length` restates the
payload and can never fail — the situation where 13 of 19 files published as a
complete version, returned 200, and moved `latest_version` with nothing
reporting a problem.

Use `upload_skill` (below) when the manifest has to carry something SKILL.md
cannot: an orchestration's pinned `dependencies`, `kind`, `provides`,
`workspace_id`.

### Manifest schema — `upload_skill({ manifest, files })`
```jsonc
{
  "id": "namespace/name",        // immutable, kebab-case, unique
  "version": "1.0.0",            // semver, immutable once published
  "kind": "leaf",                // or "orchestration"
  "visibility": "private",       // private | workspace | department | org
  "workspace_id": "",            // required when visibility = workspace (you must be a member)
  "description": "one line",
  "runtimes": ["claude-code"],
  "dependencies": { "ua/appmagic-research": "1.0.0" }, // orchestration only; EXACT versions
  "contents": ["SKILL.md", "scripts/run.py"],  // REQUIRED: every file, listed from disk
  "removes": ["assets/old.md"],                // required to drop a file the last version had
  "changelog": "…"
}
```
`files` is `path → content` and must include `SKILL.md`. A `scripts/` file makes
the skill `scripted` tier (extra review to share). Uploads are `private`; to
share, promote from the dashboard (or with `skill:publish:dept|org`) — a static
gate scans it, prompt-only skills auto-publish, scripted ones go to human review.

### Get `contents` right — this is the step that fails

Build the list by **listing the directory**, then send exactly those files:

```
ls -R skill-folder/          →  the packing list  →  manifest.contents
                             →  read each file    →  files
```

Not `contents: Object.keys(files)`. The point is to compare two independently
produced lists: what the skill *is* (disk) against what *arrived* (payload). Derive
one from the other and you have a check that can never fail — which is exactly
the situation where 13 of 19 files published as a complete version, returned 200,
and moved `latest_version`, with nothing anywhere reporting a problem.

### Decide upfront: one call, or a draft?

Sum the bytes you are about to send. Past roughly **100KB of file content** a
single call is unreliable — not because the hub refuses it (its limit is 32MB)
but because your own output budget runs out mid-map, and a truncated payload is
still valid JSON. Use the draft flow instead:

```
create_draft({ manifest })                     // declares contents; publishes nothing
add_draft_files({ draft_id, files: {...} })    // repeat; check progress.missing
publish_draft({ draft_id })                    // refuses unless complete
```

Nothing is visible and `latest_version` does not move until `publish_draft`
succeeds, so retrying costs nothing. A one-shot `upload_skill` has no such
safety: every attempt that reaches the server publishes.

### Verify before you report success

```
list_skill_files({ id, version })   // count + digests of what actually landed
```
Check the count against your `contents`. Read the `warnings` in the publish
response — a `dangling-reference` finding means SKILL.md documents a file the
package does not contain, which is what a partial upload looks like from the
outside. If something is wrong and the skill is still private and uninstalled,
`delete_version({ id, version })` removes the bad version instead of leaving it
in the history.

Orchestration skills: pin each dependency to an exact version, and put a
**setup/preflight** step at the top of the parent SKILL.md that installs/verifies
the child skills before running the task, so the client never errors on a missing
dependency.

## Change a skill you own

Published versions never change, so every edit is a release. Two paths:

**A. Dashboard (Files tab).** The owner/maintainer/admin edits, adds or deletes
files on the skill's detail page and commits with a version + changelog. Only the
changed files are sent; the rest of the base version is carried over, and the
manifest (deps, runtimes, provides) plus visibility carry forward. The commit is
refused if: the version does not advance, someone published while they were
editing, `SKILL.md` would be deleted, a path escapes the skill, or the static
gate blocks the final payload. Adding a `scripts/` file re-derives the tier to
`scripted`.

**B. MCP (`update_skill_file`).** The same operation as the Files tab, and the
default for changing a skill that is already published:

```
list_skill_files({ id: "eng/my-skill" })                # -> latest_version, paths
read_skill_file({ id: "eng/my-skill", path: "SKILL.md" })
update_skill_file({ id: "eng/my-skill", base_version: "1.4.0",
                    files: { "SKILL.md": "...entire new text..." },
                    delete: ["references/old.md"], changelog: "..." })
# -> { version: "1.4.1", files, added?, updated?, removed?, warnings? }
```

Only the files you name are sent; the rest of the version and the whole manifest
are carried forward by the hub, which already has them. Content is the file's
entire new text — never a patch or a diff. The version bumps the patch number
unless you pass one.

`base_version` is the version you actually read from, and it is the reason to
read first rather than work from memory: if someone published in between, the
call is refused and names the version to re-read, instead of quietly reverting
their release. The same refusals as the dashboard apply — the version must
advance, `SKILL.md` cannot be deleted, paths cannot escape the skill, deleting a
file the base version does not have is an error, and the static gate runs on the
final file set.

**C. MCP (`upload_skill`, or a draft when it is large).** For publishing a
skill's full contents from disk. You must send the **complete** `files` map, and
anything missing from it is **deleted** from the new version — the hub refuses
that unless you name it in `manifest.removes`, so an accidental drop is an error
rather than a silent regression, but the rule still holds: send everything you
want to keep. Use `update_skill_file` instead when you are only changing part of
what is already published.

Editing someone else's skill is not this flow — fork it and open a pull request.

## Let another department use a skill you own

Three ways to widen a skill, and only one of them means "share it with them":

| Want | Tool | What it does |
|---|---|---|
| Marketing needs it too | `share_skill_with_department` | Adds Marketing as a reader. Visibility and department unchanged. |
| Everyone needs it | `set_skill_visibility({ visibility: "org" })` | Hands it to the whole company. |
| It belongs to Marketing now | `set_skill_department` | MOVES it — the old department loses it if the skill is department-visible. |

```
share_skill_with_department({ id: "eng/market-report", department_name: "Marketing" })
# -> { shared: true, shared_with: ["Marketing"] }                      done
# -> { shared: false, status: "human_review", request_id: "..." }      queued
list_skill_shares({ id: "eng/market-report" })
unshare_skill_from_department({ id: "eng/market-report", department_name: "Marketing" })
```

Sharing runs the same gate as promoting to `department`, so a scripted skill
queues for a reviewer — check `shared` before telling anyone the skill is
available to them. Un-sharing is immediate and needs no review.

## Improve someone else's skill (fork → pull request)

There is no way to post files at a skill you do not own. A proposal is a version
of YOUR fork, and a pull request is a pointer at it:

```
fork_skill({ id: "eng/base" })
# -> <your-namespace>/base, private, merge_base = eng/base's latest at fork time

# publish your change as a version of the FORK (folder on disk, or manifest form)
upload_skill_folder({ file_count: 7, files: { ...the whole folder... } })
# or: upload_skill({ manifest: { id: "you/base", version: "1.1.0",
#                                contents: [ ...from `ls -R`... ] }, files: { ... } })

open_pull_request({ head: "you/base@1.1.0", title: "…", body: "…" })
# -> { pull_request: { id, mergeable, conflicts }, static_passed }
```

Rules that bite:

- `head` must be `namespace/name@version` and that version must already exist in
  the fork. Publish first, then open.
- `base` is optional — it defaults to the skill the fork came from. You may only
  target a skill your head is actually a fork of.
- One open PR per (fork, upstream). To propose more work, publish another version
  and `update_pull_request({ id, head_version })`; the PR and its discussion stay.
- The PR carries no files, so nothing about it can be truncated: it names an
  immutable version that already passed `contents` / `removes` / the static gate.

## Keep your fork current (`sync_fork`)

The upstream moves. `sync_fork` 3-way merges its latest INTO your fork:
base = your merge base, ours = your fork's latest, theirs = upstream's latest.

```
sync_fork({ id: "you/base" })
# clean   -> publishes a new version of your fork and advances merge_base
# conflict-> returns { synced: false, conflicts: N, merge: {...} } and publishes nothing
```

To resolve, build the full file map and send it back:

- For every file with `conflict: false` and `present: true` → keep `file.merged`.
- For every file with `conflict: true` → read `file.base` (common ancestor),
  `file.ours` (your fork), `file.theirs` (upstream) and write ONE clean merged
  text preserving both sides' intent. Remove every `<<<<<<<`, `=======`,
  `>>>>>>>` marker. Do not simply pick a side unless that is truly correct.
- Files with `present: false` are deletions — omit them.

```
sync_fork({ id: "you/base", resolved_files: { "SKILL.md": "…", … } })
update_pull_request({ id: "<pr>", head_version: "<version sync_fork published>" })
```

Do this rather than leaving a conflicting PR for the owner: it is your
divergence, on your copy, where getting it wrong costs nothing.

## Review and merge a pull request (you own the skill)

1. `list_pull_requests()` — the queue waiting on you. Each row already carries
   `mergeable` (1 clean / 0 conflicts / -1 not computed) and `conflicts`, so you
   do not need to open a merge to triage.
2. `get_pull_request_merge({ id })` — per-file status against your CURRENT latest.
3. Clean → `merge_pull_request({ id })` (optionally a `version`). Done.
4. Conflicting → ask the proposer to `sync_fork` and re-point. If you must resolve
   it yourself, build the full file map exactly as above and:
   `merge_pull_request({ id, version, resolved_files: { … } })` — every file that
   should exist in the merged version, `SKILL.md` included.
5. The hub re-runs the static gate on the merged files, publishes a new version
   **credited to the proposer**, and advances the fork's merge base. A 409 on the
   version means pick a higher one.

`close_pull_request({ id, reason })` declines it; `comment_on_pull_request` and
`request_changes` talk to the proposer instead of silently sitting on it.

### Why "behind"
If the upstream published after the fork last synced, `merge.behind` is true and
`merge_base != current_version`. The 3-way merge already accounts for it: `ours`
is the *current* latest, so nothing the upstream changed gets silently reverted —
it surfaces as a conflict instead.

## Administration
Managing departments, employees, roles, yanking versions, reviewing promotions,
and setting install policy live in the separate **`skill-hub-admin`** skill (they
need admin/maintainer permissions). Use that skill for any org-management task.
