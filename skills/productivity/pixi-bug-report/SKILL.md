---
name: pixi-bug-report
description: "Report a Pixi bug to the Pixi Bugbase sheet, with screenshots and logs, and check a reported bug's status."
version: 1.0.1
author: kiennt (@kienntpixon)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Pixi, Bug, Bug report, QA, Tester, Google Sheets]
    category: productivity
    homepage: https://pixi.pixon.cc
    related_skills: [google-workspace, pixi-artifacts]
---

# Pixi Bug Report Skill

Testers and employees report problems with **Pixi itself** by chatting. Examples:
"báo bug pixi này: …", "Pixi bị lỗi …", "log bug giúp mình", "report a Pixi bug". They
usually attach screenshots and sometimes paste a log. This skill turns that message into one
row of the **Pixi Bugbase** sheet, uploads the attachments next to it, and hands back a bug ID.
The dev team works bugs from that sheet and writes progress back into the same row.

- Sheet: https://docs.google.com/spreadsheets/d/1MYs_ROps75bdzoVy0wqTj9XVQBMxpF44shfFSmgf4Ho
- Attachments folder: https://drive.google.com/drive/folders/16eJZpykYk7hFRwuc2uQO2UYIcLwDoLn0

## When to Use

- The user reports something broken, wrong or confusing **in Pixi**. That covers the desktop app,
  its installer and updates, the Pixi agent, the pet widget, and the Pixi Admin console.
- The user asks about a bug they reported. Examples: "bug BUG-0012 sao rồi", "mấy bug mình báo
  đã fix chưa".

Do **not** use it for:

- Bugs in other products or in the user's own work. Help them directly instead.
- Ideas, wishes or complaints that aren't defects. Those belong on Pixi's feedback board
  (the `submit_feedback` tool on the Pixi connector).
- Something you only suspect from casual chatter. Ask "Bạn muốn mình báo bug này lên Pixi
  Bugbase không?" before submitting.

## Prerequisites

The script runs as the **employee's own Google account**. Two things are required:

1. **Google is connected in Pixi.** The user clicked **"Kết nối Google Workspace"**, which
   created `google_token.json` in HERMES_HOME. This is the same token the google-workspace skill uses.
2. **That account can edit the Bugbase sheet and the attachments folder.** Only the sheet
   owner (kiennt@pixon.games) can grant that.

The script says clearly which of these is missing. Pass the message on; don't try to work around it.

```bash
BUG="python ${HERMES_HOME:-$HOME/.hermes}/skills/productivity/pixi-bug-report/scripts/pixi_bugbase.py"
```

Every command prints JSON with `"ok": true|false`.

## Reporting a bug

### 1. Collect what the user already gave you

Read the whole message, including anything pasted above the request.

- **What broke and where.** Which screen, feature or step.
- **Steps.** What they did, in order, if they said it.
- **Actual result.** Quote error messages **verbatim**, e.g. `Hermes bootstrap failed at stage 'repository': exit code 1`.
- **Expected result.** Often implied, e.g. "phải vào được app".
- **Screenshots.** Images attached in this chat reach you as local file paths, in lines like
  `[Image attached at: /path/to/file.png]` or `image_url: /path/…`. Collect **every** path.
  Look at the images too: they often show the error text or the screen the user forgot to mention.
- **Pasted logs or long error text.** Save it verbatim with your file tool into a `.log` or `.txt`
  file (e.g. in the system temp dir), then attach that file. Never retype or summarize a log
  in place of attaching it.
- **Files they point to** ("file log ở ~/Downloads/x.log"). Attach them if they exist.

### 2. Ask only if it is truly missing

If you can't tell **what** broke or **where**, ask **one** short question covering everything
missing, then wait. Otherwise don't interview the reporter. A report like "cài trên mac, tới
bước cài Pixi Agent thì lỗi, kèm ảnh + log" is complete.

For bugs about install, startup, crashes, connection or the agent failing, also offer to attach
this machine's logs **in that same question**: "Mình gửi kèm log Pixi của máy (đã che token)
cho dev nhé?". Logs can contain bits of the user's chats, so never attach them without a yes.
If the user already asked to include logs, don't ask again.

### 3. Fill in the fields

| Field | How |
|---|---|
| `--title` | One line: `<where>: <what goes wrong>`, in the user's language. E.g. `Cài đặt macOS: bước "Repository" lỗi, app báo "Pixi couldn't start"`. |
| `--desc` | Numbered steps, then `→ Thực tế: …` with the verbatim error. Add the frequency (luôn luôn / thỉnh thoảng) if known. Use the user's words; don't invent steps. |
| `--expected` | What should have happened, one sentence. |
| `--severity` | See the table below. |
| `--module` | Exactly one module name from the list below. |
| `--version` | Only if the user mentioned the Pixi version. The engine commit is added automatically. |
| `--platform` | Only if the bug is on a **different** machine or is web/admin. It defaults to this machine's OS. Values: `Windows`, `macOS`, `Linux`, `Web (Admin)`, `Tất cả`. |
| `--attach` | All screenshot paths plus any log or text files from step 1. |
| `--attach-logs` | Only after the user said yes in step 2. |

**Severity**

| Value | Meaning |
|---|---|
| `Critical` | Crash, data loss, security or privacy leak, or Pixi or a whole feature can't be used, with no workaround. Install and startup failures are here. |
| `Major` | A main feature behaves wrongly; a workaround exists but is painful. |
| `Minor` | A secondary feature is wrong, or there's an easy workaround. |
| `Trivial` | Typos, misaligned UI, colors. Doesn't affect use. |

**Modules** (use the exact text):

- `Desktop – Cài đặt / Update`
- `Desktop – Đăng nhập`
- `Desktop – Chat / Agent`
- `Desktop – Skills / Tools / MCP`
- `Desktop – Widget pet`
- `Desktop – Settings / Khác`
- `Admin – Nhân sự / Tổ chức / Phân quyền`
- `Admin – LLM / Gateway / Hạn mức`
- `Admin – Artifacts / Share`
- `Admin – Feedback`
- `Admin – App Connect / Google Workspace`
- `Admin – Khác`
- `Backend / API`
- `MCP Server / Connector`
- `Khác`

The sheet's list can grow. Run `$BUG options` to see the current one.

### 4. Submit

```bash
$BUG submit --title "…" --severity Critical --module "Desktop – Cài đặt / Update" \
  --desc "1. …
2. …
→ Thực tế: …" --expected "…" --attach /path/a.png /path/b.png /tmp/pasted.log [--attach-logs]
```

Quote every argument. Multi-line `--desc` is fine inside quotes.

### 5. Reply

Keep it short, in the user's language. Include:

- the bug ID and the sheet link from the output (`sheet`)
- what was attached
- that the dev team will update the status in the sheet
- that they can ask "bug BUG-00xx sao rồi" any time

Don't paste the JSON.

**If `attachment_errors` is not empty:** the bug was still logged, just without those files,
and the row carries a note saying so. Tell the user which files didn't make it. Ask them to
drop those files into the attachments folder, named with the bug ID (e.g. `BUG-0012_screen.png`),
or to send them again so you can retry.

**If `ok` is false:**

- **Not connected, or token unusable (exit 2):** tell them to click "Kết nối Google Workspace"
  in Pixi, then say "thử lại".
- **No permission (exit 4):** tell them their Google account needs Editor access to Pixi
  Bugbase and to ask kiennt@pixon.games. Then give them the finished report as text (title,
  description, severity, module) so nothing is lost.
- **Missing libraries (exit 3):** run the `setup.py --install-deps` command the error prints,
  then retry once.

## Checking status

- `$BUG status BUG-0012` (also accepts `12`) returns status, severity, assignee, the dev's
  progress notes (newest first), the build that has the fix, and the dates.
- `$BUG mine` returns the bugs this Google account reported.

What the statuses mean for the reporter:

| Status | Meaning |
|---|---|
| New | Chưa ai xem |
| Need Info | Dev cần thêm thông tin. Read the latest progress note and help the user answer it. |
| Confirmed / In Progress | Đang xử lý |
| Fixed | Đã fix, chờ bạn test lại trên bản ghi ở "Fix trong bản" |
| Reopened | Test lại vẫn lỗi |
| Closed | Xong |
| Won't Fix / Duplicate | Không fix. The note says why, or which bug it duplicates. |

When a bug is **Fixed**, the reporter is expected to retest. If the user confirms it works or
still fails, tell them to set the status to **Closed** or **Reopened** in the sheet. The script
does not change status; this skill only adds bugs and reads them.

## Rules

- One bug per row. If the user describes two unrelated problems, submit two bugs and say so.
- Never edit or delete other rows. Status, priority and progress columns belong to the dev team.
- Before submitting, run `$BUG mine`. If the same user already reported the same thing, don't
  file it again; point them to the existing ID.
