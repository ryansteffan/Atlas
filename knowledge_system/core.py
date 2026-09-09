from __future__ import annotations

import fnmatch
import json
import shlex
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


BUILTIN_IGNORES = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "bin",
    "obj",
    "dist",
    "build",
}

SPEC_TEMPLATE = """# Name

## Objective

Describe the intended outcome.

## Requirements

- 

## Behavior

Describe observable behavior.

## Constraints

- 

## Acceptance Criteria

- 

## Open Questions

- None
"""

DOC_TEMPLATE = """# Name

## Purpose

Describe the purpose of this resource.

## Responsibilities

- 

## Behavior

Describe the implemented behavior.

## Interfaces

- 

## Dependencies

- 

## Constraints

- 

## Notes

- 
"""

SPEC_SECTIONS = (
    "# Name",
    "## Objective",
    "## Requirements",
    "## Behavior",
    "## Constraints",
    "## Acceptance Criteria",
    "## Open Questions",
)

DOC_SECTIONS = (
    "# Name",
    "## Purpose",
    "## Responsibilities",
    "## Behavior",
    "## Interfaces",
    "## Dependencies",
    "## Constraints",
    "## Notes",
)

DEFAULT_AGENT_COMMANDS = {
    "opencode": ["opencode", "run", "--format", "json"],
    "claude": ["claude", "-p"],
    "claude-code": ["claude", "-p"],
    "codex": ["codex", "exec"],
    "github-copilot": ["gh", "copilot", "suggest"],
    "copilot": ["gh", "copilot", "suggest"],
}


@dataclass
class Issue:
    severity: str
    category: str
    description: str
    evidence: list[dict[str, Any]] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


class LocalAgentAdapter:
    """Invokes a locally installed coding agent through a configured CLI."""

    def __init__(self, project: "KnowledgeProject"):
        self.project = project
        self.config = project.get_config()

    def command(self) -> list[str] | None:
        configured = self.config.get("agent.command")
        if isinstance(configured, str):
            return shlex.split(configured, posix=False)
        if isinstance(configured, list) and all(isinstance(item, str) for item in configured):
            return configured
        provider = self.config.get("agent.provider", "auto")
        if provider == "auto":
            for name in DEFAULT_AGENT_COMMANDS:
                if shutil.which(DEFAULT_AGENT_COMMANDS[name][0]):
                    provider = name
                    break
        command = DEFAULT_AGENT_COMMANDS.get(str(provider).lower())
        if command and shutil.which(command[0]):
            return command
        return None

    def verify(self, path: Path, kind: str, content: str) -> dict[str, Any] | None:
        command = self.command()
        if command is None:
            return None
        resource = path if kind == "spec" else self.project.resource_for_documentation(path)
        implementation = ""
        if resource is not None and resource.exists():
            if resource.is_file():
                try:
                    implementation = resource.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    implementation = "[binary or non-UTF-8 implementation]"
            else:
                implementation = f"[directory: {self.project.rel(resource)}]"
        prompt = (
            "You are verifying project knowledge. Compare the knowledge document below "
            "with the implementation. Return JSON only with keys status (pass, fail, or "
            "warning), summary (string), and issues (array of objects with severity, "
            "category, description, and optional evidence array). Do not modify files.\n\n"
            f"Knowledge type: {kind}\nKnowledge path: {self.project.rel(path)}\n"
            f"Knowledge document:\n{content}\n\nImplementation:\n{implementation}"
        )
        timeout = int(self.config.get("agent.timeout", 120))
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                cwd=self.project.root,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return {
                "status": "warning",
                "summary": f"Local agent verification could not run: {error}",
                "issues": [
                    {
                        "severity": "warning",
                        "category": "agent",
                        "description": str(error),
                    }
                ],
            }
        if completed.returncode != 0:
            message = completed.stderr.strip() or f"agent exited with code {completed.returncode}"
            return {
                "status": "warning",
                "summary": "Local agent verification failed to execute.",
                "issues": [{"severity": "warning", "category": "agent", "description": message}],
            }
        output = completed.stdout.strip()
        try:
            value = json.loads(output)
        except json.JSONDecodeError:
            return {
                "status": "warning",
                "summary": "Local agent returned non-JSON verification output.",
                "issues": [
                    {
                        "severity": "warning",
                        "category": "agent",
                        "description": output[:1000] or "Agent returned no output.",
                    }
                ],
            }
        if not isinstance(value, dict) or value.get("status") not in {"pass", "fail", "warning"}:
            return {
                "status": "warning",
                "summary": "Local agent returned an invalid verification result.",
                "issues": [
                    {
                        "severity": "warning",
                        "category": "agent",
                        "description": "Expected a JSON object with status pass, fail, or warning.",
                    }
                ],
            }
        return value


def result(
    result_type: str,
    target: str,
    status: str,
    issues: Iterable[Issue] = (),
) -> dict[str, Any]:
    issue_list = list(issues)
    summary = {
        "passed": sum(issue.severity == "info" for issue in issue_list),
        "failed": sum(issue.severity == "error" for issue in issue_list),
        "warnings": sum(issue.severity == "warning" for issue in issue_list),
    }
    if not issue_list and status == "pass":
        summary["passed"] = 1
    return {
        "type": result_type,
        "target": {"path": target},
        "status": status,
        "summary": summary,
        "issues": [issue.as_dict() for issue in issue_list],
    }


class KnowledgeProject:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.knowledge = self.root / "knowledge"
        self.docs = self.knowledge / "docs"
        self.specs = self.knowledge / "spec"
        self.ignore_file = self.root / ".knowledgeignore"

    def rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def ignored(self, path: Path) -> bool:
        try:
            relative = self.rel(path)
        except ValueError:
            return True
        parts = Path(relative).parts
        if any(part in BUILTIN_IGNORES for part in parts):
            return True
        if parts and parts[0] == "knowledge":
            return True
        rules = self._ignore_rules()
        for rule in rules:
            normalized = rule.lstrip("/")
            if fnmatch.fnmatch(relative, normalized) or fnmatch.fnmatch(path.name, normalized):
                return True
            if normalized.endswith("/") and (
                relative == normalized.rstrip("/") or relative.startswith(normalized)
            ):
                return True
        return False

    def _ignore_rules(self) -> list[str]:
        if not self.ignore_file.exists():
            return []
        return [
            line.strip()
            for line in self.ignore_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    def project_resources(self) -> tuple[list[Path], list[Path]]:
        directories: list[Path] = []
        files: list[Path] = []

        def visit(directory: Path) -> None:
            if directory != self.root:
                if self.ignored(directory):
                    return
                directories.append(directory)
            try:
                children = sorted(directory.iterdir(), key=lambda item: item.name.lower())
            except OSError:
                return
            for child in children:
                if self.ignored(child):
                    continue
                if child.is_dir():
                    visit(child)
                elif child.is_file():
                    files.append(child)

        visit(self.root)
        return directories, files

    def documentation_path(self, resource: Path) -> Path:
        relative = resource.relative_to(self.root)
        if resource.is_dir():
            return self.docs / relative / "docs.md"
        return self.docs / f"{relative.as_posix()}.docs.md"

    def resource_for_documentation(self, document: Path) -> Path | None:
        try:
            relative = document.relative_to(self.docs)
        except ValueError:
            return None
        if relative.name == "docs.md":
            resource = self.root / relative.parent
        elif relative.name.endswith(".docs.md"):
            resource = self.root / Path(str(relative)[: -len(".docs.md")])
        else:
            return None
        return resource

    def init(self) -> dict[str, Any]:
        self.docs.mkdir(parents=True, exist_ok=True)
        self.specs.mkdir(parents=True, exist_ok=True)
        root_info = self.knowledge / "root.info.md"
        created = 0
        if not root_info.exists():
            root_info.write_text(
                "# Project Knowledge\n\n"
                f"Project root: `{self.root.name}`.\n\n"
                "Specifications are stored in `knowledge/spec/` and canonical "
                "implementation documentation is stored in `knowledge/docs/`.\n",
                encoding="utf-8",
            )
            created += 1
        directories, files = self.project_resources()
        for resource in [*directories, *files]:
            document = self.documentation_path(resource)
            if not document.exists():
                document.parent.mkdir(parents=True, exist_ok=True)
                kind = "directory" if resource.is_dir() else "file"
                document.write_text(
                    f"# {resource.name}\n\n"
                    f"## Purpose\n\nDocumentation for the project {kind} "
                    f"`{self.rel(resource)}`.\n\n"
                    "## Responsibilities\n\n- \n\n## Behavior\n\n- \n\n"
                    "## Interfaces\n\n- \n\n## Dependencies\n\n- \n\n"
                    "## Constraints\n\n- \n\n## Notes\n\n- \n",
                    encoding="utf-8",
                )
                created += 1
        return {"created": created, "resources": len(directories) + len(files)}

    def structural_verify(self) -> dict[str, Any]:
        directories, files = self.project_resources()
        issues: list[Issue] = []
        expected = {self.documentation_path(resource).resolve() for resource in [*directories, *files]}
        for resource in [*directories, *files]:
            document = self.documentation_path(resource)
            if not document.is_file():
                issues.append(
                    Issue(
                        "error",
                        "structure",
                        f"Missing canonical documentation for {self.rel(resource)}.",
                        [{"path": self.rel(resource)}],
                    )
                )
        actual: set[Path] = set()
        if self.docs.exists():
            for document in self.docs.rglob("*.md"):
                resource = self.resource_for_documentation(document)
                if resource is not None:
                    actual.add(document.resolve())
                    if document.resolve() not in expected:
                        issues.append(
                            Issue(
                                "error",
                                "orphan",
                                f"Documentation has no corresponding project resource: {self.rel(document)}.",
                                [{"path": self.rel(document)}],
                            )
                        )
        for document in expected - actual:
            if document.exists():
                actual.add(document)
        status = "fail" if any(issue.severity == "error" for issue in issues) else "pass"
        return result("structure", ".", status, issues)

    def knowledge_verify(self, path: Path, kind: str) -> dict[str, Any]:
        result_type = "specification" if kind == "spec" else "documentation"
        if not path.is_file():
            return result(
                result_type,
                self.rel(path),
                "fail",
                [Issue("error", "missing", f"Missing {kind}: {self.rel(path)}")],
            )
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return result(
                result_type,
                self.rel(path),
                "fail",
                [Issue("error", "content", f"{kind.capitalize()} is empty.")],
            )
        required_sections = SPEC_SECTIONS if kind == "spec" else DOC_SECTIONS[1:]
        issues: list[Issue] = []
        if kind == "doc" and not any(line.startswith("# ") for line in text.splitlines()):
            issues.append(Issue("error", "format", "Missing required document title."))
        for section in required_sections:
            if section not in text:
                issues.append(Issue("error", "format", f"Missing required section: {section}."))
        if "- \n" in text or "Describe " in text:
            issues.append(
                Issue(
                    "warning",
                    "incomplete",
                    "The resource still contains template placeholders and should be completed.",
                )
            )
        agent_result = LocalAgentAdapter(self).verify(path, kind, text)
        if agent_result is None:
            issues.append(
                Issue(
                    "warning",
                    "semantic",
                    "No local agent provider is configured or installed; deterministic checks only.",
                )
            )
        else:
            issues.extend(
                Issue(
                    issue.get("severity", "warning"),
                    issue.get("category", "agent"),
                    issue.get("description", "Local agent reported an issue."),
                    issue.get("evidence"),
                )
                for issue in agent_result.get("issues", [])
                if isinstance(issue, dict)
            )
        status = "fail" if any(issue.severity == "error" for issue in issues) else "warning"
        return result(result_type, self.rel(path), status, issues)

    def project_verify(self) -> dict[str, Any]:
        structural = self.structural_verify()
        issues = [
            Issue(
                issue["severity"],
                issue["category"],
                issue["description"],
                issue.get("evidence"),
            )
            for issue in structural["issues"]
        ]
        if self.specs.exists():
            for path in sorted(self.specs.rglob("*.spec.md")):
                verification = self.knowledge_verify(path, "spec")
                issues.extend(
                    Issue(
                        issue["severity"],
                        issue["category"],
                        f"{verification['target']['path']}: {issue['description']}",
                        issue.get("evidence"),
                    )
                    for issue in verification["issues"]
                )
        directories, files = self.project_resources()
        for resource in [*directories, *files]:
            document = self.documentation_path(resource)
            if document.is_file():
                verification = self.knowledge_verify(document, "doc")
                issues.extend(
                    Issue(
                        issue["severity"],
                        issue["category"],
                        f"{verification['target']['path']}: {issue['description']}",
                        issue.get("evidence"),
                    )
                    for issue in verification["issues"]
                )
        if any(issue.severity == "error" for issue in issues):
            status = "fail"
        elif any(issue.severity == "warning" for issue in issues):
            status = "warning"
        else:
            status = "pass"
        return result("project", ".", status, issues)

    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def search(self, query: str) -> list[dict[str, Any]]:
        query_lower = query.lower()
        matches: list[dict[str, Any]] = []
        for base in (self.knowledge / "spec", self.knowledge / "docs", self.knowledge / "root.info.md"):
            paths = [base] if base.is_file() else list(base.rglob("*.md")) if base.exists() else []
            for path in paths:
                try:
                    text = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                lines = text.splitlines()
                matching_lines = [
                    {"line": number, "text": line.strip()}
                    for number, line in enumerate(lines, 1)
                    if query_lower in line.lower()
                ]
                if matching_lines:
                    matches.append({"path": self.rel(path), "matches": matching_lines[:10]})
        return matches

    def config_path(self) -> Path:
        return self.knowledge / "config.json"

    def get_config(self) -> dict[str, Any]:
        path = self.config_path()
        if not path.exists():
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("knowledge/config.json must contain a JSON object")
        return value

    def set_config(self, key: str, value: Any) -> dict[str, Any]:
        config = self.get_config()
        if isinstance(value, str):
            try:
                parsed: Any = json.loads(value)
            except json.JSONDecodeError:
                parsed = value
        else:
            parsed = value
        config[key] = parsed
        self.knowledge.mkdir(parents=True, exist_ok=True)
        self.config_path().write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        return config


def read_content(content: str | None, content_file: str | None) -> str:
    if content is not None and content_file is not None:
        raise ValueError("Use only one of --content and --file")
    if content_file is not None:
        return Path(content_file).read_text(encoding="utf-8")
    if content is not None:
        return content
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise ValueError("Content is required; provide --content, --file, or stdin")
