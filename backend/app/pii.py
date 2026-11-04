"""Supplemental bounded PII recognition with source-position-preserving normalization."""

import re
import unicodedata


def normalized_view(text: str) -> tuple[str, list[tuple[int, int]]]:
    characters, positions = [], []
    for index, character in enumerate(text):
        if unicodedata.category(character) == "Cf":
            continue
        for normalized in unicodedata.normalize("NFKC", character):
            characters.append(normalized)
            positions.append((index, index + 1))
    value = "".join(characters)
    # Only explicit bracketed markers: ordinary prose such as 'meet at noon' stays intact.
    for pattern, replacement in ((r"\s*[\[(]\s*at\s*[\])]\s*", "@"), (r"\s*[\[(]\s*dot\s*[\])]\s*", ".")):
        matches = list(re.finditer(pattern, value, re.I))
        for match in reversed(matches):
            start, end = match.span()
            value = value[:start] + replacement + value[end:]
            positions[start:end] = [(positions[start][0], positions[end - 1][1])]
    # Permit explicit spacing around email delimiters without changing released text.
    for match in reversed(list(re.finditer(r"\s*([@.])\s*", value))):
        start, end = match.span()
        value = value[:start] + match.group(1) + value[end:]
        positions[start:end] = [(positions[start][0], positions[end - 1][1])]
    return value, positions


def luhn(value: str) -> bool:
    digits = [int(character) for character in value if character.isdigit() and character.isascii()]
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    return (
        sum(
            (digit * 2 - 9 if digit * 2 > 9 else digit * 2) if index % 2 == len(digits) % 2 else digit for index, digit in enumerate(digits)
        )
        % 10
        == 0
    )


def supplemental_findings(value: str, entities: list[str] | None) -> list[tuple[int, int]]:
    supported = {
        "EMAIL_ADDRESS": r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b",
        "PHONE_NUMBER": r"(?<!\w)(?:\+?\d[\d ()-]{8,}\d)(?!\w)",
        "US_SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "CREDIT_CARD": r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)",
    }
    spans = []
    for entity, pattern in supported.items():
        if entities is not None and entity not in entities:
            continue
        for match in re.finditer(pattern, value, re.I):
            if entity != "CREDIT_CARD" or luhn(match.group()):
                spans.append(match.span())
    return spans
