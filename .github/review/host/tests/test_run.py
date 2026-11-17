import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest


HELPER = Path(__file__).resolve().parents[1] / "run.py"


@pytest.fixture
def trusted_runner(tmp_path):
    root = tmp_path / "default-branch"
    root.mkdir()
    instructions = root / "AGENTS.md"
    instructions.write_text("trusted repository instructions\n")
    return HELPER, instructions


@pytest.fixture
def trusted_config(tmp_path):
    config = tmp_path / "trusted-config"
    config.mkdir()
    (config / "opencode.json").write_text("{}\n")
    (config / "limits.json").write_text(json.dumps({
        "inspection_seconds": 10, "finalization_seconds": 5,
        "execution_overhead_seconds": 13, "termination_grace_seconds": 1,
    }))
    return config


@pytest.fixture
def checkout(tmp_path):
    checkout = tmp_path / "pr-source"
    checkout.mkdir()
    (checkout / "app.py").write_text("important source\n")
    environment = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    for args in [
        ["init", "-b", "main"], ["add", "app.py"],
        ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
         "commit", "-m", "temporary fixture"],
    ]:
        subprocess.run(["git", "-C", str(checkout), *args], env=environment,
                       check=True, capture_output=True)
    return checkout


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.syspath_prepend(str(HELPER.parent))
    spec = importlib.util.spec_from_file_location("review_runner", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("target", ["checkout-alias", "context", "instructions-alias", "configuration"])
def test_runner_cannot_overwrite_inputs(tmp_path, trusted_runner, trusted_config, checkout, target):
    helper, instructions = trusted_runner
    source = checkout / "app.py"
    environment = dict(os.environ, CSCS_INFERENCE_API_KEY="local-path-safety-test")
    context = tmp_path / "context.md"
    context.write_text("important context\n")
    if target == "checkout-alias":
        alias = tmp_path / "looks-private"
        alias.symlink_to(checkout, target_is_directory=True)
        output = alias / "app.py"
    elif target == "context":
        output = context
    elif target == "configuration":
        output = trusted_config / "opencode.json"
    else:
        output = tmp_path / "instruction-alias"
        output.symlink_to(instructions)
    # /bin/false is a real failing executable, not a simulated container. If the
    # path guard regresses, opening stdout truncates the protected file before
    # that executable fails. No container or model credentials are needed.
    result = subprocess.run([
        sys.executable, str(helper), "--engine", "/bin/false", "--image", "unused",
        "--checkout", str(checkout), "--context", str(context), "--events", str(output),
        "--instructions", str(instructions), "--config", str(trusted_config),
    ], env=environment, text=True, capture_output=True)
    assert result.returncode == 1
    assert source.read_text() == "important source\n"
    assert context.read_text() == "important context\n"
    assert instructions.read_text() == "trusted repository instructions\n"
    assert (trusted_config / "opencode.json").read_text() == "{}\n"


@pytest.mark.parametrize("alias", [False, True])
def test_runner_rejects_pr_supplied_instructions(tmp_path, trusted_config, checkout, alias):
    instructions = checkout / "AGENTS.md"
    instructions.write_text("untrusted PR instructions\n")
    if alias:
        link = tmp_path / "looks-trusted"
        link.symlink_to(instructions)
        instructions = link
    context = tmp_path / "context.md"
    context.write_text("review input\n")
    output = tmp_path / "events.jsonl"
    environment = dict(os.environ, CSCS_INFERENCE_API_KEY="local-path-safety-test")
    # A successful real executable makes acceptance observable if the path guard regresses.
    result = subprocess.run([
        sys.executable, str(HELPER), "--engine", "/bin/true", "--image", "unused",
        "--checkout", str(checkout), "--context", str(context), "--events", str(output),
        "--instructions", str(instructions), "--config", str(trusted_config),
    ], env=environment, text=True, capture_output=True)
    assert result.returncode == 1
    assert not output.exists()
    assert instructions.read_text() == "untrusted PR instructions\n"


@pytest.mark.parametrize("changed_source", [False, True])
def test_cleanup_timeout_preserves_failure_and_checks_source(
        tmp_path, trusted_runner, trusted_config, checkout, runner, monkeypatch, capsys, changed_source):
    _, instructions = trusted_runner
    context = tmp_path / "context.md"
    context.write_text("review input\n")
    monkeypatch.setenv("CSCS_INFERENCE_API_KEY", "local-cleanup-test")
    real_run = subprocess.run

    def run(command, *args, **kwargs):
        if command[:2] == ["/bin/false", "rm"]:
            if changed_source:
                (checkout / "app.py").write_text("changed during cleanup\n")
            # Force the timeout without sleeping or requiring a container daemon.
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(runner.subprocess, "run", run)
    expected = "checkout" if changed_source else "exit 1"
    with pytest.raises(ValueError, match=expected):
        runner.run_review("/bin/false", "unused", checkout, context,
                          tmp_path / "events.jsonl", instructions, trusted_config)
    assert "container cleanup failed" in capsys.readouterr().err
    diagnostic = json.loads((tmp_path / "events.diagnostics.json").read_text())
    assert diagnostic["status"] == "failed"
    assert diagnostic["failure"] == ("checkout_changed" if changed_source else "reviewer_exit")
    assert diagnostic["cleanup"] == "failed"
    assert diagnostic["exit_code"] == 1


def test_progress_reports_silence_without_exposing_event_text(tmp_path, runner, capsys):
    private_event = b'{"type":"reasoning","text":"private reasoning and credential marker"}\n'
    with (tmp_path / "events.jsonl").open("w+b") as output:
        class Reports:
            count = 0

            def wait(self, interval):
                self.count += 1
                if self.count == 2:
                    os.write(output.fileno(), private_event)
                return self.count > 2

        # Drive a quiet tick and an output tick without waiting for wall-clock time.
        runner._report_progress(output, Reports(), runner.time.monotonic())
    progress = capsys.readouterr().out
    assert "0 bytes (+0)" in progress
    assert f"{len(private_event)} bytes (+{len(private_event)})" in progress
    assert "reasoning:1" in progress
    assert "private reasoning" not in progress
    assert "credential marker" not in progress


def test_progress_waits_for_complete_events_and_counts_them_once(tmp_path, runner, capsys):
    with (tmp_path / "events.jsonl").open("w+b") as output:
        class Reports:
            count = 0

            def wait(self, interval):
                self.count += 1
                if self.count == 1:
                    os.write(output.fileno(), b'{"type":"step_finish","part":{"reason":"length')
                elif self.count == 2:
                    os.write(output.fileno(), b'"}}\n')
                return self.count > 2

        runner._report_progress(output, Reports(), runner.time.monotonic())
    lines = capsys.readouterr().out.splitlines()
    assert "events=none" in lines[0]
    assert "step_finish:1" in lines[1] and "last_finish=length" in lines[1]
    assert "step_finish:1" in lines[2] and "step_finish:2" not in lines[2]
    assert "invalid" not in "\n".join(lines)


def test_progress_summarizes_final_errors_without_exposing_unknown_fields(tmp_path, runner, capsys):
    with (tmp_path / "events.jsonl").open("w+b") as output:
        os.write(output.fileno(),
                 b'{"type":"error","error":{"message":"private error marker"}}\n'
                 b'{"type":"private event marker"}\n'
                 b'{"type":"review_phase","phase":"private phase marker"}\n'
                 b'{"type":"step_finish","part":{"reason":"private finish marker"}}')
        stopped = runner.threading.Event()
        stopped.set()
        runner._report_progress(output, stopped, runner.time.monotonic())
    progress = capsys.readouterr().out
    assert "error:1" in progress and "unknown:1" in progress
    assert "step_finish:1" in progress and "last_finish=other" in progress
    assert "phase=other" in progress
    assert "private" not in progress


@pytest.mark.parametrize(("error", "status", "timeout"), [
    ({"type": "provider.transport", "status": 200,
      "message": "Timed out waiting for the response to complete"}, 200, "response_complete"),
    ({"type": "provider.transport",
      "message": "Timed out waiting for response headers"}, None, "response_headers"),
    ({"type": "provider.transport", "message": "Response chunk timeout"}, None, "response_chunk"),
    ({"type": "TimeoutError", "message": "Request failed"}, None, "unspecified"),
    ({"type": "provider.api", "status": 504}, 504, "http_status"),
    ({"type": "provider.api", "status": 413, "message": "Request too large"}, 413, "not_reported"),
    ({"type": "provider.api", "status": 503, "message": "Unavailable"}, 503, "not_reported"),
    ({"type": [], "status": True, "message": {}}, None, "not_reported"),
    (None, None, "not_reported"),
])
def test_error_diagnostics_distinguish_timeouts_and_http_failures(
        tmp_path, runner, capsys, error, status, timeout):
    diagnostic = {}
    with (tmp_path / "events.jsonl").open("w+b") as output:
        for event in [
            {"type": "review_phase", "phase": "inspection", "state": "start"},
            {"type": "error", "error": error},
        ]:
            os.write(output.fileno(), json.dumps(event).encode() + b"\n")
        stopped = runner.threading.Event()
        stopped.set()
        runner._report_progress(output, stopped, runner.time.monotonic(), diagnostic)
    detail, = diagnostic["errors"]
    assert detail["phase"] == "inspection"
    assert detail["http_status"] == status
    assert detail["timeout"] == timeout
    assert diagnostic["events"]["error"] == 1
    progress = capsys.readouterr().out
    assert "provider.transport" not in progress
    assert f"last_error_http_status={status or 'unknown'}" in progress
    assert f"last_error_timeout={timeout}" in progress


def test_error_artifact_redacts_credentials_before_truncation(
        tmp_path, runner, monkeypatch, capsys):
    secret = 'inference-key/"with spaces'
    monkeypatch.setenv("CSCS_INFERENCE_API_KEY", secret)
    marker = "UNRETAINED_RESPONSE_PAYLOAD"
    message = (
        f"{secret} {json.dumps(secret)[1:-1]} {runner.quote(secret, safe='')} "
        f"{runner.quote_plus(secret, safe='')} "
        'Authorization: Bearer unknown-bearer-value; {"apiKey": "unknown-api-value"} '
        "password='unknown password value'; https://user:unknown-url-value@example.invalid "
        "Bearer standalone-value\n"
    )
    diagnostic = {}
    with (tmp_path / "events.jsonl").open("w+b") as output:
        # A separate message places a secret across the output boundary.
        for text in (message, "x" * 1020 + secret + " trailing detail"):
            event = {"type": "error", "error": {
                "type": f"provider.{secret}", "message": text, "status": 500,
                "responseBody": marker, "headers": {"Authorization": marker},
            }}
            os.write(output.fileno(), json.dumps(event).encode() + b"\n")
        stopped = runner.threading.Event()
        stopped.set()
        runner._report_progress(output, stopped, runner.time.monotonic(), diagnostic)
    path = tmp_path / "events.diagnostics.json"
    runner._write_diagnostic(path, diagnostic)
    raw = path.read_text()
    detail, boundary = json.loads(raw)["errors"]
    assert detail["type"] == "provider.[REDACTED]"
    assert detail["message_truncated"] is False
    assert boundary["message_truncated"] is True
    assert len(boundary["message"]) == 1024
    assert "[REDACTED]" in detail["message"]
    for forbidden in (secret, "inference-key", "unknown-bearer-value", "unknown-api-value",
                      "unknown password value", "unknown-url-value", "standalone-value", marker):
        assert forbidden not in raw
    assert path.stat().st_mode & 0o777 == 0o600
    progress = capsys.readouterr().out
    assert "provider." not in progress and "REDACTED" not in progress


def test_error_diagnostics_keep_recent_failures_with_bounded_storage(tmp_path, runner):
    diagnostic = {}
    with (tmp_path / "events.jsonl").open("w+b") as output:
        for status in range(500, 510):
            event = {"type": "error", "error": {"type": "provider.api", "status": status}}
            os.write(output.fileno(), json.dumps(event).encode() + b"\n")
        stopped = runner.threading.Event()
        stopped.set()
        runner._report_progress(output, stopped, runner.time.monotonic(), diagnostic)
    assert diagnostic["events"]["error"] == 10
    assert [detail["http_status"] for detail in diagnostic["errors"]] == list(range(502, 510))



@pytest.mark.parametrize(("tool", "state", "result"), [
    ("read", {"status": "completed"}, "read/completed"),
    ("read", {"status": "error"}, "read/error"),
    ("execute", {"status": "completed", "metadata": {"metadata": {"error": True}}}, "execute/error"),
    ("shell", {"status": "completed", "metadata": {"metadata": {"exit": 128}}}, "shell/error"),
    ("shell", {"status": "completed", "metadata": {"metadata": {"exit": 0}}}, "shell/completed"),
    ("private tool marker", {"status": "private status marker"}, "other/other"),
])
def test_progress_classifies_tool_results_without_exposing_payload(
        tmp_path, runner, capsys, tool, state, result):
    state = dict(state, input={"command": "private command marker"},
                 output="private output marker", error="private error marker")
    event = {"type": "tool_use", "part": {"tool": tool, "state": state}}
    with (tmp_path / "events.jsonl").open("w+b") as output:
        os.write(output.fileno(), json.dumps(event).encode() + b"\n")
        stopped = runner.threading.Event()
        stopped.set()
        runner._report_progress(output, stopped, runner.time.monotonic())
    progress = capsys.readouterr().out
    assert f"tools={result}:1" in progress
    assert "private" not in progress


@pytest.mark.parametrize("exit_code", [0, 7])
def test_runner_retains_private_events_and_sanitized_diagnostics(
        tmp_path, trusted_runner, trusted_config, checkout, runner, monkeypatch, capfd, exit_code):
    _, instructions = trusted_runner
    context = tmp_path / "context.md"
    context.write_text("private context marker\n")
    engine = tmp_path / "engine"
    cleanup = tmp_path / "cleanup"
    engine.write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, sys\n"
        "if sys.argv[1] == 'rm':\n"
        f"    pathlib.Path({str(cleanup)!r}).touch()\n"
        "    sys.exit(0)\n"
        "print(json.dumps({'type': 'reasoning', 'text': 'private model marker'}))\n"
        "print(json.dumps({'type': 'private event marker'}))\n"
        "print('private stderr credential marker', file=sys.stderr)\n"
        f"sys.exit({exit_code})\n"
    )
    engine.chmod(0o700)
    monkeypatch.setenv("CSCS_INFERENCE_API_KEY", "private credential marker")
    events = tmp_path / "events.jsonl"
    if exit_code:
        with pytest.raises(ValueError, match=f"exit {exit_code}"):
            runner.run_review(str(engine), "unused", checkout, context, events, instructions, trusted_config)
    else:
        runner.run_review(str(engine), "unused", checkout, context, events, instructions, trusted_config)
    diagnostic_path = tmp_path / "events.diagnostics.json"
    raw = diagnostic_path.read_text()
    diagnostic = json.loads(raw)
    assert diagnostic["status"] == ("failed" if exit_code else "success")
    assert diagnostic["failure"] == ("reviewer_exit" if exit_code else "none")
    assert diagnostic["exit_code"] == exit_code
    assert diagnostic["events"] == {"reasoning": 1, "unknown": 1}
    assert diagnostic["summary_complete"] is True
    assert diagnostic["elapsed_seconds"] >= 0
    assert diagnostic["cleanup"] == ("completed" if exit_code else "not_needed")
    assert cleanup.exists() == bool(exit_code)
    assert diagnostic_path.stat().st_mode & 0o777 == 0o600
    assert "private model marker" in events.read_text()
    stderr_path = tmp_path / "events.stderr.log"
    assert "private stderr credential marker" in stderr_path.read_text()
    assert stderr_path.stat().st_mode & 0o777 == 0o600
    captured = capfd.readouterr()
    assert "private" not in raw + captured.out + captured.err


def test_hanging_reviewer_is_killed_and_container_cleanup_is_bounded(
        tmp_path, trusted_runner, trusted_config, checkout, runner, monkeypatch):
    _, instructions = trusted_runner
    context = tmp_path / "context.md"
    context.write_text("review input\n")
    engine = tmp_path / "engine"
    cleanup = tmp_path / "cleanup"
    engine.write_text(
        f"#!{sys.executable}\n"
        "import pathlib, signal, sys, time\n"
        "if sys.argv[1] == 'rm':\n"
        f"    pathlib.Path({str(cleanup)!r}).touch()\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "while True:\n"
        "    time.sleep(60)\n"
    )
    engine.chmod(0o700)
    monkeypatch.setenv("CSCS_INFERENCE_API_KEY", "local-deadline-test")
    (trusted_config / "limits.json").write_text(json.dumps({
        "inspection_seconds": 0.1, "finalization_seconds": 0.1,
        "execution_overhead_seconds": 0.1, "termination_grace_seconds": 0.1,
    }))
    monkeypatch.setattr(runner, "_CLEANUP_TIMEOUT", 0.5)
    started = time.monotonic()
    with pytest.raises(ValueError, match="hard deadline"):
        runner.run_review(str(engine), "unused", checkout, context,
                          tmp_path / "events.jsonl", instructions, trusted_config)
    assert time.monotonic() - started < 5
    diagnostic = json.loads((tmp_path / "events.diagnostics.json").read_text())
    assert diagnostic["status"] == "failed"
    assert diagnostic["failure"] == "timeout"
    assert diagnostic["exit_code"] == -signal.SIGKILL
    assert diagnostic["process_cleanup"] == "completed"
    assert diagnostic["cleanup"] == "failed"
    assert cleanup.exists()
    assert (checkout / "app.py").read_text() == "important source\n"


@pytest.mark.parametrize("suffix", ["diagnostics.json", "stderr.log"])
def test_private_outputs_cannot_overwrite_inputs(
        tmp_path, trusted_runner, trusted_config, checkout, runner, monkeypatch, suffix):
    _, instructions = trusted_runner
    context = tmp_path / "context.md"
    context.write_text("review input\n")
    (tmp_path / f"events.{suffix}").symlink_to(context)
    monkeypatch.setenv("CSCS_INFERENCE_API_KEY", "local-path-safety-test")
    with pytest.raises(ValueError, match=suffix.split(".")[0]):
        runner.run_review("/bin/true", "unused", checkout, context,
                          tmp_path / "events.jsonl", instructions, trusted_config)
    assert context.read_text() == "review input\n"
    assert not (tmp_path / "events.jsonl").exists()


@pytest.mark.parametrize("target", ["directory", "opencode.json", "limits.json"])
def test_runner_rejects_pr_configuration_symlinks(
        tmp_path, trusted_runner, trusted_config, checkout, runner, target):
    _, instructions = trusted_runner
    context = tmp_path / "context.md"
    context.write_text("review input\n")
    if target == "directory":
        alias = tmp_path / "config-alias"
        alias.symlink_to(checkout, target_is_directory=True)
        config = alias
    else:
        source = checkout / target
        source.write_bytes((trusted_config / target).read_bytes())
        (trusted_config / target).unlink()
        (trusted_config / target).symlink_to(source)
        config = trusted_config
    output = tmp_path / "events.jsonl"
    with pytest.raises(ValueError, match="trusted configuration"):
        runner.run_review("/bin/true", "unused", checkout, context, output, instructions, config)
    assert not output.exists()


@pytest.mark.parametrize("changes", [
    {"inspection_seconds": 0},
    {"finalization_seconds": True},
    {"termination_grace_seconds": float("inf")},
    {"execution_seconds": 17},
])
def test_invalid_limits_fail_before_launch(
        tmp_path, trusted_runner, trusted_config, checkout, runner, changes):
    _, instructions = trusted_runner
    context = tmp_path / "context.md"
    context.write_text("review input\n")
    path = trusted_config / "limits.json"
    limits = json.loads(path.read_text())
    path.write_text(json.dumps(limits | changes))
    output = tmp_path / "events.jsonl"
    with pytest.raises(ValueError, match="limits.json"):
        runner.run_review("/bin/true", "unused", checkout, context, output, instructions, trusted_config)
    assert not output.exists()


