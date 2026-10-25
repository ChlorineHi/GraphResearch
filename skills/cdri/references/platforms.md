# Platform notes

The skill is a folder (`SKILL.md`, `references/`, `scripts/`, `assets/`). `install.py` copies or links it.
Discovery paths below are the conventional ones at the time of writing; if your tool version uses a different
directory, pass `--dest`.

| Platform | Install target (user) | Notes |
|---|---|---|
| Claude Code | `~/.claude/skills/cdri/` | Native skills; auto-invoked from the description. Project scope: `.claude/skills/`. |
| Codex CLI | `~/.codex/skills/cdri/` (also `~/.agents/skills/cdri/`) | `install.py` can append a pointer block to `~/.codex/AGENTS.md` (`--agents-md`). |
| Cursor | `~/.cursor/skills/cdri/` | Project scope: `.cursor/skills/`. Optional rule `.cursor/rules/cdri.mdc` (`--cursor-rule`). |
| OpenCode | `~/.config/opencode/skill/cdri/` | Project scope: `.opencode/skill/`. Some versions read `.claude/skills` too. |

Shell usage is identical everywhere: `python <installed path>/scripts/cdri.py ...`. On Windows use `python`
(or `py -3`); the CLI forces UTF-8 output. Network access must be allowed by the agent's sandbox for searches;
when it is not, the CLI reports `offline`/`error` per source - say so in the report.

Long-running work: agents run only while invoked. Use `session start/note/resume` and `refresh run` explicitly;
CDRI never schedules itself.
