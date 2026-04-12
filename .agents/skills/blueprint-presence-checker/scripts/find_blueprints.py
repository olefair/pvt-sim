#!/usr/bin/env python3
"""Search the docs vault for blueprint notes that likely match a proposed implementation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "be",
    "by",
    "do",
    "for",
    "from",
    "has",
    "have",
    "how",
    "if",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "the",
    "this",
    "to",
    "we",
    "with",
}

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
TITLE_RE = re.compile(r"^#\s+(?:Blueprint:\s+)?(.+?)\s*$", re.MULTILINE)
SECTION_RE = re.compile(
    r"^##\s+(Objective|Scope|Implementation Plan|Validation / Acceptance Criteria)\s*$",
    re.MULTILINE,
)


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _tokenize(text: str) -> list[str]:
    tokens = [token for token in _normalize(text).split() if token and token not in STOPWORDS]
    return tokens


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _parse_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    frontmatter = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith((" ", "\t")) or stripped.startswith("- "):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        frontmatter[key.strip().lower()] = value.strip().strip('"').strip("'")
    return frontmatter


def _extract_title(text: str, fallback: str) -> str:
    match = TITLE_RE.search(text)
    if match:
        return match.group(1).strip()
    return fallback


def _extract_summary(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    summary_lines: list[str] = []
    capture = False
    for line in lines:
        if SECTION_RE.match(line):
            capture = True
            continue
        if capture and line.startswith("## "):
            break
        if capture and line:
            summary_lines.append(line)
        if len(" ".join(summary_lines)) >= 200:
            break
    if summary_lines:
        return " ".join(summary_lines)[:220]

    for line in lines:
        if line and not line.startswith("---") and not line.startswith("#"):
            return line[:220]
    return ""


def _resolve_vault_root(vault: str | None, config: str | None) -> Path:
    if vault:
        root = Path(vault).expanduser().resolve()
    elif config:
        config_path = Path(config).expanduser().resolve()
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        root = _parse_root_from_config(_read_text(config_path))
    else:
        raise ValueError("Provide either --vault or --config.")

    if not root.exists():
        raise FileNotFoundError(f"Vault root not found: {root}")
    return root


def _parse_root_from_config(text: str) -> Path:
    match = re.search(r"^\s*root_directory:\s*(.+?)\s*$", text, re.MULTILINE)
    if not match:
        raise ValueError("Could not find vault.root_directory in config.")
    value = match.group(1).strip().strip('"').strip("'")
    return Path(value).expanduser().resolve()


@dataclass
class Match:
    path: str
    absolute_path: str
    title: str
    summary: str
    frontmatter: dict[str, str]
    score: int
    reasons: list[str]
    layout: str
    archived: bool


def _layout_for(path: Path) -> str:
    parts = [part.lower() for part in path.parts]
    if "_archive" in parts:
        return "archive"
    if len(parts) >= 3:
        return "implementer-project"
    if len(parts) >= 2:
        return "project-folder"
    return "root"


def _score_path(
    relative_path: Path,
    text: str,
    query: str,
    query_tokens: list[str],
    project: str | None,
    implementer: str | None,
    repo: str | None,
) -> Match | None:
    frontmatter = _parse_frontmatter(text)
    title = _extract_title(text, relative_path.stem)
    summary = _extract_summary(text)
    layout = _layout_for(relative_path)
    archived = "_archive" in {part.lower() for part in relative_path.parts}

    normalized_text = _normalize(text)
    normalized_title = _normalize(title)
    normalized_path = _normalize(str(relative_path))
    stem_tokens = set(_tokenize(relative_path.stem))
    title_tokens = set(_tokenize(title))
    path_tokens = set(_tokenize(str(relative_path)))
    text_tokens = set(_tokenize(text))

    score = 0
    query_score = 0
    reasons: list[str] = []

    query_phrase = _normalize(query)
    phrase_hit = False
    if query_phrase:
        if query_phrase in normalized_title:
            score += 25
            query_score += 25
            phrase_hit = True
            reasons.append("full query appears in title")
        elif query_phrase in normalized_path:
            score += 22
            query_score += 22
            phrase_hit = True
            reasons.append("full query appears in path")
        elif query_phrase in normalized_text:
            score += 15
            query_score += 15
            phrase_hit = True
            reasons.append("full query appears in note body")

    visible_hits = 0
    body_hits = 0
    for token in query_tokens:
        if token in stem_tokens:
            score += 10
            query_score += 10
            visible_hits += 1
            reasons.append(f"filename token '{token}'")
        elif token in title_tokens:
            score += 9
            query_score += 9
            visible_hits += 1
            reasons.append(f"title token '{token}'")
        elif token in path_tokens:
            score += 7
            query_score += 7
            visible_hits += 1
            reasons.append(f"path token '{token}'")
        elif token in text_tokens:
            score += 3
            query_score += 3
            body_hits += 1
            reasons.append(f"body token '{token}'")

    if project:
        project_slug = _slugify(project)
        project_value = _slugify(frontmatter.get("project", ""))
        if project_slug and project_slug == project_value:
            score += 14
            reasons.append("frontmatter project match")
        elif project_slug and project_slug in normalized_path:
            score += 10
            reasons.append("path project match")

    if implementer:
        implementer_slug = _slugify(implementer)
        implementer_value = _slugify(frontmatter.get("implementer", ""))
        if implementer_slug and implementer_slug == implementer_value:
            score += 10
            reasons.append("frontmatter implementer match")
        elif implementer_slug and implementer_slug in normalized_path:
            score += 8
            reasons.append("path implementer match")

    if repo:
        repo_slug = _slugify(repo)
        repo_value = _slugify(frontmatter.get("repo", ""))
        target_value = _slugify(frontmatter.get("target", ""))
        if repo_slug and repo_slug == repo_value:
            score += 14
            reasons.append("frontmatter repo match")
        elif repo_slug and (repo_slug in target_value or repo_slug in normalized_text):
            score += 7
            reasons.append("repo mention in target/body")

    status = frontmatter.get("status", "").lower()
    if status in {"archived", "superseded"}:
        score -= 18
        reasons.append(f"status={status}")
    if archived:
        score -= 25
        reasons.append("archived path")

    if layout == "implementer-project":
        score += 4
    elif layout == "project-folder":
        score += 2

    if visible_hits == 0 and body_hits < 2 and score < 20:
        return None
    required_visible_hits = 1 if len(query_tokens) <= 1 else 2
    if not phrase_hit and visible_hits < required_visible_hits and query_score < 18:
        return None
    if score < 12:
        return None

    return Match(
        path=relative_path.as_posix(),
        absolute_path="",
        title=title,
        summary=summary,
        frontmatter=frontmatter,
        score=score,
        reasons=_dedupe(reasons),
        layout=layout,
        archived=archived,
    )


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _iter_markdown_files(search_root: Path) -> Iterable[Path]:
    for path in search_root.rglob("*.md"):
        if path.is_file():
            yield path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", help="Vault root directory (the docs root).")
    parser.add_argument("--config", help="Path to obsidian_vault_config.yaml.")
    parser.add_argument("--query", required=True, help="Implementation request or blueprint title to search for.")
    parser.add_argument("--project", help="Optional project filter, such as pete or workspace.")
    parser.add_argument("--implementer", help="Optional implementer filter, such as codex or cowork.")
    parser.add_argument("--repo", help="Optional repo filter, such as pete-workspace or pete.")
    parser.add_argument("--limit", type=int, default=8, help="Maximum number of matches to print.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args()

    try:
        vault_root = _resolve_vault_root(args.vault, args.config)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    search_root = vault_root / "blueprints"
    if not search_root.exists():
        print(f"Blueprints directory not found: {search_root}", file=sys.stderr)
        return 2

    query_tokens = _tokenize(args.query)
    matches: list[Match] = []
    file_count = 0
    for path in _iter_markdown_files(search_root):
        file_count += 1
        text = _read_text(path)
        match = _score_path(
            path.relative_to(vault_root),
            text,
            args.query,
            query_tokens,
            args.project,
            args.implementer,
            args.repo,
        )
        if match is None:
            continue
        match.absolute_path = str(path.resolve())
        matches.append(match)

    matches.sort(key=lambda item: (-item.score, item.archived, item.path.lower()))
    matches = matches[: max(args.limit, 1)]

    payload = {
        "vault_root": str(vault_root),
        "search_root": str(search_root),
        "query": args.query,
        "filters": {
            "project": args.project,
            "implementer": args.implementer,
            "repo": args.repo,
        },
        "searched_files": file_count,
        "match_count": len(matches),
        "matches": [
            {
                "path": match.path,
                "absolute_path": match.absolute_path,
                "title": match.title,
                "summary": match.summary,
                "frontmatter": match.frontmatter,
                "score": match.score,
                "reasons": match.reasons,
                "layout": match.layout,
                "archived": match.archived,
            }
            for match in matches
        ],
    }

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"vault_root={payload['vault_root']}")
    print(f"search_root={payload['search_root']}")
    print(f"searched_files={payload['searched_files']}")
    print(f"match_count={payload['match_count']}")
    for index, match in enumerate(matches, start=1):
        print("")
        print(f"[{index}] score={match.score} path={match.path}")
        print(f"    title={match.title}")
        if match.frontmatter:
            fields = []
            for key in ("project", "implementer", "repo", "target", "status"):
                value = match.frontmatter.get(key)
                if value:
                    fields.append(f"{key}={value}")
            if fields:
                print(f"    frontmatter={' ; '.join(fields)}")
        if match.summary:
            print(f"    summary={match.summary}")
        if match.reasons:
            print(f"    reasons={'; '.join(match.reasons[:6])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
