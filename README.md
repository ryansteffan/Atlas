# Project Knowledge System

This repository contains a local, provider-neutral knowledge CLI and stdio MCP
server for AI-assisted development.

## Install the package

Python 3.10 or newer is required. Install directly from GitHub:

```powershell
python -m pip install "project-knowledge-system @ git+https://github.com/ryansteffan/Atlas.git"
knowledge help
```

For development from a local checkout instead:

```powershell
python -m pip install -e C:\path\to\Atlas
```

## Set up a project

The easiest approach is to ask the coding agent already working on the project to
perform setup. From the project root, send it this request:

> Set up Project Knowledge for this project. Run `knowledge setup` for this agent,
> install the project-knowledge skill, configure the appropriate MCP client, and run
> `knowledge verify`. First identify which agent you are, then use the exact command
> from the table below. Do not guess flags or substitute another provider. Only add
> `--enable-agent` after I explicitly approve local-agent execution. Do not overwrite
> existing project files or configuration. Show me every file you create and any setup
> step that needs my approval.

Use exactly one of these commands:

| Agent | Setup command |
| --- | --- |
| GitHub Copilot in VS Code | `knowledge setup --provider github-copilot --enable-agent --mcp-client vscode --skill copilot` |
| Claude Code | `knowledge setup --provider claude --enable-agent --mcp-client claude --skill claude` |
| Codex | `knowledge setup --provider codex --enable-agent --mcp-client none --skill codex` |
| OpenCode | `knowledge setup --provider opencode --enable-agent --mcp-client none --skill opencode` |

If you do not want semantic verification to invoke a local agent yet, omit
`--enable-agent`. Deterministic initialization and verification still work.

If the active agent is not listed, run:

```powershell
knowledge setup --provider auto --mcp-client none --skill none
```

Do not enable semantic agent execution for an unlisted provider unless its command
and JSON output contract have been explicitly configured and approved.

## What setup does

From the root of the project you want to develop:

```powershell
knowledge setup --provider auto --mcp-client vscode --skill copilot
```

This safely:

1. creates the `knowledge/` structure and initial documentation;
2. configures automatic local-agent detection;
3. generates `.vscode/mcp.json` for the local MCP server;
4. installs the real Agent Skill into the selected agent's project skill directory;
5. leaves existing files untouched and fails instead of overwriting them.

When `--enable-agent` is used, approval is stored in a user-level configuration
outside the repository. A repository cannot enable agent execution by committing
files. To disable it later:

```powershell
knowledge setup --disable-agent
```

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

## Verify the setup

Run these commands from the project root:

```powershell
knowledge verify
knowledge doctor
```

`knowledge verify` performs structural and deterministic checks. If a local agent
was explicitly enabled and is installed, it also performs semantic verification.
Otherwise semantic verification is reported as unavailable rather than silently
claiming it ran.

## Daily use

Search before making changes:

```powershell
knowledge search "authentication"
```

The installed skill instructs the agent to read relevant knowledge, specify material
new intent, implement, test, verify, update documentation, and verify again.

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
knowledge config set agent.timeout 180
```

Supported provider presets are `opencode`, `claude`, `codex`, `github-copilot`, and
`auto`. The adapter asks the tool to return a JSON verification result. If the tool is
unavailable, verification remains deterministic and reports a warning rather than
silently claiming semantic verification. Agent execution is disabled by default for
safety because repository configuration and content are untrusted.

The MCP read tool is restricted to files under `knowledge/`; it cannot read arbitrary
workspace files such as `.env`.

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
