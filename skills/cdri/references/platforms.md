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

## Source access failures in OpenCode or another agent

HTTP 429 from Semantic Scholar and anti-bot HTML from DBLP indicate source-access failures; inspect the run's
`summary.json` before calling the whole task failed. Successful OpenAlex/Crossref/arXiv/PubMed/Europe PMC
results remain usable with incomplete source coverage disclosed. `empty` means a completed query with no matches.
The runner pauses a rate-limited/blocked source within the current run and logs later operations as
`skipped_source`; explicitly restricting a later run to working sources is also supported.

Set `S2_API_KEY` in the environment that launches OpenCode, then restart OpenCode so Python inherits it.
`config show` and `config check --ping` report whether the CLI sees it without printing its value. A key may
improve access but cannot guarantee success. DBLP challenges have no corresponding key setting in this skill;
continue other databases and record the coverage gap. Updating model prompts does not remove server-side limits.

For a targeted retry with an explicit source scope:

```bash
python <skill-dir>/scripts/cdri.py search "<research question>" --source openalex --source crossref --source arxiv --source europepmc --source pubmed
```

Only select sources relevant to the topic. This is a fresh scoped search, not a repair of the failed historical
run; preserve both run logs and do not add per-run unique counts without cross-run deduplication.
