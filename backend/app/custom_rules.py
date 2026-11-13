"""Bounded custom detectors. No matched text is included in evidence."""

import re
import time
import regex

MAX_PATTERN = 200


def compile_pattern(value):
    # Deliberately small regex language: no groups, alternatives or backreferences.
    if any(char in value for char in "()|") or re.search(r"\\[1-9g]", value):
        raise ValueError("Custom regex does not support groups, alternatives or backreferences")
    for bounds in re.findall(r"\{(\d*)(?:,(\d*))?\}", value):
        if any(int(bound) > 1000 for bound in bounds if bound):
            raise ValueError("Custom regex repetition limit is 1000")
    try:
        pattern = regex.compile(value, regex.I | regex.VERSION1)
        if pattern.search("", timeout=0.02) is not None:
            raise ValueError("Custom regex must not match empty text")
        return pattern
    except regex.error as error:
        raise ValueError("Invalid custom regex") from error


def detect(text, rule):
    if len(text) > 12000:
        raise ValueError("Custom inspection text limit exceeded")
    deadline = time.monotonic() + 0.05
    spans = set()
    for value in rule.values:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Custom inspection deadline")
        pattern = compile_pattern(value) if rule.detection == "regex" else regex.compile(regex.escape(value), regex.I)
        for match in pattern.finditer(text, timeout=remaining, concurrent=True):
            if time.monotonic() >= deadline:
                raise TimeoutError("Custom inspection deadline")
            if match.end() <= match.start():
                raise ValueError("Zero-width custom match cannot be inspected")
            spans.add((match.start(), match.end()))
    return sorted(spans)
