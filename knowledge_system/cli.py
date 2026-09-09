from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .core import DOC_TEMPLATE, SPEC_TEMPLATE, Issue, KnowledgeProject, read_content, result


EXIT_VERIFICATION_FAILED = 2


def path_argument(project: KnowledgeProject, value: str, kind: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return (project.root / candidate).resolve()
    base = project.specs if kind == "spec" else project.docs
    if kind == "spec":
        name = value if value.endswith(".spec.md") else f"{value}.spec.md"
        return (base / name).resolve()
    return (project.root / candidate).resolve()


def spec_path(project: KnowledgeProject, value: str) -> Path:
    candidate = Path(value)
    if candidate.parts and candidate.parts[0] == "knowledge":
        return (project.root / candidate).resolve()
    return path_argument(project, value, "spec")


def doc_path(project: KnowledgeProject, value: str) -> Path:
    resource = path_argument(project, value, "doc")
    return project.documentation_path(resource)


def render(value: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, indent=2))
    elif isinstance(value, str):
        print(value, end="" if value.endswith("\n") else "\n")
    elif isinstance(value, dict) and "status" in value:
        print(f"{value['status']}: {value.get('target', {}).get('path', '.')}")
        for issue in value.get("issues", []):
            print(f"- {issue['severity']}: {issue['description']}")
    else:
        print(json.dumps(value, indent=2))


def operation(args: argparse.Namespace) -> tuple[Any, int]:
    project = KnowledgeProject(Path(args.root))
    command = args.command
    if command == "init":
        return project.init(), 0
    if command == "search":
        return {"query": args.query, "results": project.search(args.query)}, 0
    if command == "verify":
        value = project.project_verify()
        return value, EXIT_VERIFICATION_FAILED if value["status"] == "fail" else 0
    if command == "doctor":
        structural = project.project_verify()
        directories, files = project.project_resources()
        resources = len(directories) + len(files)
        documented = sum(
            project.documentation_path(path).is_file() for path in [*directories, *files]
        )
        return {
            "coverage": {"documented": documented, "resources": resources},
            "verification": structural,
        }, EXIT_VERIFICATION_FAILED if structural["status"] == "fail" else 0
    if command == "config":
        if args.config_action == "get":
            return project.get_config().get(args.key), 0
        if args.config_action == "set":
            return project.set_config(args.key, args.value), 0
        return project.get_config(), 0
    if command in {"spec", "doc"}:
        return spec_or_doc(project, args)
    raise ValueError(f"Unknown command: {command}")


def spec_or_doc(project: KnowledgeProject, args: argparse.Namespace) -> tuple[Any, int]:
    kind = args.command
    action = args.action
    if kind == "spec":
        path = spec_path(project, args.path)
        template = SPEC_TEMPLATE
    else:
        resource = path_argument(project, args.path, "doc")
        if not resource.exists() and action in {"create", "read", "update", "verify"}:
            raise FileNotFoundError(f"project resource not found: {project.rel(resource)}")
        path = doc_path(project, args.path)
        template = DOC_TEMPLATE
    if action == "read":
        if not path.is_file():
            raise FileNotFoundError(f"{kind} not found: {path}")
        return path.read_text(encoding="utf-8"), 0
    if action == "create":
        if path.exists():
            raise FileExistsError(f"{kind} already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(template, encoding="utf-8")
        return {"path": project.rel(path), "created": True}, 0
    if action in {"update", "delete"}:
        if action == "delete":
            if not path.is_file():
                raise FileNotFoundError(f"documentation not found: {path}")
            path.unlink()
            return {"path": project.rel(path), "deleted": True}, 0
        if not path.is_file():
            raise FileNotFoundError(f"{kind} not found: {path}")
        path.write_text(read_content(args.content, args.file), encoding="utf-8")
        return {"path": project.rel(path), "updated": True}, 0
    if action == "verify":
        verification = project.knowledge_verify(path, kind)
        return verification, EXIT_VERIFICATION_FAILED if verification["status"] == "fail" else 0
    raise ValueError(f"Unknown {kind} action: {action}")


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="knowledge", description="Project Knowledge System CLI")
    parser.add_argument("--root", default=".", help="Project root (default: current directory)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("spec", "doc"):
        command_parser = sub.add_parser(command)
        command_parser.add_argument("--json", action="store_true", dest="as_json", default=argparse.SUPPRESS)
        command_parser.add_argument("--root", default=argparse.SUPPRESS)
        command_parser.add_argument("action", choices=("read", "create", "update", "verify") if command == "spec" else ("read", "create", "update", "delete", "verify"))
        command_parser.add_argument("path")
        command_parser.add_argument("--content")
        command_parser.add_argument("--file")
    init = sub.add_parser("init")
    init.add_argument("--json", action="store_true", dest="as_json", default=argparse.SUPPRESS)
    init.add_argument("--root", default=argparse.SUPPRESS)
    search = sub.add_parser("search")
    search.add_argument("--json", action="store_true", dest="as_json", default=argparse.SUPPRESS)
    search.add_argument("--root", default=argparse.SUPPRESS)
    search.add_argument("query")
    verify = sub.add_parser("verify")
    verify.add_argument("--json", action="store_true", dest="as_json", default=argparse.SUPPRESS)
    verify.add_argument("--root", default=argparse.SUPPRESS)
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--json", action="store_true", dest="as_json", default=argparse.SUPPRESS)
    doctor.add_argument("--root", default=argparse.SUPPRESS)
    config = sub.add_parser("config")
    config.add_argument("--json", action="store_true", dest="as_json", default=argparse.SUPPRESS)
    config.add_argument("--root", default=argparse.SUPPRESS)
    config_sub = config.add_subparsers(dest="config_action")
    config_sub.add_parser("list")
    get = config_sub.add_parser("get")
    get.add_argument("key")
    set_parser = config_sub.add_parser("set")
    set_parser.add_argument("key")
    set_parser.add_argument("value")
    help_parser = sub.add_parser("help")
    help_parser.add_argument("--json", action="store_true", dest="as_json", default=argparse.SUPPRESS)
    help_parser.add_argument("--root", default=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "help":
        parser().print_help()
        return 0
    try:
        value, code = operation(args)
        render(value, args.as_json)
        return code
    except (OSError, ValueError, FileNotFoundError, FileExistsError) as error:
        if args.as_json:
            print(json.dumps({"error": str(error)}))
        else:
            print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
