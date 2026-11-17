import importlib.util
import json
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("review_extract", Path(__file__).resolve().parents[1] / "extract.py")
extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract)


def event(kind, message="final", session="parent", **part):
    return json.dumps({"type": kind, "sessionID": session,
                       "part": {"messageID": message, **part}})


def text(value, message="final", session="parent", part_id="text", **changes):
    return event("text", message, session, id=part_id, text=value, time={"end": 1}, **changes)


def phase(name, state, session="parent"):
    return json.dumps({"type": "review_phase", "phase": name, "state": state, "sessionID": session})


def inspection():
    return [phase("inspection", "start"), text("Private inspection notes", "inspection"),
            event("tool_use", "inspection"), phase("inspection", "end")]


def review(final):
    return [*inspection(), phase("final", "start"), *final, phase("final", "end")]


def test_only_explicit_final_parent_response_is_published():
    lines = review([
        event("step_start"),
        event("reasoning", text="Private reasoning"),
        text("## Findings", part_id="heading"),
        text("- P1: incorrect boundary."),
    ])
    assert extract.extract_review(lines) == "## Findings\n\n- P1: incorrect boundary.\n"


@pytest.mark.parametrize("position", [2, 5])
def test_foreign_session_in_either_phase_is_rejected(position):
    lines = review([text("Otherwise complete review")])
    lines.insert(position, text("Unexpected session", session="other"))
    with pytest.raises(ValueError, match="session"):
        extract.extract_review(lines)


def test_native_final_response_without_step_events_is_accepted():
    assert extract.extract_review(review([text("No actionable findings.")])) == "No actionable findings.\n"


def test_updated_text_part_is_not_duplicated():
    assert extract.extract_review(review([
        event("step_start"), text("Partial"), text("Complete review"),
    ])) == "Complete review\n"


@pytest.mark.parametrize("lines", [
    inspection(),
    [*inspection(), phase("final", "start"), text("Looks complete but was interrupted")],
    [phase("inspection", "start"), text("An inspection review"), phase("final", "start")],
    [*inspection(), phase("final", "start", "different-session"), text("Wrong session")],
    review([text("A final review")]) + [text("Unexpected extra output")],
    [json.dumps({"type": "review_phase", "phase": [], "state": "start"})],
    # An unmarked old-style stream must never bypass explicit finalization.
    [event("step_start"), text("Inspection masquerading as a final review")],
])
def test_missing_reordered_or_mismatched_phases_are_rejected(lines):
    with pytest.raises(ValueError):
        extract.extract_review(lines)


@pytest.mark.parametrize("suffix", [
    [event("tool_use"), text("A later response must not hide the tool attempt", "later")],
    [event("step_finish", reason="length")],
    [event("step_start", "unfinished")],
    [json.dumps({"type": "error", "error": {"message": "provider failed"}})],
])
def test_partial_or_tool_using_final_responses_are_not_published(suffix):
    with pytest.raises(ValueError):
        extract.extract_review(review([event("step_start"), text("Intermediate text"), *suffix]))


def test_inspection_error_cannot_be_hidden_by_a_final_response():
    lines = review([text("An otherwise complete review")])
    lines.insert(2, json.dumps({"type": "error"}))
    with pytest.raises(ValueError):
        extract.extract_review(lines)


@pytest.mark.parametrize("final", [
    [],
    [text("  ")],
    ["not JSON"],
    ["[]"],
    [json.dumps({"type": "unexpected"})],
    [json.dumps({"type": []})],
    [event("text", id="part", text="Incomplete", time={"start": 1})],
])
def test_empty_corrupt_and_incomplete_final_output_is_rejected(final):
    with pytest.raises(ValueError):
        extract.extract_review(review(final))


def test_failed_extraction_preserves_existing_output(tmp_path):
    events = tmp_path / "events.jsonl"
    events.write_text("\n".join(inspection()) + "\n")
    output = tmp_path / "review.md"
    output.write_text("existing review\n")
    with pytest.raises(SystemExit) as error:
        extract.main(["--events", str(events), "--output", str(output)])
    assert error.value.code == 1
    assert output.read_text() == "existing review\n"


def test_cli_cannot_overwrite_event_stream(tmp_path):
    events = tmp_path / "events.jsonl"
    original = "\n".join(review([text("A review")])) + "\n"
    events.write_text(original)
    alias = tmp_path / "alias"
    alias.symlink_to(events)
    with pytest.raises(SystemExit) as error:
        extract.main(["--events", str(events), "--output", str(alias)])
    assert error.value.code == 1
    assert events.read_text() == original


def incomplete_review(final):
    lines = review(final)
    marker = json.loads(lines[3])
    marker["incomplete"] = True
    lines[3] = json.dumps(marker)
    return lines


def test_interrupted_inspection_qualifies_completed_final_review():
    result = extract.extract_review(incomplete_review([text("## Findings\n\n- Boundary bug.")]))
    assert result == (
        "> Inspection was interrupted. Findings cover only the code inspected; "
        "this is not a clean bill of health for the remaining changes.\n\n"
        "## Findings\n\n- Boundary bug.\n"
    )
    assert "Private inspection notes" not in result


@pytest.mark.parametrize("final", [
    [text("Truncated"), event("step_finish", reason="length")],
    [text("Truncated"), event("step_finish", reason="length"), text("Later text", message="later")],
    [text("Failure"), event("step_finish", reason="error"), text("Later text", message="later")],
    [text("Review"), event("tool_use", session="child-session")],
    [text("Review"), json.dumps({"type": "error", "error": {"message": "private failure"}})],
    [event("text", id="text", text="Partial", time={"start": 1})],
    [],
])
def test_incomplete_inspection_never_relaxes_final_validation(final):
    with pytest.raises(ValueError):
        extract.extract_review(incomplete_review(final))


def test_interrupted_inspection_with_unfinished_final_is_not_publishable():
    with pytest.raises(ValueError):
        extract.extract_review(incomplete_review([text("Looks finished")])[:-1])


@pytest.mark.parametrize(("marker_index", "value"), [
    (0, True), (3, "true"), (3, 1), (3, None), (4, True), (6, True),
])
def test_incomplete_marker_is_only_boolean_inspection_end(marker_index, value):
    lines = review([text("A review")])
    marker = json.loads(lines[marker_index])
    marker["incomplete"] = value
    lines[marker_index] = json.dumps(marker)
    with pytest.raises(ValueError, match="incomplete"):
        extract.extract_review(lines)


def test_false_incomplete_marker_does_not_qualify_complete_inspection():
    lines = incomplete_review([text("A review")])
    marker = json.loads(lines[3])
    marker["incomplete"] = False
    lines[3] = json.dumps(marker)
    assert extract.extract_review(lines) == "A review\n"


def test_incomplete_marker_cannot_hide_inspection_error():
    lines = incomplete_review([text("A review")])
    lines.insert(3, json.dumps({"type": "error"}))
    with pytest.raises(ValueError, match="reported an error"):
        extract.extract_review(lines)
