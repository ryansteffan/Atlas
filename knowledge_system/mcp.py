from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .core import KnowledgeProject


TOOLS = [
    {"name": "knowledge_init", "description": "Initialize project knowledge.", "inputSchema": {"type": "object"}},
    {"name": "knowledge_search", "description": "Search project knowledge.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "knowledge_verify", "description": "Verify project knowledge structure.", "inputSchema": {"type": "object"}},
    {"name": "knowledge_config", "description": "Read local agent configuration.", "inputSchema": {"type": "object"}},
    {"name": "knowledge_read", "description": "Read a knowledge file.", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
]


def response(request_id: Any, result: Any = None, error: dict[str, Any] | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        message["error"] = error
    else:
        message["result"] = result
    return message


def handle(message: dict[str, Any], root: Path) -> dict[str, Any] | None:
    request_id = message.get("id")
    method = message.get("method")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return response(request_id, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "knowledge", "version": "0.1.0"}})
    if method == "tools/list":
        return response(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params", {})
        name = params.get("name")
        arguments = params.get("arguments", {})
        project = KnowledgeProject(root)
        if name == "knowledge_init":
            value = project.init()
        elif name == "knowledge_search":
            value = {"query": arguments["query"], "results": project.search(arguments["query"])}
        elif name == "knowledge_verify":
            value = project.project_verify()
        elif name == "knowledge_config":
            value = project.get_config()
        elif name == "knowledge_read":
            requested = root / arguments["path"]
            if requested.is_symlink() or any(parent.is_symlink() for parent in requested.parents):
                raise ValueError("Symlink paths are not allowed")
            path = requested.resolve()
            knowledge_root = (root / "knowledge").resolve()
            if knowledge_root not in path.parents or path.is_symlink():
                raise ValueError("Path must be a non-symlink file inside knowledge/")
            value = path.read_text(encoding="utf-8")
        else:
            return response(request_id, error={"code": -32601, "message": f"Unknown tool: {name}"})
        return response(request_id, {"content": [{"type": "text", "text": json.dumps(value, indent=2) if not isinstance(value, str) else value}], "structuredContent": value})
    return response(request_id, error={"code": -32601, "message": f"Unknown method: {method}"})


def main() -> int:
    root = Path.cwd()
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            output = handle(message, root)
            if output is not None:
                print(json.dumps(output), flush=True)
        except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
            print(json.dumps(response(None, error={"code": -32603, "message": str(error)})), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
