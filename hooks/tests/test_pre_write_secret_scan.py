"""Tests for hooks/pre_write_secret_scan.py."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from io import StringIO

import pytest

from hooks import pre_write_secret_scan


def _run(
    monkeypatch: pytest.MonkeyPatch,
    payload: Mapping[str, object],
) -> int:
    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps(payload)))
    return pre_write_secret_scan.main()


def _edit(file_path: str, content: str, tool: str = "Write") -> Mapping[str, object]:
    return {
        "tool_name": tool,
        "tool_input": {"file_path": file_path, "content": content},
    }


class TestForbiddenFilenames:
    @pytest.mark.parametrize(
        "name",
        [
            ".env",
            ".env.local",
            ".env.production",
            "credentials.json",
            "secrets.json",
            "server.pem",
            "deploy.key",
            "/nested/dir/.env",
            "C:/Projects/app/.env.prod",
        ],
    )
    def test_blocks(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        name: str,
    ) -> None:
        rc = _run(monkeypatch, _edit(name, "harmless"))
        captured = capsys.readouterr()
        assert rc == 2
        assert "forbidden filename" in captured.err

    def test_allows_safely_named_config(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        rc = _run(monkeypatch, _edit("config.json", '{"key": "value"}'))
        assert rc == 0


class TestSecretPatterns:
    @pytest.mark.parametrize(
        "content,expected_label",
        [
            ("AWS_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE", "AWS access key ID"),
            ("token: ghp_ABCDEFGHIJKLMNOPQRST1234", "GitHub token"),
            ("token: gho_aaaaaaaaaaaaaaaaaaaaaa", "GitHub token"),
            (
                "OPENAI_KEY=sk-proj1234567890abcdefghij1234567890ABCDEFGHIJ1234567890",
                "OpenAI API key",
            ),
            ("ANTHROPIC_API_KEY=sk-ant-api03-ABCDEFGHIJKLMNOPQR", "Anthropic API key"),
            ("-----BEGIN RSA PRIVATE KEY-----", "PEM private key header"),
            ("-----BEGIN OPENSSH PRIVATE KEY-----", "PEM private key header"),
        ],
    )
    def test_blocks(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        content: str,
        expected_label: str,
    ) -> None:
        rc = _run(monkeypatch, _edit("safe.py", content))
        captured = capsys.readouterr()
        assert rc == 2
        assert expected_label in captured.err

    def test_allows_fake_aws_in_comment_pattern_not_matching(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        rc = _run(monkeypatch, _edit("safe.py", "# AWS keys look like AKIA followed by 16 chars"))
        assert rc == 0

    def test_scans_new_string_and_old_string(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "file.py",
                "old_string": "TOKEN=old",
                "new_string": "TOKEN=ghp_ABCDEFGHIJKLMNOPQRST1234",
            },
        }
        assert _run(monkeypatch, payload) == 2

    def test_scans_multiedit_edits_array(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        payload = {
            "tool_name": "MultiEdit",
            "tool_input": {
                "file_path": "file.py",
                "edits": [
                    {"old_string": "a", "new_string": "b"},
                    {"old_string": "x", "new_string": "key=AKIAIOSFODNN7EXAMPLE"},
                ],
            },
        }
        assert _run(monkeypatch, payload) == 2


class TestNonEditTool:
    def test_read_tool_is_ignored(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": ".env"},
        }
        assert _run(monkeypatch, payload) == 0


class TestMalformedInput:
    def test_tool_input_not_a_dict(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        payload: dict[str, object] = {"tool_name": "Write", "tool_input": "not a dict"}
        assert _run(monkeypatch, payload) == 0

    def test_empty_payload(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        assert _run(monkeypatch, {}) == 0
