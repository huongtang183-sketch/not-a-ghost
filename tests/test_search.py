import json
import subprocess
from types import SimpleNamespace

import pytest

from ghost import search


def fake_runner(stdout="", stderr="", code=0, capture=None, raises=None):
    def run(cmd, **kwargs):
        if capture is not None:
            capture.update(cmd=cmd, **kwargs)
        if raises:
            raise raises
        return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=code)
    return run


def test_returns_the_result_text():
    out = json.dumps({"type": "result", "is_error": False, "result": "[1]"})
    assert search.run_claude("p", runner=fake_runner(out), exe="claude") == "[1]"


def test_command_allows_only_web_tools_and_sends_prompt_on_stdin():
    seen = {}
    out = json.dumps({"is_error": False, "result": "ok"})
    search.run_claude("my prompt", runner=fake_runner(out, capture=seen), exe="C:/x/claude.exe")
    cmd = seen["cmd"]
    assert cmd[0] == "C:/x/claude.exe" and "-p" in cmd
    assert cmd[cmd.index("--tools") + 1] == "WebSearch,WebFetch"
    assert cmd[cmd.index("--allowedTools") + 1] == "WebSearch,WebFetch"
    assert cmd[cmd.index("--output-format") + 1] == "json"
    assert "--no-session-persistence" in cmd
    assert seen["input"] == "my prompt"
    assert seen["encoding"] == "utf-8"


def test_error_result_raises_with_its_message():
    out = json.dumps({"is_error": True, "result": "Not logged in"})
    with pytest.raises(search.SearchError, match="Not logged in"):
        search.run_claude("p", runner=fake_runner(out), exe="claude")


def test_nonzero_exit_without_json_uses_stderr():
    with pytest.raises(search.SearchError, match="boom"):
        search.run_claude("p", runner=fake_runner("", "boom", code=1), exe="claude")


def test_plain_text_output_is_returned():
    assert search.run_claude("p", runner=fake_runner("[2]"), exe="claude") == "[2]"


def test_empty_answer_raises():
    with pytest.raises(search.SearchError):
        search.run_claude("p", runner=fake_runner(json.dumps({"is_error": False, "result": " "})), exe="claude")


def test_timeout_raises():
    runner = fake_runner(raises=subprocess.TimeoutExpired("claude", 1))
    with pytest.raises(search.SearchError, match="too long"):
        search.run_claude("p", runner=runner, exe="claude")


def test_missing_program_raises(monkeypatch):
    monkeypatch.setattr(search, "find_claude", lambda: None)
    with pytest.raises(search.SearchError, match="not installed"):
        search.run_claude("p")


def test_find_claude_prefers_path(monkeypatch):
    monkeypatch.setattr(search.shutil, "which", lambda name: "/usr/bin/claude")
    assert search.find_claude() == "/usr/bin/claude"


def test_find_claude_falls_back_to_the_installer_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(search.shutil, "which", lambda name: None)
    monkeypatch.setattr(search.Path, "home", lambda: tmp_path)
    assert search.find_claude() is None
    folder = tmp_path / ".local" / "bin"
    folder.mkdir(parents=True)
    exe = folder / ("claude.exe" if search.sys.platform == "win32" else "claude")
    exe.write_text("x")
    assert search.find_claude() == str(exe)


def test_photos_go_in_as_image_blocks_on_stdin():
    seen = {}
    out = "\n".join([json.dumps({"type": "system"}), json.dumps({"type": "result", "is_error": False, "result": "[2]"})])
    text = search.run_claude("describe it", runner=fake_runner(out, capture=seen), exe="claude", images=[("image/jpeg", "QUJD")])
    assert text == "[2]"
    cmd = seen["cmd"]
    assert cmd[cmd.index("--input-format") + 1] == "stream-json" and cmd[cmd.index("--output-format") + 1] == "stream-json"
    assert cmd[cmd.index("--tools") + 1] == "WebSearch,WebFetch"
    message = json.loads(seen["input"])
    blocks = message["message"]["content"]
    assert blocks[0] == {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "QUJD"}}
    assert blocks[-1] == {"type": "text", "text": "describe it"}


def test_photo_run_error_is_reported():
    out = json.dumps({"type": "result", "is_error": True, "result": "Not logged in"})
    with pytest.raises(search.SearchError, match="Not logged in"):
        search.run_claude("p", runner=fake_runner(out), exe="claude", images=[("image/png", "QQ==")])
