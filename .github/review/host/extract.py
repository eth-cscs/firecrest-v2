#!/usr/bin/env python3
"""Extract the final assistant message from native OpenCode v2 JSONL output."""

import argparse
import json
from pathlib import Path


EVENT_TYPES = {"review_phase", "step_start", "step_finish", "tool_use", "text", "reasoning", "error"}
_INCOMPLETE_NOTICE = (
    "> Inspection was interrupted. Findings cover only the code inspected; "
    "this is not a clean bill of health for the remaining changes."
)


def extract_review(lines):
    phase = "initial"
    session = None
    message = None
    parts = {}
    finish_reason = None
    incomplete = False
    transitions = {
        ("initial", "inspection", "start"): "inspection",
        ("inspection", "inspection", "end"): "inspected",
        ("inspected", "final", "start"): "final",
        ("final", "final", "end"): "complete",
    }
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid OpenCode JSON on line {line_number}") from error
        if (not isinstance(event, dict) or not isinstance(event.get("type"), str)
                or event["type"] not in EVENT_TYPES):
            raise ValueError(f"unsupported OpenCode event on line {line_number}")
        kind = event["type"]
        if kind == "error":
            raise ValueError("OpenCode reported an error; refusing to publish a partial review")
        if kind == "review_phase":
            transition = (phase, event.get("phase"), event.get("state"))
            if not all(isinstance(value, str) for value in transition) or transition not in transitions:
                raise ValueError("invalid review phase transition")
            if phase != "initial" and (session is None or event.get("sessionID") != session):
                raise ValueError("review phase changed the inspection session")
            if "incomplete" in event:
                if transition != ("inspection", "inspection", "end") or type(event["incomplete"]) is not bool:
                    raise ValueError("invalid incomplete inspection marker")
                incomplete = event["incomplete"]
            phase = transitions[transition]
            continue
        if phase not in ("inspection", "final"):
            raise ValueError("OpenCode event outside an active review phase")
        part = event.get("part")
        if not isinstance(part, dict):
            raise ValueError(f"missing OpenCode event part on line {line_number}")
        event_session = event.get("sessionID")
        if not isinstance(event_session, str) or not event_session:
            raise ValueError("missing OpenCode session ID")
        if session is None:
            session = event_session
        if phase == "final" and kind == "tool_use":
            raise ValueError("final review phase attempted to use a tool")
        if phase == "final" and kind == "step_finish" and part.get("reason") not in ("stop", "end_turn"):
            raise ValueError("OpenCode stopped before completing the final review phase")
        if event_session != session:
            raise ValueError("OpenCode event changed the inspection session")
        # Inspection text is private evidence, never a publishable fallback.
        if phase == "inspection":
            continue
        message_id = part.get("messageID")
        if not isinstance(message_id, str) or not message_id:
            raise ValueError("missing OpenCode message ID")
        # Message IDs delimit responses when the CLI omits explicit step events.
        if kind == "step_start" or message_id != message:
            message = message_id
            parts = {}
            finish_reason = None
        if kind == "step_start":
            continue
        if kind == "step_finish":
            finish_reason = part.get("reason")
        elif kind == "text":
            part_id = part.get("id")
            text = part.get("text")
            end = part.get("time", {}).get("end") if isinstance(part.get("time"), dict) else None
            if not isinstance(part_id, str) or not isinstance(text, str):
                raise ValueError("malformed OpenCode text part")
            if type(end) not in (int, float) or end <= 0:
                raise ValueError("OpenCode text part is incomplete")
            parts[part_id] = text
    # Require the explicit final phase to finish, not merely an inspection summary.
    if phase != "complete" or finish_reason not in (None, "stop", "end_turn"):
        raise ValueError("OpenCode stopped before completing the final review phase")
    review = "\n\n".join(parts.values()).strip()
    if not review:
        raise ValueError("OpenCode produced no final review text")
    if incomplete:
        review = _INCOMPLETE_NOTICE + "\n\n" + review
    return review + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.events.resolve() == args.output.resolve():
            raise ValueError("review output must not overwrite the event stream")
        with args.events.open(encoding="utf-8") as events:
            review = extract_review(events)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(review, encoding="utf-8")
    except (OSError, ValueError) as error:
        parser.exit(1, f"review extraction: {error}\n")


if __name__ == "__main__":
    main()
