# Using the hub from Pixi (Hermes runtime)

Pixi is not `claude-code` and not `cursor`. Two things follow, and they are the
only two that differ from the rest of this skill.

## 1. The connector is already there — you do not paste a token

`references/connect.md` describes adding the MCP server by hand. **Skip that on
Pixi.** Pixi's server writes the connector into each employee's `config.yaml`
when their profile is built:

```yaml
mcp_servers:
  skillhub:
    url: https://skillhub.pixon.cc/mcp
    headers:
      Authorization: Bearer ${PIXI_MCP_TOKEN_SKILLHUB}
```

The token itself never touches disk — the desktop app resolves
`${PIXI_MCP_TOKEN_SKILLHUB}` at spawn from the credential Pixi minted for that
person. So the hub's tools show up on their own, named after the `skillhub`
server (`skillhub__search_skills`, `skillhub__download_skill_zip`, …).

**If the tools are missing, the fix is not a token.** The person has not been
granted the `skillhub` app. A Pixi admin grants it in the console under
**Settings → App Connect**, at whichever level applies (department, position, or
that one person); the linker runs on login and every 15 minutes. Tell them that
rather than walking them through `claude mcp add` — that command configures
Claude Code, not Pixi, and will not give Pixi the tools.

An MCP server added to `config.yaml` needs a reload before its tools appear
(`/reload-mcp`, or the config watcher). A *skill* does not — see below.

## 2. Install into Pixi's own skills directory, not `.claude/skills/`

`download_skill_zip` and `install_skill` both answer with a `place` map that
only knows `claude-code` → `.claude/skills/` and `cursor` → `.cursor/skills/`.
**Ignore `place`.** Pass a supported `runtime` anyway — the dependency closure
and the files it returns are runtime-agnostic — and unpack into Pixi's skills
directory instead:

| OS | Skills directory |
|---|---|
| Windows | `%LOCALAPPDATA%\hermes\skills\` |
| macOS / Linux | `~/.hermes/skills/` |

`HERMES_HOME` overrides both when it is set, and the skills dir is always
`$HERMES_HOME/skills`. Check it before writing rather than assuming the default
— a profile install moves it.

So the `download_skill_zip` command, which arrives written for `.claude/skills/`:

```bash
curl -fsSL "<url>" -o my-skill.zip && unzip -oq my-skill.zip -d .claude/skills/ && rm my-skill.zip
```

becomes, on Pixi (Windows shown; the archive already unpacks to a folder named
after the skill, which is exactly the layout Pixi expects):

```bash
curl -fsSL "<url>" -o my-skill.zip \
  && unzip -oq my-skill.zip -d "$LOCALAPPDATA/hermes/skills/" \
  && rm my-skill.zip
```

Then write the call's `lock` array to `<skill-folder>/skillhub.lock` so the
install is reproducible and `sync_fork` / update checks have a baseline.

Dependency nodes come back with `hidden: true`. Write them too — the parent
needs them; hidden only means "do not advertise this one to the user".

**No restart.** Pixi reads skills straight off that directory, so a freshly
written skill is usable in the same session. (Contrast the MCP servers above,
which do need a reload.)

## 3. Publishing from Pixi

Nothing changes. The default publish path in `SKILL.md` — zip the folder and
`POST {hub}/api/skills/folder/zip` — works the same here, and is still the one
to reach for: it moves the bytes in one request instead of retyping every file
through the model. Two Windows notes, both of which bite on Pixi more than
elsewhere:

- Write the `.zip` **beside the folder**, not in `/tmp`. The shell and Python
  disagree about where `/tmp` is on Windows, and the upload then reads nothing.
- No `zip` binary? Use the stdlib:
  `python -c "import shutil;shutil.make_archive('my-skill','zip','.','my-skill')"`

## 4. Skills that ship with Pixi

This skill is one of Pixi's **bundled** skills: it lives in the Pixi engine repo
under `skills/software-development/skill-hub/` and is seeded into each user's
skills directory on install and update. That seeding never overwrites a skill
the user has edited, and never re-adds one they deleted — so a person who has
their own copy keeps it.

Editing the copy in the skills directory therefore only changes that one
machine. To change it **for everybody**, edit it in the engine repo and ship it;
to change it for the whole org *outside* Pixi, publish a new version to the hub
instead.
