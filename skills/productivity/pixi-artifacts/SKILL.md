---
name: pixi-artifacts
description: "Publish an HTML page to Pixi and share it with colleagues."
version: 1.1.0
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

Tools this skill uses: `create_artifact`, `get_artifact_upload_url`,
`update_artifact`, `read_artifact`, `list_artifacts`, `get_artifact`,
`list_artifact_targets`, `grant_artifact_access`, `revoke_artifact_access`,
`set_artifact_visibility`.

## How to Run

**Write the page to disk, then upload the file. Do not retype it into a tool
argument.**

`create_artifact(content=…)` carries the whole document through your own
output — every byte of it, base64 images included. A report with four charts
costs megabytes of conversation to say something already sitting in a file, and
the 16 MiB ceiling arrives long before your output limit is comfortable.

So write the folder, zip it, and hand it to curl:

```bash
mkdir -p report/img
# ...write report/index.html and report/img/*.png the way you would any file...
zip -qr report.zip report
#   No `zip` binary (common on Windows)? The stdlib has one:
#   python -c "import shutil;shutil.make_archive('report','zip','.','report')"
```

```
create_artifact(title="Q3 puzzle market — top movers",
                description="Downloads and revenue for the eight titles that moved most")
get_artifact_upload_url(id=<id>)     # -> { upload_url, expires_in, max_bytes }
```

```bash
curl -sS -X PUT "<upload_url>" \
  -H 'Content-Type: application/zip' --data-binary @report.zip
# -> {"version":1,"created":true}
```

The zip must hold **`index.html` at its top level**, plus whatever that page
references. A single wrapping folder is fine and is stripped — `zip -r
report.zip report/` works. Inside the page, reference assets the ordinary
relative way: `<img src="img/chart.png">`, `<link rel=stylesheet
href="style.css">`. Pixi serves them from the same directory as the page, so
what renders locally renders there.

One HTML file and nothing else? Skip the zip:

```bash
curl -sS -X PUT "<upload_url>" -H 'Content-Type: text/html' --data-binary @page.html
```

**No shell available?** Then `create_artifact(title, description,
content="<!doctype html>…")` still works, with everything embedded as `data:`
URIs. It is the fallback, not the default — reach for it only when you genuinely
cannot run a command.

The page starts **private**: nobody else can open it until it is shared. Then
share it with whoever asked:

```
grant_artifact_access(id=<id>, subject_kind="user", subject_id=<uuid>)
```

Report the link back as `https://pixi.pixon.cc/artifacts/<id>` so the person can
open it.

## Quick Reference

| Goal | Call |
|---|---|
| New page | `create_artifact(title, description)` then upload |
| Get somewhere to upload to | `get_artifact_upload_url(id)` |
| Send the file (page + assets) | `curl -X PUT "<upload_url>" -H 'Content-Type: application/zip' --data-binary @report.zip` |
| Send one HTML file | `curl -X PUT "<upload_url>" -H 'Content-Type: text/html' --data-binary @page.html` |
| Replace the page's HTML (no shell) | `update_artifact(id, content=…)` |
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

**2. Write the page, and keep its files beside it.** The page runs sandboxed
with `connect-src 'none'`, so anything it fetches from another host simply does
not load — and it fails for the *reader*, not for you, which is why this is the
constraint everything else follows from:

- **Its own files: ordinary relative paths.** `img/chart.png`, `style.css`,
  `fonts/inter.woff2`. Ship them in the zip and they load. This is the normal
  way to build a page; `data:` URIs are only needed when you cannot use a shell.
- **Another host: no.** A remote `<img src="https://example.com/logo.png">` is
  blocked. Download it into the folder instead.
- Scripts: your own `.js` files, or `https://cdnjs.cloudflare.com` and
  `https://cdn.jsdelivr.net` pinned to an exact version. Nothing else.
- Styles: your own `.css`, inline, or Google Fonts stylesheets.
- No `fetch`, no forms that post anywhere, no analytics beacons — all blocked.
- Give it a `<title>`, make it readable on a phone, and set explicit background
  and text colours rather than relying on the reader's theme.
- 16 MiB total, up to 200 files. Extensions Pixi will not serve (`.exe`, and
  anything else not on its list) are refused at upload with a message saying so.

**3. Publish, then share.** Create it, then grant access. Two steps on purpose:
a page exists privately for a moment before anybody else can see it, which is
the moment to notice it is wrong.

**4. Hand back the link and say who can open it.** "Shared with the Marketing
department" is the part people need; a bare URL invites them to forward it to
somebody who will get a 404.

**5. Updating.** Ask for a fresh `get_artifact_upload_url(id)` and PUT again —
that publishes a new version and keeps the old ones. Re-publishing an identical
file set creates no new version, so a nightly job that regenerates the same page
does not fill the history. An upload URL is good for fifteen minutes and for
that one artifact; get a new one rather than storing it.

## Pitfalls

- **Remote images.** The single most common way an artifact looks broken to its
  reader and fine to whoever made it. Put the file in the zip, or leave it out.
- **Pushing the file through the conversation.** `create_artifact(content=…)`
  works and is sometimes the only option, but every byte is emitted by you. If
  you can run a command, upload instead.
- **A zip of the wrong shape.** `index.html` must be at the top (one wrapping
  folder is stripped for you). No `..` in any path, no absolute paths, no
  symlinks — all refused, because on this server such a path would write over
  another artifact rather than merely misbehave.
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
   not a truncated copy. (For a bundle this returns `index.html`; the assets are
   verified by the upload having succeeded, since a zip that lost a file would
   have changed the version's hash.)
3. Check the returned permissions say what you intended: `visibility`, and the
   grants you added.

If the reader reports a blank page, the cause is almost always step 2 of the
*Procedure*: something in the HTML is fetched from a host the sandbox blocks.
Read it back and look for an absolute `https://` URL that is not one of the two
allowed script CDNs.

If images are missing but the text is there, the file is probably not in the
zip — `unzip -l report.zip` and compare against what the page references.
