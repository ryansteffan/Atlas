# Project Knowledge System

This repository contains a local, provider-neutral knowledge CLI and stdio MCP
server for AI-assisted development.

## Install

```powershell
python -m pip install -e .
knowledge help
```

## Fast setup

From the root of the project you want to develop:

```powershell
knowledge setup --provider auto --mcp-client vscode --skill copilot
```

This safely:

1. creates the `knowledge/` structure and initial documentation;
2. configures automatic local-agent detection;
3. generates `.vscode/mcp.json` for the local MCP server;
4. installs the skill into the selected agent's project instructions;
5. leaves existing files untouched and fails instead of overwriting them.

Use `--mcp-client claude` or `--mcp-client cursor` for those clients. Use
`--mcp-client none` when configuring MCP manually or through another client.
Use `--skill all` to install the skill for all supported agents:

| Agent | Project-local destination |
| --- | --- |
| GitHub Copilot | `.github/skills/project-knowledge/SKILL.md` |
| Claude Code | `.claude/skills/project-knowledge/SKILL.md` |
| Codex | `.agents/skills/project-knowledge/SKILL.md` |
| OpenCode | `.opencode/skills/project-knowledge/SKILL.md` |

These are real Agent Skills: each is a directory containing a `SKILL.md` with
portable `name` and `description` metadata. The command refuses to overwrite any
existing skill. Use `--skill none` when skills are managed elsewhere. The source
skill remains available at `skills/project-knowledge/SKILL.md`.

## Manual project use

Run from the project root:

```powershell
knowledge init
knowledge verify
knowledge search "authentication"
knowledge doctor
```

Add generated directories to `.knowledgeignore` before initialization, for example:

```text
node_modules/
.venv/
bin/
obj/
dist/
build/
```

Create and maintain intent and implementation knowledge explicitly:

```powershell
knowledge spec create knowledge/spec/feature.spec.md
knowledge doc read src\feature.py
knowledge doc update src\feature.py --file feature-doc.md
knowledge doc verify src\feature.py
```

`verify` enforces structure and performs deterministic document checks. It can also
delegate semantic comparison to any local coding agent CLI. Configure one explicitly:

```powershell
knowledge config set agent.provider opencode
# Or provide an arbitrary command; the prompt is sent on stdin:
knowledge config set agent.command 'my-agent --json'
knowledge config set agent.timeout 180
```

Supported provider presets are `opencode`, `claude`, `codex`, `github-copilot`, and
`auto`. The adapter asks the tool to return a JSON verification result. If the tool is
unavailable, verification remains deterministic and reports a warning rather than
silently claiming semantic verification.

## MCP

Configure a stdio MCP server with `knowledge_mcp.py` as the command and the target
project root as its working directory:

```json
{
  "command": "python",
  "args": ["C:\\path\\to\\Atlas\\knowledge_mcp.py"],
  "cwd": "${workspaceFolder}"
}
```
