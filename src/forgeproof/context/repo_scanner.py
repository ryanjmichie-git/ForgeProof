"""Scan repository tree and collect context for the AI agent."""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

# Files to always include when found
PRIORITY_FILES = [
    "AGENTS.md",
    ".forgeproof.yml",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
]

# Directories to skip when building the tree
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", "egg-info", ".eggs",
}

MAX_FILE_SIZE = 100_000  # bytes — skip files larger than this for context


def scan_repo_tree(root: Path, max_depth: int = 4) -> list[str]:
    """Return a list of relative file paths in the repo (up to max_depth)."""
    paths: list[str] = []
    _walk(root, root, 0, max_depth, paths)
    paths.sort()
    return paths


def read_agents_md(root: Path) -> str:
    """Read AGENTS.md if it exists."""
    p = root / "AGENTS.md"
    if p.is_file():
        return p.read_text(encoding="utf-8", errors="replace")
    return ""


def read_priority_files(root: Path) -> dict[str, str]:
    """Read priority files that exist in the repo root."""
    result: dict[str, str] = {}
    for name in PRIORITY_FILES:
        p = root / name
        if p.is_file() and p.stat().st_size <= MAX_FILE_SIZE:
            result[name] = p.read_text(encoding="utf-8", errors="replace")
    return result


def read_files(root: Path, paths: list[str]) -> dict[str, str]:
    """Read specific files relative to repo root. Skip binary / too-large files."""
    result: dict[str, str] = {}
    for rel in paths:
        p = root / rel
        if not p.is_file():
            log.warning("File not found: %s", rel)
            continue
        if p.stat().st_size > MAX_FILE_SIZE:
            log.info("Skipping large file: %s", rel)
            continue
        try:
            result[rel] = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            log.warning("Could not read file: %s", rel, exc_info=True)
    return result


def select_relevant_files(
    tree: list[str],
    plan_files: list[str] | None = None,
    extensions: set[str] | None = None,
) -> list[str]:
    """Filter the tree to files likely relevant for the task."""
    exts = extensions or {".py", ".md", ".yml", ".yaml", ".toml", ".json", ".txt"}
    selected: list[str] = []

    # Always include plan-specified files
    if plan_files:
        selected.extend(f for f in plan_files if f in tree)

    # Add source/test files with matching extensions
    for p in tree:
        if p in selected:
            continue
        suffix = Path(p).suffix.lower()
        if suffix in exts:
            selected.append(p)

    return selected


# ---------------------------------------------------------------------------

def _walk(base: Path, current: Path, depth: int, max_depth: int, out: list[str]) -> None:
    if depth > max_depth:
        return
    try:
        entries = sorted(current.iterdir())
    except PermissionError:
        return
    for entry in entries:
        if entry.name.startswith(".") and entry.name not in (".forgeproof.yml",):
            if entry.is_dir():
                continue
        if entry.is_dir():
            if entry.name in SKIP_DIRS:
                continue
            _walk(base, entry, depth + 1, max_depth, out)
        elif entry.is_file():
            try:
                out.append(str(entry.relative_to(base)).replace("\\", "/"))
            except ValueError:
                pass
