---
name: skill-hub
description: "Find, install, publish and improve skills on the PixOn hub."
version: 1.6.0
author: kiennt (@kienntpixon)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Skill Hub, Skills, Registry, MCP, Publishing, PixOn]
    category: software-development
    homepage: https://skillhub.pixon.cc
    related_skills: [pixi-artifacts, hermes-agent-skill-authoring]
---

# Agent Skill Hub

The hub is an **internal skill registry delivered as an MCP server**. Once your
MCP client is connected to it, the hub's tools appear as callable tools and you
operate the whole registry through them, scoped to your permissions. Everything
runs as *you* — the identity behind your MCP token.

- **On Pixi, read `references/pixi-runtime.md` first** — the connector is already
  provisioned for you, and skills install into Pixi's own skills directory, not
  `.claude/skills/`. It overrides the two points below.
- Connect once: `references/connect.md` (Claude Code / Desktop / Cursor config + token).
- Full tool reference with arguments: `references/tools.md`.
- Step-by-step workflows (install, upload manifest shape, 3-way merge resolution): `references/workflows.md`.

If the hub tools are **not** available yet, the client is not connected. On
Pixi that means the person has not been granted the `skillhub` app — a Pixi
admin grants it under Settings → App Connect (see `references/pixi-runtime.md`);
pasting a token will not help. On every other client, read
`references/connect.md` and help the user add the MCP server + token first.

## When to Use

Use this skill whenever the user wants to:

- **Find** a skill — "skill hub", "search skills", "có skill nào làm được X không".
- **Install** one — "install a skill", "cài skill từ hub", "tải skill về máy".
  Includes the full dependency closure.
- **Publish / share** their own — "publish a skill", "upload a skill folder",
  "đăng skill lên hub", "chia sẻ skill", "share with my department".
- **Improve someone else's** — "fork a skill", "open a pull request",
  "propose an improvement", "fork skill", "gửi pull request", "sync my fork".
- **Review** — "merge a pull request", "duyệt / merge PR", "resolve merge
  conflicts" (as the AI resolver).
- **Read or edit a skill's files** — "read the skill's source", "xem source của
  skill", "sửa file skill", "download a skill as a zip".

For hub **administration** — departments, employees, roles, yanking a version,
promotion review, install policy — use the separate `skill-hub-admin` skill
instead.

## The tools at a glance

| Group | Tools |
|---|---|
| Discover | `search_skills`, `get_skill` |
| Read source | `list_skill_files`, `read_skill_file` |
| Install | `download_skill_zip` (default), `install_skill` (when you must read the files) |
| Report use | `record_skill_usage` |
| **Publish (default — you have a shell)** | **not a tool: `POST {hub}/api/skills/folder/zip`** |
| Publish (no shell, small skill) | `upload_skill_folder` |
| Publish (manifest needed) | `upload_skill` |
| Publish (no shell, large — several calls) | `create_draft`, `add_draft_files`, `publish_draft`, `list_drafts`, `discard_draft` |
| Edit specific files | `update_skill_file` |
| Manage | `set_skill_visibility`, `set_skill_department`, `delete_skill`, `delete_version`, `transfer_skill_owner` |
| Share with departments | `share_skill_with_department`, `unshare_skill_from_department`, `list_skill_shares` |
| Document | `update_skill_docs` |
| Fork | `fork_skill`, `sync_fork` |
| Improve (PR) | `open_pull_request`, `update_pull_request`, `list_pull_requests`, `get_pull_request`, `get_pull_request_merge`, `merge_pull_request`, `close_pull_request`, `comment_on_pull_request`, `request_changes` |
| Health | `ping` |

(Tool names may be prefixed by the server, e.g. `mcp__skill-hub__install_skill`.)

**Publishing is not a tool call. Check for a shell before you reach for one.**
`POST {hub}/api/skills/folder/zip` (or `/api/skills/folder`) with your `ash_`
token sends the folder straight from disk — same service behind
`upload_skill_folder`, same rules, same response, but **no file content passes
through the conversation at all**. The publishing tools exist for hosted
connectors that have no terminal; if you can run `zip` and `curl`, they are the
wrong tool and the difference is not small. See core rule 3 and the recipe below.

**Administration** (departments, employees, roles, yank, promotion review,
policy) is a separate skill: **`skill-hub-admin`**. Use it for any org-management
or governance request — those tools are permission-gated to admins/maintainers.

## Core rules (do not violate)

1. **Versions are immutable and must advance.** Never reuse a published version
   string; a new version must be numerically greater than the current latest.
2. **A version is a whole snapshot, and you must say what whole means.** Every
   upload replaces the previous file set entirely — files you leave out are
   *deleted*. Which tool you use decides how you state it:
   - `upload_skill_folder` (a folder on disk, no shell — see rule 3): send the files plus
     `file_count`, the number of files **in the folder listing**. That one
     integer is the truncation guard; taken from the map you are sending instead
     of from disk, it guards nothing. Deletions are worked out for you and
     reported in `removed` — read that list, it is the folder speaking.
   - `upload_skill` (when the manifest carries something SKILL.md cannot —
     pinned dependencies, `kind`, `workspace_id`): the manifest must carry
     `contents`, every path the version holds, listed from disk; dropping a file
     the previous version had additionally requires `removes`.
   Neither is the tool for changing part of a published skill: use
   `update_skill_file`, which names only what changed and carries the rest
   forward server-side, so a file you never read cannot be lost by omission.
3. **Publish by transfer, not by retyping. This is the default path, not an
   optimisation.** Before any upload, ask one question: *is the folder on disk
   and can I run a command?* If yes, POST it and stop — do not open a draft, do
   not call `upload_skill_folder`. Those carry every byte of the skill through
   your own output.

   Measured, publishing a 26-file / 268 KB skill: **one curl** the right way;
   **26 tool calls and ~130k tokens of retyped file content** the wrong way,
   for a byte-identical result. The draft route also *looks* correct while it
   happens, which is why it gets chosen — the cost is invisible until it is
   spent. Reading this rule before the first upload of a session is the whole
   fix.
   - `POST {hub}/api/skills/folder/zip` — zip the folder, one `curl -F
     "file=@my-skill.zip"`. Simplest, and the shape `download_skill_zip` hands
     back, so download → edit → re-upload is a round trip.
   - `POST {hub}/api/skills/folder` — JSON `{namespace, name, version,
     changelog, files}` built from disk by a few lines of script. Use when you
     want to set fields explicitly.
   Both run the *same* service as `upload_skill_folder`, with the same rules,
   the same response (`added` / `removed` / `skipped` / `warnings`) and the same
   `ash_` token — the hub accepts it on REST and on `/mcp` alike. `{hub}` is
   your connector URL minus the trailing `/mcp`. Neither takes `file_count`:
   the guard exists for a payload typed out from memory, and a shell that
   globbed the directory has already stated what whole means.
   This is the install rule below, pointed the other way. Publishing a 39-file
   skill this way costs what a 2-file one costs.
4. **If you cannot use a shell, do not try to fit a big skill in one call.**
   A hosted connector has no terminal, and files you generated in-conversation
   are not on disk. There, `upload_skill_folder` is right — but your own output
   budget, not the hub, is what truncates a large skill, and a truncated upload
   used to publish successfully as a broken version. Above roughly 100KB of file
   content use `create_draft` → repeated `add_draft_files` → `publish_draft`:
   nothing is published and no version moves until the final call, so a failed
   attempt leaves no wreckage.
5. **Install by downloading, not by reading.** `download_skill_zip` returns one
   ready-to-run command per skill in the closure; each fetches a `.zip` straight
   to disk and unpacks it into the runtime's skills directory. No file content
   passes through the conversation, so a 40-file skill costs what a 2-file one
   costs. Run the commands in the order given — dependencies first — and soon:
   each link is one-shot and expires in minutes. Reach for `install_skill`
   (which returns every file inline) only when you actually need to READ the
   files — to review a skill before trusting it, or to patch one on the way in;
   to read just one, `read_skill_file` is cheaper still. Either way the hub has
   already resolved the dependency closure: never hand-resolve deps.
6. **Orchestration skills pin exact dependency versions** and carry a
   setup/preflight step; when authoring one, declare each dependency at an exact
   version in the manifest.
7. **Widening is not the only way to share.** A second department needing the
   skill is a `share_skill_with_department` call, not a promotion to `org` and
   not a department move — the first hands it to the whole company, the second
   takes it away from the department already using it.
8. **Visibility is earned, not declared.** Uploads land `private` by default.
   Raising to `department`/`org` goes through `set_skill_visibility` + the static
   gate. Holding `skill:publish:*` publishes a passing prompt-only skill on the
   spot; without it the call files a request a maintainer must approve, and
   scripted skills queue for everyone. Do not assume you can publish org-wide,
   and never report a queued request as published.
9. **You cannot send files at a skill you do not own.** Improving someone else's
   skill means forking it, publishing your change as a version of YOUR fork, and
   opening a pull request pointing at that version. There is no tool that posts a
   file map into another person's skill — `propose_skill_improvement` is gone.
   That is what makes a proposal reviewable: it is a real published version,
   already through the completeness check and the static gate, not a payload that
   might have arrived half-written.
10. **Merging is a real 3-way merge, and conflicts belong to the proposer.** base
   = the upstream version your fork is synced to, ours = the upstream's current
   latest, theirs = your fork's version. A clean merge auto-applies. When it
   conflicts, run `sync_fork` on YOUR fork, resolve there, and re-point the PR —
   do not hand conflict resolution to the skill's owner. See the workflow below.
11. **Report the skills you run.** When you finish a task where you used a skill
   that came from the hub, call `record_skill_usage({ id: "ns/name" })` once (add
   `count` if you ran it several times). Installs only prove a skill was fetched;
   this is the only thing that tells the hub which skills still earn their keep,
   and it drives the Usage ranking on Trending and the "Most used skills" board.
   It sends no content — only which skill, by whom, on which UTC day — never
   fails your task, and is counted per person per day, so one ping is enough.

## Quick recipes

**Find and install a skill**
```
search_skills({ q: "market" })                 # discover
get_skill({ id: "ua/game-market-intel" })      # inspect versions/deps
download_skill_zip({ id: "ua/game-market-intel", runtime: "claude-code" })
# -> { install_dir: ".claude/skills/", downloads: [ { skill, folder, command, url }, ... ] }
# run each `command` in order (dependencies first) — one curl + unzip each:
#   curl -fsSL "<url>" -o appmagic.zip && unzip -oq appmagic.zip -d .claude/skills/ && rm appmagic.zip
```
The links are one-shot and expire in ~15 minutes, so run them now; if one is
refused with `401`, call `download_skill_zip` again. Nothing else is needed to
count the install — fetching the file is the install.

Only when you need the file contents *in the conversation* (reviewing a skill
before trusting it, patching a file on the way in):
```
install_skill({ id: "ua/game-market-intel", runtime: "claude-code" })
# -> write every file in the result to result.place[runtime] + node path
```

**After you use one — one line, once per task**
```
record_skill_usage({ id: "ua/game-market-intel" })        # ran it
record_skill_usage({ id: "ua/game-market-intel", count: 3 })
```

**Publish a folder you have on disk, from a shell — DO THIS ONE**
```bash
HUB=https://skillhub.pixon.cc          # your connector URL minus /mcp

# Put the token in a curl config file rather than on the command line: it stays
# out of shell history and out of `ps`. (The hub's own static gate blocks a
# skill that puts $…TOKEN on a curl line, and it is right to.)
printf 'header = "Authorization: Bearer ash_YOUR_TOKEN"
' > auth.conf && chmod 600 auth.conf

# a) as a .zip — one command, and the shape download_skill_zip gives back.
#    Write the archive beside the folder, not in /tmp: on Windows the shell and
#    python disagree about where /tmp is, and the upload then reads nothing.
zip -qr my-skill.zip my-skill
#    No `zip` binary (common on Windows)? The stdlib has one:
#    python -c "import shutil;shutil.make_archive('my-skill','zip','.','my-skill')"
curl -s -K auth.conf -X POST "$HUB/api/skills/folder/zip" \
  -F "file=@my-skill.zip" -F "changelog=what changed"

# b) as JSON, when you want to set the fields explicitly
python - <<'PY' > body.json
import io, json, os
files = {}
for root, dirs, fs in os.walk('my-skill'):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', '__pycache__')]
    for f in fs:
        full = os.path.join(root, f)
        rel = os.path.relpath(full, 'my-skill').replace(os.sep, '/')
        files[rel] = io.open(full, encoding='utf-8').read()
print(json.dumps({"namespace": "you", "name": "my-skill",
                  "version": "1.1.0", "changelog": "what changed", "files": files}))
PY
curl -s -K auth.conf -X POST "$HUB/api/skills/folder" \
  -H "Content-Type: application/json" --data-binary @body.json
```
Same response as `upload_skill_folder` — read `removed`, `skipped` and
`warnings` before reporting success. Then confirm what actually landed:
`curl -fsSL -K auth.conf "$HUB/api/skills/you/my-skill/zip" -o check.zip`
and diff it against the folder. Paths present only locally (`.git/`,
`node_modules/`) are the hub correctly dropping junk, not a short upload —
they are the same paths it listed back in `skipped`.

**Publish a folder when you have NO shell** — a hosted connector with no
terminal, or files that exist only in this conversation and never touched disk.
Not for a folder you could have zipped: every byte below is retyped by you.
```
# ls the folder first — the count is what catches a truncated upload
upload_skill_folder({
  file_count: 2,                                  # from the listing, not from `files`
  files: { "SKILL.md": "---\nname: my-skill\ndescription: what it does…\n---\n…",
           "references/guide.md": "…" }
})
# -> { published: true, skill: "you/my-skill", version: "1.0.0", created: true,
#      visibility: "private", files: 2, added: [...], skipped?: [...], warnings?: [...] }
```
No manifest, no `contents`, no `removes`: the name, description and version come
from SKILL.md's frontmatter, and files the previous version had that this folder
does not are deleted and listed back in `removed`. Read `removed` and `skipped`
before reporting success — they are the hub telling you what your folder said.

**Publish when the manifest carries more than SKILL.md can** (pinned
dependencies, `kind: orchestration`, a workspace):
```
upload_skill({
  manifest: { id: "eng/my-skill", version: "1.0.0", kind: "leaf",
              visibility: "private", description: "...", runtimes: ["claude-code"],
              contents: ["SKILL.md", "references/guide.md"] },   # from `ls`, not from `files`
  files: { "SKILL.md": "...", "references/guide.md": "..." }
})
# -> { skill, version, files: 2, derived: { tier: "prompt-only" },
#      ignored_fields: [...], warnings: [...] }
```
The response tells you what the hub decided for you: `ignored_fields` (manifest
keys it has no use for — e.g. `tier`, which it always derives from the payload
instead), `derived`, and `warnings` (files your SKILL.md points at but did not
ship). Read them; do not assume a 200 means everything you sent took effect.

**Publish a LARGE skill (several calls)** — still the no-shell path, for
anything over ~100KB of content or more files than you can reliably emit in one
message. With a shell this is never the answer, however large the skill: the zip
POST costs the same for 2 files as for 200.
```
# 1. list the folder first, then declare it — this is the packing list
create_draft({ manifest: { id: "ua/big-skill", version: "1.0.0",
                           contents: [ ...every path from the folder listing... ] } })
# -> { draft_id, progress: { declared: 19, received: 0 } }

# 2. send in batches; retries are safe (re-sending a path overwrites it)
add_draft_files({ draft_id, files: { "SKILL.md": "...", "scripts/a.py": "..." } })
# -> { progress: { received: 7, missing: [...], complete: false }, next: "..." }
#    repeat until complete: true

# 3. one publish, one version
publish_draft({ draft_id })
```
`publish_draft` refuses while anything is missing and publishes **nothing** —
so an incomplete attempt costs you nothing but the retry. Use `list_drafts()`
to find work you left half-sent, `discard_draft({ draft_id })` to abandon it.

**Let one more department use it — `share_skill_with_department`**
Reach for this before raising visibility. Sharing adds named departments as
readers; it does **not** make the skill org-wide and does **not** move it out of
its own department.
```
share_skill_with_department({ id: "eng/market-report", department_name: "Marketing" })
# -> { shared: true,  department: "Marketing", shared_with: ["Marketing"] }
# -> { shared: false, status: "human_review", request_id: "...", next: "..." }
unshare_skill_from_department({ id: "eng/market-report", department_name: "Marketing" })
list_skill_shares({ id: "eng/market-report" })
```
**Read `shared` before you report success.** `false` means a reviewer has to
approve it first — sharing runs the same gate as raising visibility to
`department`, so a scripted skill (or a sharer without `skill:publish:dept`)
queues. Telling Marketing to go look at a skill they cannot see yet is the
mistake this field exists to prevent.

Un-sharing needs no review: it can only reduce who can read the skill.

**Share it — raise its visibility**
```
set_skill_visibility({ id: "eng/my-skill", visibility: "org" })
# -> {"changed":true, "visibility":"org", "status":"published"}      you had skill:publish:org
# -> {"changed":false,"status":"human_review","request_id":"…"}      queued: a maintainer must
#    approve_promotion({ id: request_id }). The skill is NOT public yet — say that plainly.
```
**Which department is it shared WITH?**
```
set_skill_department({ id: "eng/my-skill", department_name: "AI Lab" })
```
A skill's department comes from whoever uploaded it and never moves on its own —
not on ownership transfer, not when a person changes department. While the skill
is `department`-visible that field IS its audience, so changing it needs
`skill:publish:dept`. A skill belongs to exactly one department; use
`visibility: "org"` when everyone should see it.

Lowering (`org` → `private`) applies immediately. `upload_skill` cannot do this:
it sets `visibility` only when creating a skill, so bumping the version of an
existing skill leaves its scope untouched.

**Document / market a skill you own**
Every skill has a detail page in the dashboard — its "marketing" page. Beyond the
manifest metadata it shows three owner-maintained, mutable Markdown sections:
**Usage**, **Best practices**, and **Sample output**. Edit them any time (owner
or admin) — no new version needed:
```
update_skill_docs({ id: "eng/my-skill",
  usage_md: "## Invoke\n`do_thing({ ... })`\n\nBasic example…",
  best_practices_md: "- Do X\n- Avoid Y",
  sample_output_md: "![screenshot](https://…/demo.png)\n\nhttps://youtu.be/ID" })
```
- Bodies are full Markdown; the page renders images, tables, code, **video files**
  (`![](clip.mp4)`) and **YouTube/Vimeo embeds** (a bare link on its own line).
- Omit a field to leave it unchanged; pass `""` to clear that section.
- `get_skill(...)` returns the current `docs` (plus `updated_at` / `updated_by_email`).

**Fork a skill to start from someone else's work**
```
fork_skill({ id: "ua/game-market-intel" })
# -> a new PRIVATE skill <your-namespace>/game-market-intel, seeded from the
#    source's latest version. Same name, your namespace — pass namespace/name only
#    to override. It records the source as its origin AND as its merge base.
```

**Read a skill's real source before installing or forking it**
```
list_skill_files({ id: "ua/game-market-intel" })         # paths + sizes + digests
read_skill_file({ id: "ua/game-market-intel", path: "scripts/run.py" })
# both take an optional `version:`; default is latest
```
The dashboard's **Files** tab shows the same thing for a human. Don't claim to
have read a source you haven't.

**Sync a local folder to the hub** — never guess what is up there:
```
list_skill_files({ id: "eng/my-skill" })     # what the hub holds, with digests
# compare against your local files (sha256 of each file's bytes, "sha256:<hex>")
# then upload the FULL set as a new version — contents from your local listing.
```
This is the only honest way to answer "is the hub in sync?". Comparing against
your memory of what you sent is not a check — that memory is exactly what is
wrong when an upload came up short.

**Fix specific files (owner / maintainer / admin) — `update_skill_file`**
Use this, not `upload_skill`, whenever you are changing part of a skill that is
already published. Name only the files you touched; the hub carries the rest of
the version forward, along with the manifest's deps, runtimes and provides.
```
list_skill_files({ id: "eng/my-skill" })                 # what is actually published
read_skill_file({ id: "eng/my-skill", path: "references/guide.md" })
update_skill_file({
  id: "eng/my-skill",
  base_version: "1.4.0",                                 # the version you just read from
  files: { "references/guide.md": "...ENTIRE new text..." },
  delete: ["references/old.md"],                         # optional
  changelog: "rewrite the guide"
})
# -> { version: "1.4.1", files: 7, updated: [...], removed: [...] }
```
Content is the file's **entire new text** — the hub takes no patches or diffs.
The version bumps the patch number unless you pass `version`.

Always pass `base_version`, and get it from `list_skill_files`/`read_skill_file`
rather than memory. It is what makes the call fail instead of silently reverting
a release someone published while you were working; on that failure, re-read the
files at the version named in the error and reapply your change. Check `added`
in the response too: a path you meant to replace showing up there means you
typo'd it and just published a second copy under a near-miss name.

Versions stay immutable — this publishes a new one, it does not patch the old
one. Reach for `upload_skill_folder` (or `upload_skill`) when publishing a skill's
full contents from disk, or a draft when that will not fit in one call.

On the dashboard's Files tab the owner does the same thing by hand: add, edit
and delete files, then commit. Committing publishes a new version, by the same
rules.

**Improve someone's skill (fork → PR)** — three calls, in this order:
```
fork_skill({ id: "eng/base" })                       # -> you/base, private
upload_skill_folder({ file_count: 7, files: { ...the whole folder... } })   # a version of YOUR fork
open_pull_request({ head: "you/base@1.1.0", title: "what this changes" })
```
`head` is always `namespace/name@version`, and that version must already be
published in your fork. `base` defaults to the skill you forked from. Pushing
more work means publishing another version and calling
`update_pull_request({ id, head_version })` — the PR and its discussion survive.

**Your PR conflicts — fix it on your own fork** (the normal path):
```
sync_fork({ id: "you/base" })
# clean -> published. Conflicts -> the response carries the 3-way merge: for each
# file with conflict=true read base/ours/theirs and write ONE clean merged version
# (no <<<<<<< markers), keep `merged` for the rest, then:
sync_fork({ id: "you/base", resolved_files: { "SKILL.md": "…", ...every kept file… } })
update_pull_request({ id: "<pr>", head_version: "<the version sync_fork published>" })
```

**Resolve conflicts as the REVIEWER (you own the skill)** — only when the
proposer cannot:
```
get_pull_request_merge({ id: "<pr>" })
merge_pull_request({ id: "<pr>", version: "<greater-than-latest>",
  resolved_files: { "SKILL.md": "<clean merged>", ...every kept file... } })
```
A clean PR needs no `resolved_files` — just `merge_pull_request({ id })`. The
version it publishes credits the proposer.

See `references/workflows.md` for the exact placement rules, manifest schema,
and the full conflict-resolution procedure. See `references/tools.md` for every
tool's arguments and return shape.

## Gotchas
- Tools fail with a permission error if you lack the right permission — that is
  expected; report it, don't retry blindly. Admin-only actions need admin.
- `install_skill` marks dependency skills `hidden` so they don't clutter the
  user's skill list — still write them; they're needed at runtime.
- When authoring an orchestration, its SKILL.md must include a setup step that
  pulls/verifies its child skills before running (the hub resolves them, but the
  parent should re-check so the client never errors on a missing dependency).
- A skill that another skill depends on cannot be deleted — yank the version
  instead.
- **CRLF on disk lands as LF on the hub.** That is normalisation, not a short
  upload. Diff a round-tripped zip with `diff -r --strip-trailing-cr` before
  concluding that anything was lost.
- **Verify a publish before you report it done.** `list_skill_files` on the
  version you just created and check the count against the folder you sent. An
  upload that reports success published exactly what reached the server, which is not
  always what you meant to send.
- **Clean up your own wreckage.** `delete_version({ id, version })` erases a bad
  version outright while the skill is still private and uninstalled; once anyone
  can see it, `yank_version` is the honest tool instead. Don't leave failed
  attempts in a skill's history.
- After changing a skill's files, its **docs may no longer describe it**. The
  detail page flags docs written against an older version; refresh them with
  `update_skill_docs` when the package moves under them.
- Editing files on the dashboard only ever applies to the **latest** version, and
  a commit is refused if someone published while the user was editing (they must
  reload and reapply). Adding a `scripts/` file re-derives the tier to `scripted`,
  which changes what it takes to share the skill.
- `fork_skill` needs read access to the source: a private skill you cannot see is
  not forkable, over MCP or the dashboard.
- **Your namespace is yours alone.** Everyone has a personal namespace (derived
  from their email) that nobody else may publish into, and forks land there by
  default. Uploading into someone else's is refused.
- One open pull request per fork per upstream. A second proposal from the same
  fork is `update_pull_request`, not a new PR.
- A fork with an open pull request cannot be deleted — close the PR first.
- After a merge the hub advances your fork's merge base to the version it just
  published, so your next PR proposes only what is new. Never re-send merged work.
