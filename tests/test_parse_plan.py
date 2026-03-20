"""Tests for plan parsing from Claude responses."""

import json

from forgeproof.phases.parse_plan import (
    _extract_json_object,
    _parse_plan_response,
    _strip_code_fence,
)


# -- _strip_code_fence --

def test_strip_code_fence_json():
    text = '```json\n{"key": 1}\n```'
    assert _strip_code_fence(text) == '{"key": 1}'


def test_strip_code_fence_bare():
    text = '```\n{"key": 1}\n```'
    assert _strip_code_fence(text) == '{"key": 1}'


def test_strip_code_fence_no_fence():
    text = '{"key": 1}'
    assert _strip_code_fence(text) == '{"key": 1}'


def test_strip_code_fence_python():
    text = '```python\nprint("hi")\n```'
    assert _strip_code_fence(text) == 'print("hi")'


def test_strip_code_fence_no_closing():
    text = '```json\n{"key": 1}'
    result = _strip_code_fence(text)
    assert '{"key": 1}' in result


# -- _extract_json_object --

def test_extract_json_basic():
    result = _extract_json_object('Here is the plan: {"key": "val"} end.')
    assert result == {"key": "val"}


def test_extract_json_nested():
    obj = {"outer": {"inner": [1, 2, 3]}}
    result = _extract_json_object(f"prefix {json.dumps(obj)} suffix")
    assert result == obj


def test_extract_json_none():
    assert _extract_json_object("no json here") is None


def test_extract_json_invalid():
    assert _extract_json_object("prefix {broken json} suffix") is None


# -- _parse_plan_response --

def test_parse_plan_valid():
    data = {
        "requirements": [
            {"id": "REQ-1", "description": "Do X", "acceptance_criteria": "X works"}
        ],
        "steps": [
            {"step": 1, "action": "create", "file_path": "a.py", "description": "Create a"}
        ],
        "relevant_files": ["existing.py"],
        "risk_notes": ["Risk A"],
    }
    plan = _parse_plan_response(json.dumps(data))
    assert len(plan.requirements) == 1
    assert plan.requirements[0].id == "REQ-1"
    assert len(plan.steps) == 1
    assert plan.steps[0].file_path == "a.py"
    assert plan.relevant_files == ["existing.py"]
    assert plan.risk_notes == ["Risk A"]


def test_parse_plan_in_code_fence():
    data = {"requirements": [], "steps": []}
    text = f"```json\n{json.dumps(data)}\n```"
    plan = _parse_plan_response(text)
    assert plan.requirements == []
    assert plan.steps == []


def test_parse_plan_with_prose():
    data = {"requirements": [{"id": "R1", "description": "Test"}], "steps": []}
    text = f"Here is my plan:\n{json.dumps(data)}\nThat's the plan."
    plan = _parse_plan_response(text)
    assert len(plan.requirements) == 1


def test_parse_plan_garbage():
    plan = _parse_plan_response("totally garbage response")
    assert plan.requirements == []
    assert plan.steps == []


def test_parse_plan_malformed_requirements():
    data = {
        "requirements": [
            {"id": "REQ-1", "description": "Good"},
            {"bad": "missing id and description"},
        ],
        "steps": [],
    }
    plan = _parse_plan_response(json.dumps(data))
    assert len(plan.requirements) == 1
    assert plan.requirements[0].id == "REQ-1"


def test_parse_plan_empty_json():
    plan = _parse_plan_response("{}")
    assert plan.requirements == []
    assert plan.steps == []
