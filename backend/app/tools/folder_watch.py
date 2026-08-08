#!/usr/bin/env python
"""Match a folder of files you already own against the catalog.

This reads filenames and modification times on a path you point it at. It never
downloads anything, never opens a media file, and never talks to a tracker. If a
filename looks like "Frieren - S01E07.mkv" and you watched it an hour ago, Kura
offers to move your progress to episode 7. You approve each one.

    python -m app.tools.folder_watch --path /media/anime --dry-run
    python -m app.tools.folder_watch --path /media/anime --apply --token "$KURA_TOKEN"
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

VIDEO_SUFFIXES = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".webm", ".ogm", ".wmv"}

EPISODE_PATTERNS = [
    re.compile(r"[sS](\d{1,2})[eE](\d{1,3})"),
    re.compile(r"\b[eE][pP]?[\s._-]?(\d{1,3})\b"),
    re.compile(r"[-_\s]\s?(\d{1,3})\s?[-_\s\[(]"),
]

NOISE = re.compile(
    r"\[[^\]]*\]|\([^)]*\)|\b(1080p|720p|480p|2160p|4k|x264|x265|hevc|bluray|bd|web|webrip|"
    r"dvd|aac|flac|dual[\s._-]?audio|multi|sub(bed|s)?|dub(bed)?|hi10p?|repack|v\d)\b",
    re.IGNORECASE,
)


@dataclass
class Candidate:
    path: Path
    title_guess: str
    episode: int | None
    modified: datetime


def clean_title(stem: str) -> str:
    text = NOISE.sub(" ", stem)
    text = re.sub(r"[._]+", " ", text)
    text = re.sub(r"[sS]\d{1,2}[eE]\d{1,3}", " ", text)
    text = re.sub(r"\b[eE][pP]?[\s]?\d{1,3}\b", " ", text)
    text = re.sub(r"\s+-\s+\d{1,3}\s*$", " ", text)
    text = re.sub(r"[^A-Za-z0-9' ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def guess_episode(stem: str) -> int | None:
    for pattern in EPISODE_PATTERNS:
        match = pattern.search(stem)
        if not match:
            continue
        value = match.group(match.lastindex or 1)
        try:
            number = int(value)
        except ValueError:
            continue
        if 0 < number <= 999:
            return number
    return None


def scan(root: Path, within_days: int) -> list[Candidate]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=within_days)
    found: list[Candidate] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in VIDEO_SUFFIXES:
            continue
        try:
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if modified < cutoff:
            continue
        title = clean_title(path.stem) or clean_title(path.parent.name)
        if not title:
            continue
        found.append(
            Candidate(
                path=path,
                title_guess=title,
                episode=guess_episode(path.stem),
                modified=modified,
            )
        )
    found.sort(key=lambda c: c.modified, reverse=True)
    return found


def best_match(client: httpx.Client, base_url: str, title: str) -> dict | None:
    try:
        resp = client.get(f"{base_url}/api/anime/suggest", params={"q": title[:60]})
        resp.raise_for_status()
        items = resp.json().get("items") or []
    except Exception:
        return None
    if not items:
        return None
    names = [item["title"] for item in items]
    close = difflib.get_close_matches(title, names, n=1, cutoff=0.45)
    if close:
        for item in items:
            if item["title"] == close[0]:
                return item
    return items[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Match local files to your Kura shelf")
    parser.add_argument("--path", required=True, help="Folder holding files you own")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--token", default="", help="JWT from /api/auth/login")
    parser.add_argument("--days", type=int, default=14, help="Only files touched recently")
    parser.add_argument("--apply", action="store_true", help="Write progress instead of listing")
    parser.add_argument("--dry-run", action="store_true", default=False)
    args = parser.parse_args(argv)

    root = Path(args.path).expanduser()
    if not root.is_dir():
        print(f"Not a folder: {root}", file=sys.stderr)
        return 2

    candidates = scan(root, args.days)
    if not candidates:
        print(f"No recently touched video files under {root}")
        return 0

    print(f"Found {len(candidates)} recent files under {root}\n")
    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    applied = 0

    with httpx.Client(timeout=20.0, headers=headers) as client:
        # One suggest call per distinct title guess, not per file.
        resolved: dict[str, dict | None] = {}
        for candidate in candidates:
            key = candidate.title_guess.lower()
            if key not in resolved:
                resolved[key] = best_match(client, args.base_url, candidate.title_guess)
            match = resolved[key]
            episode = candidate.episode
            label = match["title"] if match else "no catalog match"
            print(
                f"  {candidate.path.name}\n"
                f"    guess: {candidate.title_guess} | episode {episode or '?'} -> {label}"
            )

            if not (args.apply and match and episode and args.token):
                continue
            try:
                resp = client.put(
                    f"{args.base_url}/api/library/{match['id']}",
                    json={"status": "watching", "progress": episode},
                )
                resp.raise_for_status()
                applied += 1
                print(f"    set {match['title']} to episode {episode}")
            except Exception as exc:
                print(f"    could not update: {exc}")

    if args.apply and not args.token:
        print("\nPass --token to actually write progress. Nothing was changed.")
    elif args.apply:
        print(f"\nUpdated {applied} titles.")
    else:
        print("\nDry run. Re-run with --apply and --token to write progress.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
