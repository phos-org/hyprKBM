#!/usr/bin/env python3

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PREFIXES = ("http://", "https://", "mailto:", "irc:", "ftp://")
FENCE = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]*)\)")
IMG = re.compile(r"<img\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)
HREF = re.compile(r"<a\b[^>]*?\bhref\s*=\s*[\"']([^\"']+)[\"']", re.I)
INLINE_CODE = re.compile(r"`[^`]*`")


def heading_text(raw):
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", raw)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("`", "")
    text = text.replace("**", "").replace("__", "")
    text = text.replace("*", "").replace("_", "")
    return text.strip()


def github_slug(text):
    text = heading_text(text).lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = text.strip()
    text = re.sub(r"\s+", "-", text)
    return text


def anchors_in(path):
    seen = {}
    found = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADING.match(line)
        if match is None:
            continue
        base = github_slug(match.group(2))
        count = seen.get(base, 0)
        seen[base] = count + 1
        found.add(base if count == 0 else "%s-%d" % (base, count))
    return found


def split_target(raw):
    raw = raw.strip()
    if raw.startswith("<") and ">" in raw:
        return raw[1:raw.index(">")].strip()
    return raw.split()[0] if raw.split() else ""


def targets_in(line):
    found = []
    visible = INLINE_CODE.sub("", line)
    for pattern in (LINK, IMG, HREF):
        for match in pattern.finditer(visible):
            target = split_target(match.group(1))
            if target:
                found.append((match.start(1), target))
    return found


def markdown_files():
    files = [ROOT / "README.md"]
    docs = ROOT / "docs"
    if docs.is_dir():
        files.extend(sorted(p for p in docs.rglob("*.md") if p.is_file()))
    return files


def check_file(path, cache, failures):
    fenced = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        for _start, target in targets_in(line):
            if target.startswith(SKIP_PREFIXES) or target.startswith("//"):
                continue
            path_part, _, anchor = target.partition("#")
            if path_part == "":
                destination = path
            else:
                destination = (path.parent / path_part).resolve()
                try:
                    destination.relative_to(ROOT)
                except ValueError:
                    failures.append("%s:%d: %s leaves the repository" % (path.relative_to(ROOT), number, target))
                    continue
                if not destination.exists():
                    failures.append("%s:%d: %s does not exist" % (path.relative_to(ROOT), number, target))
                    continue
            if anchor == "":
                continue
            if destination.suffix.lower() != ".md":
                failures.append("%s:%d: %s has an anchor but is not a Markdown file" % (
                    path.relative_to(ROOT), number, target))
                continue
            if destination not in cache:
                cache[destination] = anchors_in(destination)
            if anchor not in cache[destination]:
                failures.append("%s:%d: %s has no heading #%s" % (
                    path.relative_to(ROOT), number, target, anchor))


def main():
    files = markdown_files()
    failures = []
    cache = {}
    for path in files:
        check_file(path, cache, failures)
    if failures:
        print("\n".join(failures))
        print("%d broken link(s) in %d file(s)" % (len(failures), len(files)))
        return 1
    print("ok: %d markdown file(s), relative links and in-repo anchors resolve" % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
