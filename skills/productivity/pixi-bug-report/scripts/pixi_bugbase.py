#!/usr/bin/env python3
"""Log a Pixi bug into the Pixi Bugbase sheet, and look up bugs already there.

Runs as the employee's own Google account, reusing the OAuth token the
google-workspace skill keeps in HERMES_HOME (created by Pixi's
"Kết nối Google Workspace" button).

    pixi_bugbase.py submit --title T --severity S --module M --desc D
                           [--expected E] [--version V] [--platform P]
                           [--attach FILE ...] [--attach-logs]
    pixi_bugbase.py status BUG-0012
    pixi_bugbase.py mine
    pixi_bugbase.py options
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SHEET_ID = "1MYs_ROps75bdzoVy0wqTj9XVQBMxpF44shfFSmgf4Ho"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
EVIDENCE_FOLDER = "16eJZpykYk7hFRwuc2uQO2UYIcLwDoLn0"
OWNER = "kiennt@pixon.games"
TAB = "Bugs"
TAB_GID = 0
FIRST_ROW = 3
LAST_ROW = 1000
COLS = ["id", "status", "title", "severity", "module", "platform", "version", "desc", "expected",
        "image", "links", "reporter", "reported", "priority", "assignee", "progress", "fix_in",
        "updated", "closed"]
SEVERITIES = ["Critical", "Major", "Minor", "Trivial"]
PLATFORMS = ["Windows", "macOS", "Linux", "Web (Admin)", "Tất cả"]
LOG_FILES = ["desktop.log", "errors.log", "agent.log", "gateway.log"]
LOG_TAIL_LINES = 400
VN_TZ = dt.timezone(dt.timedelta(hours=7))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Reuse the google-workspace skill's token handling (same skills category dir).
_GW_SCRIPTS = Path(__file__).resolve().parents[2] / "google-workspace" / "scripts"
sys.path.insert(0, str(_GW_SCRIPTS))


def fail(msg: str, code: int = 1):
    print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False, indent=1))
    sys.exit(code)


def hermes_home() -> Path:
    try:
        from _hermes_home import get_hermes_home
        return Path(get_hermes_home())
    except Exception:
        val = os.environ.get("HERMES_HOME", "").strip()
        return Path(val) if val else Path.home() / ".hermes"


def services():
    token = hermes_home() / "google_token.json"
    if not token.exists():
        fail("Chưa kết nối Google. Mở Pixi → bấm \"Kết nối Google Workspace\" rồi thử lại.", 2)
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as e:
        fail(f"Thiếu thư viện Google ({e}). Chạy: python \"{_GW_SCRIPTS / 'setup.py'}\" --install-deps", 3)
    data = json.loads(token.read_text(encoding="utf-8"))
    # When gws refreshes this file it stores `expiry` as seconds-until-expiry (an int),
    # which google-auth cannot parse. Drop it and always refresh; the file is left as is.
    if not isinstance(data.get("expiry"), str):
        data.pop("expiry", None)
    try:
        creds = Credentials.from_authorized_user_info(data, data.get("scopes"))
        creds.refresh(Request())
    except Exception as e:
        fail(f"Token Google không dùng được ({e}). Bấm lại \"Kết nối Google Workspace\" trong Pixi.", 2)
    granted = set(data.get("scopes") or [])
    need = {"https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"}
    if granted and not need & granted:
        fail("Token Google hiện tại không có quyền Sheets/Drive. Bấm lại \"Kết nối Google Workspace\" trong Pixi để cấp quyền.", 2)
    return (build("sheets", "v4", credentials=creds, cache_discovery=False),
            build("drive", "v3", credentials=creds, cache_discovery=False))


def http_error(e) -> None:
    status = getattr(getattr(e, "resp", None), "status", None)
    if status in (403, 404):
        fail(f"Tài khoản Google của bạn chưa có quyền sửa file Pixi Bugbase ({SHEET_URL}). "
             f"Nhờ {OWNER} cấp quyền Editor cho file và thư mục Evidence, rồi thử lại.", 4)
    fail(f"Google API lỗi ({status}): {e}")


def serial(t: dt.datetime) -> float:
    d = t.replace(tzinfo=None) - dt.datetime(1899, 12, 30)
    return round(d.days + d.seconds / 86400, 6)


def now_vn() -> dt.datetime:
    return dt.datetime.now(VN_TZ).replace(second=0, microsecond=0)


def cell(row: int, key: str, value) -> dict:
    col = COLS.index(key)
    v = {"numberValue": value} if isinstance(value, (int, float)) else {"stringValue": str(value)}
    return {"updateCells": {"range": {"sheetId": TAB_GID, "startRowIndex": row - 1, "endRowIndex": row,
                                      "startColumnIndex": col, "endColumnIndex": col + 1},
                            "fields": "userEnteredValue", "rows": [{"values": [{"userEnteredValue": v}]}]}}


def read_rows(sheets) -> list[dict]:
    res = sheets.spreadsheets().values().get(spreadsheetId=SHEET_ID, range=f"{TAB}!A{FIRST_ROW}:S{LAST_ROW}").execute()
    rows = []
    for i, vals in enumerate(res.get("values", [])):
        vals = vals + [""] * (len(COLS) - len(vals))
        r = dict(zip(COLS, vals))
        r["row"] = FIRST_ROW + i
        rows.append(r)
    return rows


def me(drive) -> dict:
    u = drive.about().get(fields="user(displayName,emailAddress)").execute().get("user", {})
    return {"name": u.get("displayName") or u.get("emailAddress", ""), "email": u.get("emailAddress", "")}


def detect_platform() -> str:
    return {"Darwin": "macOS", "Windows": "Windows", "Linux": "Linux"}.get(platform.system(), "")


def engine_version() -> str:
    """Short commit of the engine checkout — the closest thing to a build id the agent can see."""
    for root in (hermes_home() / "hermes-agent", Path(__file__).resolve().parents[4]):
        if (root / ".git").exists():
            try:
                sha = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                                     capture_output=True, text=True, timeout=5).stdout.strip()
                if sha:
                    return f"engine {sha}"
            except Exception:
                pass
    return ""


_SECRET_PATTERNS = [
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{12,}"), r"\1[REDACTED]"),
    (re.compile(r"\b(sk|pk|rk|ghp|gho|glpat|xox[abp])[-_][A-Za-z0-9_-]{10,}"), "[REDACTED]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"), "[REDACTED_JWT]"),
    (re.compile(r'(?i)("?(?:access_token|refresh_token|id_token|api[_-]?key|client_secret|password|passwd|secret|token)"?\s*[:=]\s*"?)[^"\s,;}&]{6,}'), r"\1[REDACTED]"),
]


def redact(text: str) -> str:
    for pat, repl in _SECRET_PATTERNS:
        text = pat.sub(repl, text)
    return text


def collect_logs() -> Path | None:
    """Last lines of the local Pixi/engine logs, secrets masked, in one file."""
    logs = hermes_home() / "logs"
    parts = []
    for name in LOG_FILES:
        p = logs / name
        if not p.exists():
            continue
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[-LOG_TAIL_LINES:]
        except OSError:
            continue
        parts.append(f"===== {name} (last {len(lines)} lines) =====\n" + redact("\n".join(lines)))
    if not parts:
        return None
    out = Path(tempfile.mkdtemp(prefix="pixi-bug-")) / "pixi-logs.txt"
    out.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    return out


def upload(drive, path: Path, name: str) -> str:
    from googleapiclient.http import MediaFileUpload
    import mimetypes
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    f = drive.files().create(body={"name": name, "parents": [EVIDENCE_FOLDER]},
                             media_body=MediaFileUpload(str(path), mimetype=mime, resumable=False),
                             fields="id", supportsAllDrives=True).execute()
    return f"https://drive.google.com/file/d/{f['id']}/view"


def claim_row(sheets, title: str) -> int:
    """Write the title into the first empty row and read it back, so two people
    reporting at the same moment don't land on one row."""
    for _ in range(5):
        rows = read_rows(sheets)
        taken = {r["row"] for r in rows if r["title"].strip()}
        row = next((n for n in range(FIRST_ROW, LAST_ROW + 1) if n not in taken), None)
        if row is None:
            fail(f"Sheet đã đầy {LAST_ROW} dòng — báo {OWNER} mở rộng thêm dòng.")
        sheets.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": [cell(row, "title", title)]}).execute()
        got = sheets.spreadsheets().values().get(spreadsheetId=SHEET_ID, range=f"{TAB}!C{row}").execute()
        if (got.get("values") or [[""]])[0][0] == title:
            return row
    fail("Không giành được dòng trống sau 5 lần thử — thử lại sau ít phút.")


def pick(value: str | None, allowed: list[str], label: str) -> str:
    if not value:
        return ""
    for a in allowed:
        if a.lower() == value.strip().lower():
            return a
    fail(f"{label} phải là một trong: {', '.join(allowed)}")


def cmd_submit(a):
    severity = pick(a.severity, SEVERITIES, "--severity")
    plat = pick(a.platform, PLATFORMS, "--platform") if a.platform else detect_platform()
    attach = [Path(p).expanduser() for p in (a.attach or [])]
    missing = [str(p) for p in attach if not p.is_file()]
    if missing:
        fail("Không tìm thấy file đính kèm: " + ", ".join(missing))
    sheets, drive = services()
    from googleapiclient.errors import HttpError
    try:
        who = me(drive)
        row = claim_row(sheets, a.title)
    except HttpError as e:
        http_error(e)
    bug_id = f"BUG-{row - 2:04d}"
    if a.attach_logs:
        lp = collect_logs()
        if lp:
            attach.append(lp)
    # The row is claimed now: a failed upload must not leave it holding only a title,
    # so record the failure and still write the report.
    links, upload_errors = [], []
    for i, p in enumerate(attach, 1):
        try:
            links.append((p.name, upload(drive, p, f"{bug_id}_{i}_{p.name}")))
        except Exception as e:
            upload_errors.append({"file": str(p), "error": str(e)[:300]})
    try:
        version = " · ".join(x for x in (a.version, engine_version()) if x) or "?"
        t = now_vn()
        reqs = [cell(row, "status", "New"), cell(row, "severity", severity), cell(row, "module", a.module),
                cell(row, "platform", plat), cell(row, "version", version), cell(row, "desc", a.desc),
                cell(row, "reporter", who["name"]), cell(row, "reported", serial(t)), cell(row, "updated", serial(t))]
        if a.expected:
            reqs.append(cell(row, "expected", a.expected))
        if links:
            text, runs = "", []
            u16 = lambda s: len(s.encode("utf-16-le")) // 2
            for i, (label, url) in enumerate(links):
                text += "\n" if i else ""
                runs.append({"startIndex": u16(text), "format": {"link": {"uri": url}, "underline": True}})
                text += label
            col = COLS.index("links")
            reqs.append({"updateCells": {"range": {"sheetId": TAB_GID, "startRowIndex": row - 1, "endRowIndex": row,
                                                   "startColumnIndex": col, "endColumnIndex": col + 1},
                                         "fields": "userEnteredValue,textFormatRuns",
                                         "rows": [{"values": [{"userEnteredValue": {"stringValue": text}, "textFormatRuns": runs}]}]}})
        if upload_errors:
            note = "Không upload được: " + ", ".join(Path(x["file"]).name for x in upload_errors)
            reqs.append(cell(row, "progress", f"{t:%d/%m} – {note} (người báo cần gửi lại file)"))
        sheets.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": reqs}).execute()
    except HttpError as e:
        # Release the claimed row rather than leave a title with no report behind it.
        try:
            sheets.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": [cell(row, "title", "")]}).execute()
        except Exception:
            pass
        http_error(e)
    print(json.dumps({"ok": True, "id": bug_id, "row": row, "reporter": who["name"], "severity": severity,
                      "module": a.module, "platform": plat, "version": version,
                      "attachments": [{"file": l, "url": u} for l, u in links],
                      "attachment_errors": upload_errors,
                      "sheet": f"{SHEET_URL}/edit#gid={TAB_GID}&range=A{row}"}, ensure_ascii=False, indent=1))


def cmd_status(a):
    m = re.search(r"(\d+)", a.id)
    if not m:
        fail(f"Mã bug không hợp lệ: {a.id}")
    bug_id = f"BUG-{int(m.group(1)):04d}"
    sheets, _ = services()
    from googleapiclient.errors import HttpError
    try:
        rows = read_rows(sheets)
    except HttpError as e:
        http_error(e)
    for r in rows:
        if r["id"] == bug_id:
            keep = ("id", "status", "title", "severity", "priority", "assignee", "progress", "fix_in",
                    "reporter", "reported", "updated", "closed")
            print(json.dumps({"ok": True, **{k: r[k] for k in keep},
                              "sheet": f"{SHEET_URL}/edit#gid={TAB_GID}&range=A{r['row']}"}, ensure_ascii=False, indent=1))
            return
    fail(f"Không thấy {bug_id} trong Pixi Bugbase.")


def cmd_mine(a):
    sheets, drive = services()
    from googleapiclient.errors import HttpError
    try:
        who = me(drive)
        rows = read_rows(sheets)
    except HttpError as e:
        http_error(e)
    keys = {who["name"].lower(), who["email"].lower()} - {""}
    mine = [{k: r[k] for k in ("id", "status", "severity", "title", "assignee", "updated")}
            for r in rows if r["title"].strip() and r["reporter"].strip().lower() in keys]
    print(json.dumps({"ok": True, "reporter": who["name"], "bugs": mine}, ensure_ascii=False, indent=1))


def cmd_options(a):
    sheets, _ = services()
    from googleapiclient.errors import HttpError
    try:
        res = sheets.spreadsheets().values().get(spreadsheetId=SHEET_ID, range="'Danh mục'!A1:F60",
                                                 majorDimension="COLUMNS").execute()
    except HttpError as e:
        http_error(e)
    out = {col[0]: [v for v in col[1:] if v] for col in res.get("values", []) if col}
    print(json.dumps({"ok": True, **out}, ensure_ascii=False, indent=1))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submit")
    for f in ("--title", "--severity", "--module", "--desc"):
        s.add_argument(f, required=True)
    s.add_argument("--expected")
    s.add_argument("--version", help="Pixi app version if the user knows it; the engine commit is added automatically")
    s.add_argument("--platform", help="defaults to this machine's OS")
    s.add_argument("--attach", nargs="*", help="screenshots / videos / log files to upload")
    s.add_argument("--attach-logs", action="store_true", help="also attach the tail of this machine's Pixi logs (secrets masked)")
    s.set_defaults(fn=cmd_submit)
    s = sub.add_parser("status"); s.add_argument("id"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("mine"); s.set_defaults(fn=cmd_mine)
    s = sub.add_parser("options"); s.set_defaults(fn=cmd_options)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
