"""Conservatively format a reviewed Markdown report (Python 3, standard library).

Usage: python script/compile.py [draft.md] [-o report.md] [--force]
Citation HTML, tables, fenced code, and Markdown hard breaks are preserved.
This tool does not verify sources or certify review approval.
"""

import argparse
from pathlib import Path
import re
import sys


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
        formatted = format_report(text)
        with args.output.open("w" if args.force else "x", encoding="utf-8", newline="\n") as output:
            output.write(formatted)
    except (OSError, UnicodeError, ValueError) as exc:
        print("compile: " + str(exc), file=sys.stderr)
        return 1
    print("Report written to " + str(args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
