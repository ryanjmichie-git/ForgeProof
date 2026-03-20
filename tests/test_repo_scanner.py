"""Tests for repository scanning."""

from forgeproof.context.repo_scanner import (
    read_agents_md,
    read_files,
    read_priority_files,
    scan_repo_tree,
    select_relevant_files,
)


def _create_tree(tmp_path, files):
    """Helper to create a directory tree from a list of relative paths."""
    for f in files:
        p = tmp_path / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"content of {f}", encoding="utf-8")


# -- scan_repo_tree --

def test_scan_repo_tree_basic(tmp_path):
    _create_tree(tmp_path, ["src/main.py", "tests/test_main.py", "README.md"])
    tree = scan_repo_tree(tmp_path)
    assert "src/main.py" in tree
    assert "tests/test_main.py" in tree
    assert "README.md" in tree


def test_scan_repo_tree_skips_git(tmp_path):
    _create_tree(tmp_path, ["src/main.py", ".git/config", ".git/HEAD"])
    tree = scan_repo_tree(tmp_path)
    assert all(".git" not in p for p in tree)


def test_scan_repo_tree_skips_pycache(tmp_path):
    _create_tree(tmp_path, ["src/main.py", "__pycache__/foo.pyc"])
    tree = scan_repo_tree(tmp_path)
    assert all("__pycache__" not in p for p in tree)


def test_scan_repo_tree_skips_node_modules(tmp_path):
    _create_tree(tmp_path, ["index.js", "node_modules/pkg/index.js"])
    tree = scan_repo_tree(tmp_path)
    assert all("node_modules" not in p for p in tree)


def test_scan_repo_tree_max_depth(tmp_path):
    _create_tree(tmp_path, ["a/b/c/d/e/deep.py", "top.py"])
    tree = scan_repo_tree(tmp_path, max_depth=2)
    assert "top.py" in tree
    assert "a/b/c/d/e/deep.py" not in tree


def test_scan_repo_tree_forward_slashes(tmp_path):
    _create_tree(tmp_path, ["src/sub/file.py"])
    tree = scan_repo_tree(tmp_path)
    for p in tree:
        assert "\\" not in p, f"Backslash found in path: {p}"


def test_scan_repo_tree_sorted(tmp_path):
    _create_tree(tmp_path, ["z.py", "a.py", "m.py"])
    tree = scan_repo_tree(tmp_path)
    assert tree == sorted(tree)


# -- read_agents_md --

def test_read_agents_md_exists(tmp_path):
    (tmp_path / "AGENTS.md").write_text("# Agents\nRules here", encoding="utf-8")
    content = read_agents_md(tmp_path)
    assert "Rules here" in content


def test_read_agents_md_missing(tmp_path):
    assert read_agents_md(tmp_path) == ""


# -- read_priority_files --

def test_read_priority_files(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[build]", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("flask", encoding="utf-8")
    result = read_priority_files(tmp_path)
    assert "pyproject.toml" in result
    assert "requirements.txt" in result


def test_read_priority_files_skips_large(tmp_path):
    big = tmp_path / "pyproject.toml"
    big.write_text("x" * 200_000, encoding="utf-8")
    result = read_priority_files(tmp_path)
    assert "pyproject.toml" not in result


# -- read_files --

def test_read_files_basic(tmp_path):
    _create_tree(tmp_path, ["src/main.py"])
    result = read_files(tmp_path, ["src/main.py"])
    assert "src/main.py" in result


def test_read_files_missing(tmp_path):
    result = read_files(tmp_path, ["nonexistent.py"])
    assert result == {}


def test_read_files_skips_large(tmp_path):
    big = tmp_path / "huge.py"
    big.write_text("x" * 200_000, encoding="utf-8")
    result = read_files(tmp_path, ["huge.py"])
    assert "huge.py" not in result


# -- select_relevant_files --

def test_select_relevant_files_plan_first():
    tree = ["a.py", "b.py", "c.js", "plan_target.py"]
    selected = select_relevant_files(tree, plan_files=["plan_target.py"])
    assert selected[0] == "plan_target.py"


def test_select_relevant_files_by_extension():
    tree = ["code.py", "data.csv", "readme.md", "style.css"]
    selected = select_relevant_files(tree)
    assert "code.py" in selected
    assert "readme.md" in selected
    assert "data.csv" not in selected
    assert "style.css" not in selected


def test_select_relevant_files_no_duplicates():
    tree = ["a.py", "b.py"]
    selected = select_relevant_files(tree, plan_files=["a.py"])
    assert selected.count("a.py") == 1
