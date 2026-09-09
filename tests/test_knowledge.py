from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from knowledge_system.cli import main
from knowledge_system.core import KnowledgeProject, LocalAgentAdapter
from knowledge_system.mcp import handle


class KnowledgeProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules" / "ignored.js").write_text("ignored", encoding="utf-8")
        self.project = KnowledgeProject(self.root)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_init_is_repeatable_and_maps_files_and_directories(self) -> None:
        self.assertEqual(self.project.init()["created"], 3)
        self.assertEqual(self.project.init()["created"], 0)
        self.assertTrue((self.root / "knowledge" / "docs" / "src" / "docs.md").is_file())
        self.assertTrue(
            (self.root / "knowledge" / "docs" / "src" / "app.py.docs.md").is_file()
        )
        self.assertEqual(self.project.structural_verify()["status"], "pass")

    def test_missing_documentation_is_reported(self) -> None:
        self.project.init()
        (self.root / "knowledge" / "docs" / "src" / "app.py.docs.md").unlink()
        verification = self.project.structural_verify()
        self.assertEqual(verification["status"], "fail")
        self.assertIn("Missing canonical documentation", verification["issues"][0]["description"])

    def test_knowledge_verification_detects_missing_sections(self) -> None:
        spec = self.root / "knowledge" / "spec" / "feature.spec.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("# Name\n\n## Objective\n", encoding="utf-8")
        verification = self.project.knowledge_verify(spec, "spec")
        self.assertEqual(verification["status"], "fail")
        self.assertTrue(any(issue["category"] == "format" for issue in verification["issues"]))

    def test_search_reads_knowledge_resources(self) -> None:
        self.project.init()
        document = self.root / "knowledge" / "docs" / "src" / "app.py.docs.md"
        document.write_text("# App\n\n## Purpose\nHandles authentication.\n", encoding="utf-8")
        matches = self.project.search("authentication")
        self.assertEqual(matches[0]["path"], "knowledge/docs/src/app.py.docs.md")

    def test_project_verify_includes_document_checks(self) -> None:
        self.project.init()
        verification = self.project.project_verify()
        self.assertEqual(verification["status"], "warning")
        self.assertTrue(any(issue["category"] == "semantic" for issue in verification["issues"]))

    def test_local_agent_adapter_accepts_configured_command(self) -> None:
        self.project.set_config(
            "agent.command",
            [sys.executable, "-c", "print('{\"status\":\"pass\",\"issues\":[]}')"],
        )
        adapter = LocalAgentAdapter(self.project)
        self.assertEqual(adapter.command()[:1], [sys.executable])
        self.project.init()
        document = self.root / "knowledge" / "docs" / "src" / "app.py.docs.md"
        verification = adapter.verify(document, "doc", document.read_text(encoding="utf-8"))
        self.assertEqual(verification["status"], "pass")


class InterfaceTests(unittest.TestCase):
    def test_cli_accepts_global_options_after_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(main(["init", "--root", str(root), "--json"]), 0)
            self.assertTrue((root / "knowledge" / "root.info.md").is_file())

    def test_mcp_lists_tools_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialized = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"}, root)
            self.assertEqual(initialized["result"]["serverInfo"]["name"], "knowledge")
            tools = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, root)
            names = {tool["name"] for tool in tools["result"]["tools"]}
            self.assertIn("knowledge_verify", names)
            value = handle(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "knowledge_init", "arguments": {}},
                },
                root,
            )
            self.assertEqual(json.loads(value["result"]["content"][0]["text"])["created"], 1)


if __name__ == "__main__":
    unittest.main()
