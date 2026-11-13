"""Conservatively format a reviewed Markdown report (Python 3, standard library).

Usage: python script/compile.py [draft.md] [-o report.md] [--force]
Number appendix HTML links and replace body citation labels with their numbers.
This tool does not verify sources or certify review approval.
"""

import argparse
from html import unescape
from pathlib import Path
import re
import sys


def number_references(text):
    """Number HTML source links under appendix headings, preserving URLs and markup."""
    # Mask examples without changing offsets used to edit the original text.
    masked = list(text)
    fence = None
    offset = 0
    for line in text.splitlines(keepends=True):
        match = re.match(r" {0,3}(`{3,}|~{3,})", line)
        protected = fence is not None or match is not None
        if fence:
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}\s*", line):
                fence = None
        elif match:
            fence = (match[1][0], len(match[1]))
        if protected:
            masked[offset:offset + len(line)] = ['\n' if c == '\n' else ' ' for c in line]
        offset += len(line)
    visible = ''.join(masked)
    for match in re.finditer(r'<!--.*?-->|<(pre|script|style)\b[^>]*>.*?</\1\s*>|(`+)[^`\n]*?\2', visible, re.I | re.S):
        masked[match.start():match.end()] = ['\n' if c == '\n' else ' ' for c in match[0]]
    visible = ''.join(masked)
    heading = re.compile(r'^ {0,3}(#{1,6})[ \t]+(.+?)\s*#*\s*$', re.M)
    regions = []
    appendix_start = None
    appendix_level = None
    for match in heading.finditer(visible):
        level = len(match[1])
        if appendix_start is not None and level <= appendix_level:
            regions.append((appendix_start, match.start()))
            appendix_start = None
        if appendix_start is None and re.match(r'(?:附录|附件|appendix)\b|^(?:附录|附件)', match[2], re.I):
            appendix_start, appendix_level = match.end(), level
    if appendix_start is not None:
        regions.append((appendix_start, len(text)))

    anchor = re.compile(r'<a\b[^>]*\bhref\s*=\s*([\'"])(.*?)\1[^>]*>(.*?)</a\s*>', re.I | re.S)
    anchors = list(anchor.finditer(visible))
    numbers = {}
    edits = []
    for match in anchors:
        if any(start <= match.start() < end for start, end in regions):
            url = unescape(match[2]).strip()
            if not re.match(r'https?://', url, re.I):
                continue
            number = numbers.setdefault(url, len(numbers) + 1)
            label = text[match.start(3):match.end(3)]
            label = re.sub(r'^\s*\[\d+\]\s*', '', label)
            edits.append((match.start(3), match.end(3), f'[{number}] {label}'))
    missing = []
    for match in anchors:
        if any(start <= match.start() < end for start, end in regions):
            continue
        # Only the skill's superscript citation syntax is rewritten.
        if not re.search(r'<sup\b[^>]*>\s*$', visible[:match.start()], re.I):
            continue
        if not re.match(r'\s*</sup\s*>', visible[match.end():], re.I):
            continue
        if not re.fullmatch(r'\s*\[(?:链接|\d+)\]\s*', match[3]):
            continue
        url = unescape(match[2]).strip()
        if url not in numbers:
            missing.append(url)
        else:
            edits.append((match.start(3), match.end(3), f'[{numbers[url]}]'))
    if missing:
        raise ValueError('citation URLs missing from appendix: ' + ', '.join(dict.fromkeys(missing)))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def format_report(text):
    """Normalize newlines and blank lines outside fenced code and HTML blocks."""
    lines = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()  # The terminal newline does not create an extra content line.
    result = []
    fence = None
    html = None
    protected_end = 0
    for line in lines:
        if fence:
            result.append(line)
            protected_end = len(result)
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}\s*", line):
                fence = None
            continue
        if html:
            result.append(line)
            protected_end = len(result)
            if html in line.lower():
                html = None
            continue
        match = re.match(r" {0,3}(`{3,}|~{3,})", line)
        if match:
            fence = (match[1][0], len(match[1]))
            result.append(line)
            continue
        match = re.match(r"\s*<(table|pre|script|style)\b", line, re.I)
        if match:
            closing = "</" + match[1].lower() + ">"
            html = None if closing in line.lower() else closing
            result.append(line)
            continue
        if not line.strip():
            if result and result[-1] != "":
                result.append("")
        else:
            result.append(line)
    while len(result) > protected_end and result[-1] == "":
        result.pop()
    return "\n".join(result) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=Path("draft.md"))
    parser.add_argument("-o", "--output", type=Path, default=Path("report.md"))
    parser.add_argument("--force", action="store_true", help="overwrite an existing output")
    args = parser.parse_args()
    try:
        if args.input.resolve() == args.output.resolve():
            raise ValueError("input and output must be different files")
        if args.output.exists() and args.input.samefile(args.output):
            raise ValueError("input and output must be different files")
        text = args.input.read_text(encoding="utf-8-sig")
        if not text.strip():
            raise ValueError("input report is empty")
        formatted = format_report(number_references(text))
        with args.output.open("w" if args.force else "x", encoding="utf-8", newline="\n") as output:
            output.write(formatted)
    except (OSError, UnicodeError, ValueError) as exc:
        print("compile: " + str(exc), file=sys.stderr)
        return 1
    print("Report written to " + str(args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
