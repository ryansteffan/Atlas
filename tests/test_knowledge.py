from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from knowledge_system.cli import main
from knowledge_system.core import DEFAULT_AGENT_COMMANDS, KnowledgeProject, LocalAgentAdapter
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
        self.project.init()
        document = self.root / "knowledge" / "docs" / "src" / "app.py.docs.md"
        with patch.object(KnowledgeProject, "user_config_path", return_value=self.root / "user.json"):
            self.project.set_agent_authorization(True, command=sys.executable)
            self.assertEqual(adapter.command()[:1], [sys.executable])

    def test_agent_execution_is_disabled_by_default(self) -> None:
        self.project.set_config("agent.provider", "codex")
        with patch.object(KnowledgeProject, "user_config_path", return_value=self.root / "user.json"):
            self.assertIsNone(LocalAgentAdapter(self.project).command())

    def test_github_copilot_provider_uses_standalone_cli(self) -> None:
        self.assertEqual(DEFAULT_AGENT_COMMANDS["github-copilot"], ["copilot"])
        self.assertEqual(DEFAULT_AGENT_COMMANDS["copilot"], ["copilot"])

    def test_spec_paths_cannot_escape_knowledge_directory(self) -> None:
        from knowledge_system.cli import main

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root.parent / "outside.spec.md"
            outside.write_text("secret", encoding="utf-8")
            self.assertEqual(
            main(["spec", "read", str(outside), "--root", str(root), "--json"]),
            1,
            )


class InterfaceTests(unittest.TestCase):
    def test_cli_accepts_global_options_after_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(main(["init", "--root", str(root), "--json"]), 0)
            self.assertTrue((root / "knowledge" / "root.info.md").is_file())

    def test_setup_initializes_and_generates_mcp_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(
                main(
                    [
                        "setup",
                        "--root",
                        str(root),
                        "--provider",
                        "auto",
                        "--mcp-client",
                        "vscode",
                        "--skill",
                        "all",
                        "--json",
                    ]
                ),
                0,
            )
            self.assertTrue((root / "knowledge" / "root.info.md").is_file())
            self.assertTrue((root / ".vscode" / "mcp.json").is_file())
            self.assertTrue(
                (root / ".github" / "skills" / "project-knowledge" / "SKILL.md").is_file()
            )
            self.assertTrue(
                (root / ".claude" / "skills" / "project-knowledge" / "SKILL.md").is_file()
            )
            self.assertTrue(
                (root / ".agents" / "skills" / "project-knowledge" / "SKILL.md").is_file()
            )
            self.assertTrue(
                (root / ".opencode" / "skills" / "project-knowledge" / "SKILL.md").is_file()
            )

    def test_setup_can_enable_agent_without_environment_variables(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            user_config = root / "user.json"
            with patch.object(KnowledgeProject, "user_config_path", return_value=user_config):
                self.assertEqual(
                    main(
                        [
                            "setup",
                            "--root",
                            str(root),
                            "--provider",
                            "claude",
                            "--enable-agent",
                            "--json",
                        ]
                    ),
                    0,
                )
                self.assertTrue(
                    json.loads(user_config.read_text(encoding="utf-8"))["projects"]
                )
                self.assertTrue(KnowledgeProject(root).get_agent_authorization()["enabled"])

    def test_skill_installation_does_not_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / ".claude" / "skills" / "project-knowledge" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("user skill", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                KnowledgeProject(root).install_skill("claude")

    def test_installed_skill_contains_strong_workflow_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            KnowledgeProject(root).install_skill("codex")
            content = (
                root / ".agents" / "skills" / "project-knowledge" / "SKILL.md"
            ).read_text(encoding="utf-8")
            self.assertIn("name: project-knowledge", content)
            self.assertIn("## Authority", content)
            self.assertIn("## Core development loop", content)
            self.assertIn("## Completion criteria", content)
            self.assertIn("knowledge spec verify", content)

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

    def test_mcp_read_rejects_workspace_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("SECRET=value", encoding="utf-8")
            with self.assertRaises(ValueError):
                handle(
                    {
                        "jsonrpc": "2.0",
                        "id": 4,
                        "method": "tools/call",
                        "params": {"name": "knowledge_read", "arguments": {"path": ".env"}},
                    },
                    root,
                )

    def test_mcp_read_rejects_symlinked_knowledge_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            knowledge = root / "knowledge"
            knowledge.mkdir()
            secret = root / "secret.txt"
            secret.write_text("SECRET=value", encoding="utf-8")
            link = knowledge / "secret.md"
            try:
                link.symlink_to(secret)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks are unavailable in this environment")
            with self.assertRaises(ValueError):
                handle(
                    {
                        "jsonrpc": "2.0",
                        "id": 5,
                        "method": "tools/call",
                        "params": {"name": "knowledge_read", "arguments": {"path": "knowledge/secret.md"}},
                    },
                    root,
                )


if __name__ == "__main__":
    unittest.main()
