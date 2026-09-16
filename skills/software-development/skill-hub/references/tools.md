# Hub MCP tool reference

Every tool runs as the connected identity and enforces the same permissions as
the dashboard. Arguments are a JSON object; results are JSON text.

## Discover
- `search_skills({ q?: string })` → skills visible to you (optionally filtered).
- `get_skill({ id: "ns/name" })` → `{ skill, versions, docs }` (metadata, version
  list, and the owner-maintained docs — see below).

## Install

Two doors. `download_skill_zip` moves the files over HTTP and costs the same for
a 2-file skill as for a 40-file one; `install_skill` moves them through this
conversation, which is only worth paying for when you need to READ them.

- `download_skill_zip({ id: "ns/name", version?: string, runtime?: "claude-code"|"cursor" })`
  → `{ root, runtime, install_dir, downloads[], lock[], expires_in_seconds, next }`.
  **The default way to install.** No file content comes back — only links.
  - `downloads[]`: one entry per skill in the closure, **dependencies first**,
    each `{ skill, version, folder, dependency, files, bytes, url, command }`.
  - `command` is ready to run as-is: it curls the `.zip`, unpacks it into
    `install_dir`, and deletes the archive. Run them in the order given.
  - Each `url` carries a **one-shot ticket** that expires in ~15 minutes and
    needs no token — the shell you run `curl` in does not hold your hub
    credential, and this is why it does not need one. A spent or stale link
    answers `401`; call the tool again for fresh ones.
  - The archive unpacks to `<folder>/SKILL.md …`, which is the layout the runtime
    expects — nothing to rename or move afterwards.
  - Fetching the file is what counts the install, so there is nothing else to
    call. (`record_skill_usage` is still yours to send after you RUN it.)
  - Windows PowerShell, if `curl`/`unzip` are missing:
    `Invoke-WebRequest <url> -OutFile x.zip; Expand-Archive x.zip -DestinationPath <install_dir> -Force`
- `install_skill({ id: "ns/name", version?: string, runtime?: "claude-code"|"cursor" })`
  → `{ root, nodes[], lock[], place }`. Use when you need the contents in the
  conversation — to read a skill before trusting it, or to patch a file on the
  way in. Otherwise it is the expensive way to write files.
  - `nodes[]`: each `{ full_name, version, digest, kind, hidden, files{path:content} }`
    — the parent plus every dependency (deps have `hidden:true`).
  - `place`: `{ "claude-code": ".claude/skills/", "cursor": ".cursor/skills/" }`.
  - Write each node's files under `place[runtime] + <install-name>/<path>`.
  - To read one file rather than all of them, `list_skill_files` +
    `read_skill_file` are cheaper still.

## Report use
- `record_skill_usage({ id: "ns/name", count?: number })` →
  `{ recorded, skill, total_uses, users }`.
  - Call it once after a task where you actually ran a hub skill; `count` batches
    several runs into one call.
  - Counted per person per UTC day, so repeat pings the same day just add up and
    the caller is still one "user". No content leaves your machine.
  - This is the only usage signal the hub has — installs alone cannot tell a
    skill people rely on from one that was downloaded and forgotten.

## Publish

Two doors, same as install. **With a shell on the machine holding the folder,
publishing is not a tool call at all** — POST the folder and no file content
passes through the conversation:

- `POST {hub}/api/skills/folder/zip` — multipart, `file=@my-skill.zip`.
- `POST {hub}/api/skills/folder` — JSON `{namespace, name, version, changelog,
  files}`.

Both take the same `ash_` bearer token as `/mcp`, run the same service as
`upload_skill_folder`, and answer with the same body. Neither takes
`file_count`: that guard exists for a payload typed out from memory, and a glob
has already stated what whole means. `{hub}` is your connector URL minus `/mcp`.
Round-trip with `GET {hub}/api/skills/{ns}/{name}/zip` to diff what landed.

The tools below are for when there is no shell — a hosted connector, or files
you generated in this conversation and never wrote to disk.

- `upload_skill_folder({ files, file_count, namespace?, name?, version?, changelog? })` →
  `{ published, skill, version, created, visibility, description, files,
     added?, updated?, removed?, removed_note?, skipped?, skipped_note?, warnings? }`.
  **Publishes a folder without a manifest** — `SKILL.md`'s frontmatter is the
  manifest. The right tool when you cannot reach the REST route above.
  - `files` is the folder, keyed by path **relative to the directory holding
    SKILL.md** (a `my-skill/` prefix is trimmed for you if you leave it on).
  - `file_count` is how many files the folder holds **on disk** — count the
    listing, never `Object.keys(files).length`. It is the whole truncation guard
    that `contents` used to be, at the cost of one integer: a payload short of
    its own count is refused with `PACKAGE_INCOMPLETE`, published nothing.
  - The name comes from frontmatter `name` (kebab-case) and the description from
    frontmatter `description`; both are required, and a missing description is a
    refusal, not a warning — a skill nobody can match is a skill nobody finds.
  - The version comes from frontmatter `version` if present, else a patch bump of
    the current latest, else `1.0.0`. Pass `version` to override.
  - `namespace` defaults to your personal namespace. `name` is only for the case
    where the hub's name for the skill differs from the one SKILL.md declares
    (this hub publishes its own `skill-hub` skill as `using-skill-hub`) — leave
    it out and the frontmatter decides.
  - It is a **whole snapshot**: files the previous version had and this folder
    does not are deleted, listed back in `removed`. That is the folder speaking,
    not you — check the list.
  - Junk (`.git/`, `node_modules/`, `.DS_Store`, caches) and binaries are dropped
    and reported in `skipped`. A skill's payload is text.
  - Publishing into a skill you do not own is refused with the route attached:
    `fork_skill` → upload into the fork → `open_pull_request`.
  - It cannot set what SKILL.md does not carry — `dependencies`, `kind`,
    `provides`, `workspace_id`. Use `upload_skill` for those.
- `upload_skill({ manifest, files })` →
  `{ skill, version, files, derived, ignored_fields?, overrides?, warnings? }`.
  Private by default. One call, whole snapshot. See the manifest schema in
  `workflows.md`. `files` must include `SKILL.md`. Reach for it when the manifest
  carries something SKILL.md cannot (an orchestration's pinned dependencies, a
  workspace placement); otherwise `upload_skill_folder` says the same thing with
  three fewer lists to keep in agreement.
  - **`manifest.contents` is required**: every path this version contains, taken
    from the folder on disk. The upload is refused with `PACKAGE_INCOMPLETE` and
    the exact missing paths when the files received do not match it. Generating
    `contents` from the `files` map you are sending defeats the check entirely —
    it can only catch a short payload if it came from the other side.
  - **`manifest.removes`** is required to drop a file the previous version had.
    Otherwise the upload is refused with `FILES_DROPPED` and the paths at risk:
    a version is a replacement, so an omitted file is a deletion.
  - `ignored_fields` lists manifest keys the hub has no use for (e.g. `tier`),
    `overrides` what it changed (e.g. a visibility you cannot grant yourself),
    `derived` what it worked out itself. Nothing is applied in silence — but
    equally, nothing you send is honoured just because the call returned 200.
  - `warnings` carries lint findings, notably `dangling-reference`: a path your
    SKILL.md points at that the package does not contain.
- **Large skills — `create_draft` → `add_draft_files`… → `publish_draft`.**
  A version must be sent whole, and one MCP call caps at 32MB of request body —
  but your own generation budget runs out long before that, around 100KB of file
  content. Above that, assemble the version across calls:
  - `create_draft({ manifest })` → `{ draft_id, progress, max_bytes_per_call }`.
    The manifest needs `contents`; that packing list is what makes "am I done?"
    answerable.
  - `add_draft_files({ draft_id, files })` →
    `{ progress: { declared, received, missing, unexpected, complete }, next }`.
    Call as many times as needed. Re-sending a path overwrites it, so any retry
    is safe. Send until `complete: true`.
  - `publish_draft({ draft_id })` → publishes one immutable version. While
    anything declared is still missing it fails with `PACKAGE_INCOMPLETE` and
    **publishes nothing** — the skill's `latest_version` moves exactly once, on
    success, so a failed attempt leaves no junk version behind.
  - `list_drafts()` / `discard_draft({ draft_id })` — find and abandon
    half-finished work. Drafts are invisible to everyone but you.
- `delete_version({ id, version })` → erase one version outright. Allowed only
  while the skill is `private`, has no installs, no other skill pins that exact
  version, and it is not the skill's only version; the reply carries the new
  `latest_version`. For anything the org can already see, `yank_version` is the
  correct tool — history that others may hold a copy of is not yours to rewrite.
- `delete_skill({ id })` → deletes a skill you own (best for private drafts).
  Refused if another skill depends on it (yank the version instead).
- `set_skill_visibility({ id, visibility })` → change a skill's scope
  (`private` | `workspace` | `department` | `org`). **The only way to change
  visibility over MCP** — `upload_skill` writes `visibility` when it *creates* a
  skill and never again, so a version bump cannot widen an existing one.
  Owner, `skill:maintain` or admin only; anyone else is refused outright.
  - **Lowering** applies immediately — reducing exposure needs no review.
  - **Raising** runs the static gate. With the matching publish permission
    (`skill:publish:org` for org, `skill:publish:dept` otherwise) a prompt-only
    skill that passes is published on the spot. Without it, the call still
    succeeds but files a request: `status: "human_review"` plus a `request_id`,
    and the visibility is unchanged until a reviewer calls `approve_promotion`.
  - **Scripted/privileged skills always queue**, even for an admin.
  - Returns `{ changed, visibility, status, detail, request_id?, report }`.
    `changed: false` with a `request_id` means "asked, not yet granted" — say so
    rather than reporting the skill as published.
  - `workspace` is refused unless the skill already has a `workspace_id`
    (otherwise it would be visible to nobody).
- `transfer_skill_owner({ id, new_owner_id? , new_owner_email? })` → hand
  maintainership to another employee. The `original_author` is preserved for
  attribution and never changes. Only the current owner or an admin can transfer.
  Every skill exposes `owner_email` (current maintainer) and
  `original_author_email` (first uploader).
- `fork_skill({ id, namespace, name })` → GitHub-style fork: create a NEW skill
  you own, seeded from the source's latest version (files + deps copied). The
  fork records the source as its origin (`forked_from_full_name` /
  `forked_from_version`, shown on its page) and starts **private** — diverge
  freely (add/remove features), then share it back through the review gate. Use
  this to start contributing from an existing skill. `namespace/name` must be
  kebab-case and unique. `get_skill` on the source returns a `fork_count`.
  Requires read access to the source — a skill you cannot see is not forkable.

### Reading a skill's files
- `list_skill_files({ id, version? })` →
  `{ skill, version, files: [{ path, size, digest }], count, total_size }`.
  Content-free, so it is cheap enough to call before deciding what to read. The
  digest is `sha256:<hex>` of the file's bytes — compare it against a local file
  to diff a folder against the hub without downloading anything.
- `read_skill_file({ id, path, version? })` →
  `{ skill, version, path, size, content, truncated, binary }`. Both default to
  the latest version. Files over 1MB come back cut with `truncated: true` and the
  true `size`, never silently short. Binary files report `binary: true` with
  empty content.

These are how you verify an upload landed whole, review a skill before installing
it, and answer "is the hub in sync with local?" with something better than your
own memory of what you sent.

The skill's detail page → **Files** tab shows the same tree for a human. The
owner (or a maintainer/admin) can also edit files there and commit — which
**publishes a new version**, since versions are immutable. `update_skill_file`
below is the same operation over MCP.

## Edit specific files
- `update_skill_file({ id, files?, delete?, base_version?, version?, changelog? })`
  → `{ published, skill, version, base_version, files, added?, updated?, removed?, warnings? }`.
  Owner/maintainer/admin only. Publishes a new immutable version made of the base
  version plus your changes — it does not patch a released version.
  - `files` maps path → the file's **entire new text**. Not a patch, not a diff.
    Every path you do not name is carried forward untouched, along with the
    manifest's dependencies, runtimes and provides.
  - `delete` names paths to drop. Deleting a path the base version does not have
    is refused rather than ignored — it means you are working from a stale
    picture of the skill. `SKILL.md` can never be deleted.
  - `base_version` is the version you actually read the files from. Pass it: if
    the skill moved in between, the call is refused with the current version in
    the error, instead of silently reverting whatever was published meanwhile.
    Then re-read at that version, reapply, and retry.
  - `version` defaults to a patch bump of the latest.
  - Check `added` in the response. A file you meant to replace listed there means
    the path was wrong and you have just published a near-miss duplicate.
  - Prefer this over `upload_skill` for any change to a skill that is already
    published; `upload_skill` is for publishing full contents from disk.

## Share with named departments
- `share_skill_with_department({ id, department_name? | department_id? })` →
  `{ shared, skill, department, status, detail, shared_with[], request_id?, next? }`.
  Owner/maintainer/admin only. Lets ONE more department read the skill.
  - A share is **additive**. The skill's `visibility` and its own `department_id`
    do not change, so a private skill shared with Marketing is readable by
    Marketing and nobody else new. This is the tool to reach for when a second
    team needs a skill — raising to `org` hands it to the whole company, and
    `set_skill_department` moves it away from the team already using it.
  - It runs the **same review as raising visibility to `department`**, because it
    is the same increase in exposure. Prompt-only + `skill:publish:dept` shares
    on the spot; anything scripted, or a sharer without that permission, is
    queued for a reviewer.
  - **Branch on `shared`, never on the absence of an error.** `false` means
    queued: `request_id` names the request a reviewer must approve, and the
    department cannot see the skill until they do.
  - Refused with a reason on an `org`-visible skill: everyone can read it
    already, and a share recorded there would quietly outlive a later drop back
    to private.
- `unshare_skill_from_department({ id, department_name? | department_id? })` →
  `{ unshared, skill, department, shared_with[] }`. No review — it can only
  reduce who can read the skill. Does not touch visibility.
- `list_skill_shares({ id })` → `{ skill, visibility, own_department, shared_with[], count }`.
  Anyone who can read the skill can see who else relies on it.

## Department
- `set_skill_department({ id, department_id? | department_name? })` →
  `{ moved, skill, department_id, department_name, visibility }`.
  - A skill's department is stamped from **whoever uploaded it** and never moves
    on its own: transferring ownership does not move it, and neither does moving
    a person to another department. This tool is the only way to change it.
  - When the skill is `department`-visible its department **is** its audience —
    the move grants the new department access and takes it from the old one, so
    it needs `skill:publish:dept` (or maintain/admin) on top of owning the skill.
    On any other skill it is bookkeeping the owner can do.
  - Omit both fields to clear it (refused while the skill is department-visible,
    which would leave it readable by nobody but the owner).

## Document — the skill's detail page
Every skill has an owner-maintained docs block (Markdown) shown on its detail
page in the dashboard, separate from immutable versions. Update it any time — no
new version needed.
- `update_skill_docs({ id, usage_md?, best_practices_md?, sample_output_md? })`
  → `{ updated, docs }`. Only the current owner or an admin may edit.
  - `usage_md` — how to invoke the skill, arguments, a basic example.
  - `best_practices_md` — do's & don'ts, gotchas, when to reach for it.
  - `sample_output_md` — a representative result (use a fenced ``` block).
  - Omit a field to leave it unchanged; pass an empty string to clear that
    section. `get_skill(...).docs` also returns `updated_at` and
    `updated_by_email`.

## Fork — your own copy
- `fork_skill({ id, namespace?, name? })` → a new PRIVATE skill you own, seeded
  from the source's latest version. Defaults to `<your-namespace>/<same-name>`;
  namespace/name only override that. Records `forked_from_*` (provenance) and
  `merge_base_version` (the version a PR from it will diff against).
- `sync_fork({ id, version?, resolved_files? })` → 3-way merges the upstream's
  latest INTO your fork (base = merge base, ours = your fork, theirs = upstream)
  and publishes the result as a new version of the fork, advancing the merge
  base. Clean applies by itself; conflicts return
  `{ synced: false, conflicts, merge }` and publish nothing until you pass
  `resolved_files` (a full `path→content` map). `{ up_to_date: true }` when
  there is nothing to pull.

## Pull requests — proposing into someone else's skill
A PR points at a version of your fork. It carries no files.
- `open_pull_request({ head, base?, title?, body? })` — `head` is
  `"namespace/name@version"` and must already be published in your fork; `base`
  defaults to the skill you forked from. → `{ pull_request, static_passed,
  mergeable, conflicts, advice }`.
- `update_pull_request({ id, head_version })` → re-points at a newer version of
  the same fork ("push another commit"); keeps the discussion, re-runs the gate,
  re-prices the merge.
- `list_pull_requests({ role?, status?, skill? })` — `role="reviewer"` (default)
  is the queue waiting on you, `role="author"` the ones you opened. Rows carry
  cached `mergeable` (1 clean / 0 conflicts / -1 unknown) and `conflicts`.
- `get_pull_request({ id })` → the PR plus its `events` timeline.
- `get_pull_request_merge({ id })` → the **3-way merge**:
  `{ pull_request, merge: { base_skill, head_skill, merge_base, current_version,
     head_version, behind, next_version_hint, result: { files[], conflicts, clean } } }`.
  Each file: `{ path, status, conflict, base, ours, theirs, merged, present }`.
- `merge_pull_request({ id, version?, resolved_files? })` → publishes a merged
  version of the upstream, credited to the proposer. Clean → auto-applies.
  Conflicts → you MUST pass `resolved_files` (a full `path→content` map), though
  the better move is asking the proposer to `sync_fork` first. Version must be
  greater than current latest (omit to auto-pick).
- `close_pull_request({ id, reason? })` — the proposer or the skill's
  owner/maintainer.
- `comment_on_pull_request({ id, body })` / `request_changes({ id, body })` —
  the discussion; `request_changes` also moves the PR's status and needs
  maintain authority.

`propose_skill_improvement` was **removed**: it posted a file map into someone
else's skill, which is the thing this model exists to prevent. The old
`list_contributions` / `get_contribution_merge` / `merge_contribution` /
`reject_contribution` names still resolve as aliases for one release.

## Org administration & governance
Departments, employees, roles, `yank_skill`, promotion review, and department
policy are **permission-gated admin tools** documented in the separate
**`skill-hub-admin`** skill. Use that skill for any org-management or governance
request.

## Return-shape tips
- List tools return a JSON array; parse it, don't assume single objects.
- MCP tokens are never returned in employee objects (there is no password —
  employees sign in via SSO).
- On any permission failure the tool returns an error like
  `permission org:roles:manage required` — surface it; don't retry.
