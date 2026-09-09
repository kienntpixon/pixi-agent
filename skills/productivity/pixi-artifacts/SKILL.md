---
name: pixi-artifacts
description: "Publish an HTML page to Pixi and share it with colleagues."
version: 1.0.0
author: kiennt (@kienntpixon)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Pixi, Artifacts, Publishing, Sharing, HTML, Report]
    category: productivity
    homepage: https://pixi.pixon.cc
---

# Pixi Artifacts Skill

Turn work you just finished into a page a colleague can open — a report, a
dashboard, a comparison table, a one-pager — hosted on Pixi at a link that keeps
meaning the same thing. Pixi stores the HTML, decides who may read it, and
serves it inside a sandbox.

This skill does not design documents and does not replace writing a file
locally. Use it when the result needs to reach somebody else.

## When to Use

Reach for it when the answer is a **page**, not a paragraph, and somebody other
than the person in front of you will read it:

- A summary with tables, charts or images that would be unreadable in chat.
- Something the same person will come back to next week and expect to find.
- Anything a whole department or job position should see rather than one inbox.

Do not use it for a one-line answer, for scratch work, or for content only this
session needs. An artifact nobody opens is a link somebody has to decide what to
do with later.

## Prerequisites

The artifact tools arrive over the **Pixi MCP connector**, which Pixi attaches
to every signed-in machine by itself — there is nothing to install. Check with
`list_artifacts`; if that tool is missing, the person is not signed in to Pixi
on this machine, and saying so is the whole answer. There is no local-file
fallback, because a page has to live on the server for sharing and revocation
to mean anything.

Tools this skill uses: `create_artifact`, `update_artifact`, `read_artifact`,
`list_artifacts`, `get_artifact`, `list_artifact_targets`,
`grant_artifact_access`, `revoke_artifact_access`, `set_artifact_visibility`.

## How to Run

Write the complete HTML, then publish it in one call:

```
create_artifact(
  title="Q3 puzzle market — top movers",
  description="Downloads and revenue for the eight titles that moved most",
  content="<!doctype html>…"
)
```

It returns the artifact's `id`. The page starts **private**: nobody else can
open it until it is shared. Then share it with whoever asked:

```
grant_artifact_access(id=<id>, subject_kind="user", subject_id=<uuid>)
```

Report the link back as `https://pixi.pixon.cc/artifacts/<id>` so the person can
open it.

## Quick Reference

| Goal | Call |
|---|---|
| New page | `create_artifact(title, description, content)` |
| Replace the page's HTML | `update_artifact(id, content=…)` |
| Rename it | `update_artifact(id, title=…, description=…)` |
| Read what is on it now | `read_artifact(id)` |
| Share with a person | `grant_artifact_access(id, "user", <user uuid>)` |
| Share with a department | `grant_artifact_access(id, "department", <dept uuid>)` |
| Share with a job position | `grant_artifact_access(id, "position", <position uuid>)` |
| Let them edit too | add `can_edit=true` |
| Open to the whole company | `set_artifact_visibility(id, "org")` |
| Stop sharing | `revoke_artifact_access(id, kind, subject_id)` |
| Find pages | `list_artifacts()` |

Subject UUIDs come from `list_artifact_targets`, which returns people,
departments and positions as id + label. Never invent one — a wrong UUID
silently shares with nobody, and the person who asked believes it arrived.

That tool is the only directory this skill gets, on purpose: turning "send it to
Minh" into a UUID does not need the ability to read personnel records, so the
agent's credential does not carry it.

## Procedure

**1. Decide it is a page.** See *When to Use*. If it is not, answer normally.

**2. Write ONE self-contained HTML file.** This is the constraint everything
else follows from — the page runs sandboxed with `connect-src 'none'`, so
anything it tries to fetch from another host simply does not load, and it does
not load for the *reader* rather than for you:

- Images, fonts and data: embed as `data:` URIs. No remote `<img src="https://…">`.
- Scripts: only `https://cdnjs.cloudflare.com` and `https://cdn.jsdelivr.net`,
  pinned to an exact version. Everything else is blocked.
- Styles: inline, or Google Fonts stylesheets.
- No `fetch`, no forms that post anywhere, no analytics beacons — all blocked.
- Give it a `<title>`, make it readable on a phone, and set explicit background
  and text colours rather than relying on the reader's theme.
- 16 MiB is the ceiling, `data:` URIs included.

**3. Publish, then share.** Create it, then grant access. Two steps on purpose:
a page exists privately for a moment before anybody else can see it, which is
the moment to notice it is wrong.

**4. Hand back the link and say who can open it.** "Shared with the Marketing
department" is the part people need; a bare URL invites them to forward it to
somebody who will get a 404.

**5. Updating.** `update_artifact(id, content=…)` publishes a new version and
keeps the old ones. Re-publishing byte-identical content creates no new version,
so a nightly job that regenerates the same page does not fill the history.

## Pitfalls

- **Remote images.** The single most common way an artifact looks broken to its
  reader and fine to whoever made it. Embed, or leave it out.
- **Sharing with a department shares with everything under it.** Granting
  "Engineering" reaches every team beneath it. Say which department out loud
  before doing it.
- **`org` is not `public`.** `set_artifact_visibility(id, "org")` means every
  signed-in employee. Putting a page on the open internet is deliberately not
  available to an agent at all — it needs a person on the Pixi console who holds
  the `artifacts:publish` permission. If someone asks for a public link, say
  that, and do not look for a way around it.
- **Editing is not sharing.** `can_edit=true` lets them change the page; it does
  not let them pass it on. Only the owner shares.
- **Quota.** Each person may hold a couple of hundred live artifacts. Delete the
  drafts rather than accumulating "report-final-2".

## Verification

After publishing, confirm the page is really there and really reachable:

1. `get_artifact(id)` — check `version` is not 0. A 0 means the metadata was
   created and the HTML never landed.
2. `read_artifact(id)` — check the HTML that came back is the HTML you sent,
   not a truncated copy.
3. Check the returned permissions say what you intended: `visibility`, and the
   grants you added.

If the reader reports a blank page, the cause is almost always step 2 of the
*Procedure*: something in the HTML is fetched from a host the sandbox blocks.
Read it back and look for an absolute `https://` URL that is not one of the two
allowed script CDNs.
