"""Tests for issue loading and parsing."""

import json

from forgeproof.context.issue_loader import (
    _extract_comments,
    _int,
    extract_acceptance_criteria,
    load_issue_from_file,
    load_issue_from_gitlab,
    load_issue_from_markdown,
    parse_issue_context,
    parse_trigger,
)


# -- parse_trigger --

def test_parse_trigger_strips_whitespace():
    t = parse_trigger("  @forgeproof run  ")
    assert t.raw_input == "@forgeproof run"
    assert t.type == "mention"


def test_parse_trigger_empty():
    t = parse_trigger("")
    assert t.raw_input == ""


# -- parse_issue_context --

def test_parse_issue_context_empty():
    info = parse_issue_context("")
    assert info.issue_iid == 0
    assert info.issue_title == ""


def test_parse_issue_context_invalid_json():
    info = parse_issue_context("{not valid json")
    assert info.issue_iid == 0


def test_parse_issue_context_flat():
    ctx = json.dumps({
        "project_id": 42,
        "iid": 7,
        "title": "Fix bug",
        "description": "It broke",
        "labels": ["bug"],
    })
    info = parse_issue_context(ctx)
    assert info.project_id == 42
    assert info.issue_iid == 7
    assert info.issue_title == "Fix bug"
    assert info.issue_body == "It broke"
    assert info.labels == ["bug"]


def test_parse_issue_context_nested_issue():
    ctx = json.dumps({"issue": {"iid": 3, "title": "Nested", "description": "body"}})
    info = parse_issue_context(ctx)
    assert info.issue_iid == 3
    assert info.issue_title == "Nested"


def test_parse_issue_context_nested_parent_object():
    ctx = json.dumps({"parent_object": {"iid": 5, "title": "Parent"}})
    info = parse_issue_context(ctx)
    assert info.issue_iid == 5
    assert info.issue_title == "Parent"


# -- load_issue_from_markdown --

def test_load_issue_from_markdown_with_title():
    info = load_issue_from_markdown("# My Issue\nSome body text")
    assert info.issue_title == "My Issue"
    assert "Some body text" in info.issue_body


def test_load_issue_from_markdown_no_title():
    info = load_issue_from_markdown("Just a body with no heading")
    assert info.issue_title == ""
    assert "Just a body" in info.issue_body


def test_load_issue_from_markdown_empty():
    info = load_issue_from_markdown("")
    assert info.issue_title == ""


# -- load_issue_from_gitlab --

def test_load_issue_from_gitlab():
    api_data = {
        "project_id": 100,
        "iid": 42,
        "title": "Add feature",
        "description": "Details here",
        "labels": ["enhancement"],
    }
    info = load_issue_from_gitlab(api_data)
    assert info.project_id == 100
    assert info.issue_iid == 42
    assert info.issue_title == "Add feature"
    assert info.comments == []


def test_load_issue_from_gitlab_missing_fields():
    info = load_issue_from_gitlab({})
    assert info.project_id == 0
    assert info.issue_title == ""


# -- load_issue_from_file --

def test_load_issue_from_file(tmp_path):
    f = tmp_path / "issue.json"
    f.write_text(json.dumps({
        "project_id": 1,
        "issue_iid": 2,
        "issue_title": "Test",
        "issue_body": "body",
    }), encoding="utf-8")
    info = load_issue_from_file(str(f))
    assert info.issue_iid == 2
    assert info.issue_title == "Test"


# -- extract_acceptance_criteria --

def test_extract_acceptance_criteria():
    body = (
        "## Description\nSome desc\n"
        "## Acceptance Criteria\n"
        "- Must work\n"
        "- Must be fast\n"
        "## Next Section\n"
    )
    criteria = extract_acceptance_criteria(body)
    assert criteria == ["Must work", "Must be fast"]


def test_extract_acceptance_criteria_with_checkboxes():
    body = "## Acceptance Criteria\n- [x] Done\n- [ ] Not done\n"
    criteria = extract_acceptance_criteria(body)
    assert "Done" in criteria
    assert "Not done" in criteria


def test_extract_acceptance_criteria_requirements_heading():
    body = "## Requirements\n- REQ A\n- REQ B\n"
    criteria = extract_acceptance_criteria(body)
    assert criteria == ["REQ A", "REQ B"]


def test_extract_acceptance_criteria_empty():
    assert extract_acceptance_criteria("No criteria here") == []


# -- helpers --

def test_int_none():
    assert _int(None) == 0


def test_int_string():
    assert _int("42") == 42


def test_int_invalid():
    assert _int("abc") == 0


def test_int_zero():
    assert _int(0) == 0


def test_extract_comments_dict_notes():
    data = {"notes": [{"body": "comment 1"}, {"body": "comment 2"}]}
    assert _extract_comments(data) == ["comment 1", "comment 2"]


def test_extract_comments_string_notes():
    data = {"notes": ["plain string"]}
    assert _extract_comments(data) == ["plain string"]


def test_extract_comments_empty():
    assert _extract_comments({}) == []
