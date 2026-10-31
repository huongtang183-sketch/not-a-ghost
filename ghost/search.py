"""Web search through Claude Code, using the user's own Claude login (no API key).

Claude Code runs in the background with only its web tools switched on, so a page
it reads cannot make it run commands or touch files.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = "WebSearch,WebFetch"
TIMEOUT = 240


class SearchError(Exception):
    """Search could not run. The message is shown to the user."""


def find_claude():
    """Path to the claude program, or None."""
    found = shutil.which("claude")
    if found:
        return found
    name = "claude.exe" if sys.platform == "win32" else "claude"
    candidate = Path.home() / ".local" / "bin" / name
    return str(candidate) if candidate.exists() else None


def command(exe):
    return [exe, "-p", "--output-format", "json", "--model", "sonnet",
            "--tools", TOOLS, "--allowedTools", TOOLS, "--no-session-persistence"]


def run_claude(prompt, timeout=TIMEOUT, runner=subprocess.run, exe=None):
    """Send the prompt to Claude Code and return its text answer."""
    exe = exe or find_claude()
    if not exe:
        raise SearchError("Claude Code is not installed.")
    try:
        done = runner(command(exe), input=prompt, capture_output=True, text=True, encoding="utf-8",
                      timeout=timeout, cwd=tempfile.gettempdir())
    except subprocess.TimeoutExpired as error:
        raise SearchError("The search took too long.") from error
    except OSError as error:
        raise SearchError(f"Claude Code could not start: {error}") from error
    out = (done.stdout or "").strip()
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        if data.get("is_error") or done.returncode != 0:
            raise SearchError(str(data.get("result") or "Claude Code reported an error.")[:300])
        text = data.get("result")
        if isinstance(text, str) and text.strip():
            return text
        raise SearchError("Claude Code returned no answer.")
    if done.returncode != 0:
        raise SearchError((done.stderr or out or "Claude Code reported an error.").strip()[:300])
    if out:
        return out
    raise SearchError("Claude Code returned no answer.")
