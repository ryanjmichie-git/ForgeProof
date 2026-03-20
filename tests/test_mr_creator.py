"""Tests for MR creation helpers."""

from forgeproof.gitlab.mr_creator import (
    _build_issue_comment,
    _build_mr_description,
    create_branch_name,
    slugify,
)
from forgeproof.models import (
    EvalScorecard,
    FileChange,
    IssueInfo,
    RunState,
)


# -- slugify --

def test_slugify_basic():
    assert slugify("Hello World!") == "hello-world"


def test_slugify_empty():
    assert slugify("") == ""


def test_slugify_special_chars():
    assert slugify("Feature @#$ Test") == "feature-test"


def test_slugify_truncation():
    result = slugify("a" * 100)
    assert len(result) <= 50


def test_slugify_strips_hyphens():
    result = slugify("--leading--")
    assert not result.startswith("-")
    assert not result.endswith("-")


# -- create_branch_name --

def test_create_branch_name():
    name = create_branch_name(42, "Add CSV export")
    assert name.startswith("forgeproof/42-")
    assert "add-csv-export" in name


def test_create_branch_name_special_chars():
    name = create_branch_name(1, "Fix bug #123!")
    assert name.startswith("forgeproof/1-")


# -- _build_mr_description --

def _make_state(review_ready=True, coverage=100.0, gate_failures=None):
    state = RunState()
    state.issue = IssueInfo(issue_iid=2, issue_title="Test")
    state.file_changes = [FileChange(path="src/a.py", content="x", action="create")]
    state.evaluation = EvalScorecard(
        deterministic_pass=review_ready,
        requirements_coverage=coverage,
        review_ready=review_ready,
        gate_failures=gate_failures or [],
    )
    return state


def test_mr_description_passing():
    state = _make_state(review_ready=True)
    desc = _build_mr_description(state)
    assert "PASS" in desc
    assert "100%" in desc or "100" in desc
    assert state.run_id in desc


def test_mr_description_failing():
    state = _make_state(review_ready=False, coverage=50.0, gate_failures=["tests failed"])
    desc = _build_mr_description(state)
    assert "FAIL" in desc
    assert "tests failed" in desc


def test_mr_description_no_eval():
    state = RunState()
    state.issue = IssueInfo(issue_iid=1)
    state.evaluation = None
    desc = _build_mr_description(state)
    assert "N/A" in desc


def test_mr_description_contains_file_list():
    state = _make_state()
    desc = _build_mr_description(state)
    assert "src/a.py" in desc


# -- _build_issue_comment --

def test_issue_comment_with_mr():
    state = _make_state()
    comment = _build_issue_comment(state, "https://gitlab.com/mr/1")
    assert "https://gitlab.com/mr/1" in comment
    assert state.run_id in comment


def test_issue_comment_no_mr():
    state = _make_state()
    comment = _build_issue_comment(state, "")
    assert "_(not created)_" in comment


def test_issue_comment_review_ready():
    state = _make_state(review_ready=True)
    comment = _build_issue_comment(state, "")
    assert "True" in comment


def test_issue_comment_not_ready():
    state = _make_state(review_ready=False, gate_failures=["lint failed"])
    comment = _build_issue_comment(state, "")
    assert "False" in comment
    assert "lint failed" in comment


def test_issue_comment_file_count():
    state = _make_state()
    comment = _build_issue_comment(state, "")
    assert "1" in comment  # 1 file
