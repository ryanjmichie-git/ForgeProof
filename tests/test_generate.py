"""Tests for code generation parsing."""

import json

from forgeproof.phases.generate import (
    _extract_json_object,
    _parse_changes,
    _strip_code_fence,
)


# -- _parse_changes --

def test_parse_changes_valid():
    data = {
        "changes": [
            {"path": "src/main.py", "content": "print('hi')", "action": "create"},
            {"path": "tests/test.py", "content": "assert True", "action": "create"},
        ],
        "summary": "Generated 2 files",
    }
    changes = _parse_changes(json.dumps(data))
    assert len(changes) == 2
    assert changes[0].path == "src/main.py"
    assert changes[1].path == "tests/test.py"


def test_parse_changes_default_action():
    data = {"changes": [{"path": "a.py", "content": "x"}]}
    changes = _parse_changes(json.dumps(data))
    assert changes[0].action == "create"


def test_parse_changes_in_code_fence():
    data = {"changes": [{"path": "a.py", "content": "x"}]}
    text = f"```json\n{json.dumps(data)}\n```"
    changes = _parse_changes(text)
    assert len(changes) == 1


def test_parse_changes_missing_path():
    data = {"changes": [{"content": "x"}]}
    changes = _parse_changes(json.dumps(data))
    assert changes == []


def test_parse_changes_missing_content():
    data = {"changes": [{"path": "a.py"}]}
    changes = _parse_changes(json.dumps(data))
    assert changes == []


def test_parse_changes_empty_path():
    data = {"changes": [{"path": "", "content": "x"}]}
    changes = _parse_changes(json.dumps(data))
    assert changes == []


def test_parse_changes_garbage():
    changes = _parse_changes("not json at all")
    assert changes == []


def test_parse_changes_empty_changes():
    data = {"changes": []}
    changes = _parse_changes(json.dumps(data))
    assert changes == []


def test_parse_changes_with_prose():
    data = {"changes": [{"path": "a.py", "content": "x"}]}
    text = f"Here are the changes:\n{json.dumps(data)}\nDone."
    changes = _parse_changes(text)
    assert len(changes) == 1


# -- _strip_code_fence (duplicated from parse_plan) --

def test_strip_code_fence():
    assert _strip_code_fence('```json\n{"a":1}\n```') == '{"a":1}'
    assert _strip_code_fence('{"a":1}') == '{"a":1}'


# -- _extract_json_object --

def test_extract_json_object():
    assert _extract_json_object('text {"k": 1} more') == {"k": 1}
    assert _extract_json_object("no json") is None
