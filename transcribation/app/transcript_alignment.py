from __future__ import annotations

import re
import unicodedata


def normalize_text(text: str) -> str:
    """Normalize whitespace and unicode."""
    # Normalize unicode (e.g., combining characters)
    text = unicodedata.normalize("NFC", text)
    # Collapse whitespace
    text = " ".join(text.split())
    return text


def tokenize(text: str) -> list[str]:
    n = normalize_text(text)
    return n.split() if n else []


def token_sig(t: str) -> str:
    """Signature for fuzzy token comparison — strip punctuation and casefold."""
    return re.sub(r"[^\w]", "", t).casefold()


def longest_suffix_prefix_overlap(left: list[str], right: list[str]) -> int:
    """Find the longest overlap where the suffix of `left` matches the prefix of `right`.

    Limits search to avoid O(n^2) on long transcripts.
    """
    max_search = min(len(left), len(right), 50)  # cap search window
    for ol in range(max_search, 0, -1):
        if all(
            token_sig(a) == token_sig(b)
            for a, b in zip(left[-ol:], right[:ol])
        ):
            return ol
    return 0


def extract_new_from_context_segments(
    segments: list,
    context_duration: float,
    existing_stable_text: str,
) -> str:
    """Extract text spoken after context_duration using segment timestamps.

    Segments that start at or after `context_duration` are considered new.
    Segments that straddle the boundary are included if more than half of their
    duration falls after the boundary.
    """
    if not segments:
        return ""

    if context_duration <= 0.05:
        return " ".join(seg.text.strip() for seg in segments if seg.text.strip())

    new_parts: list[str] = []
    for seg in segments:
        seg_text = seg.text.strip()
        if not seg_text:
            continue

        seg_duration = seg.end - seg.start
        if seg_duration <= 0:
            continue

        if seg.start >= context_duration - 0.15:
            # Segment starts at or after context boundary
            new_parts.append(seg_text)
        else:
            # Segment straddles boundary — include if majority is in new region
            overlap_new = seg.end - context_duration
            if overlap_new > 0 and (overlap_new / seg_duration) > 0.5:
                new_parts.append(seg_text)

    new_text = " ".join(new_parts)
    if not new_text.strip():
        return ""

    # De-duplicate against existing stable text
    new_tokens = tokenize(new_text)
    existing_tokens = tokenize(existing_stable_text)

    if new_tokens and existing_tokens:
        ol = longest_suffix_prefix_overlap(existing_tokens, new_tokens)
        if ol > 0:
            new_tokens = new_tokens[ol:]

    return " ".join(new_tokens)


def merge_transcripts(existing: str, delta: str) -> str:
    """Merge existing transcript with new delta text."""
    existing = normalize_text(existing)
    delta = normalize_text(delta)

    if not delta:
        return existing
    if not existing:
        return delta

    # Check for overlap to avoid duplication
    existing_tokens = tokenize(existing)
    delta_tokens = tokenize(delta)

    if existing_tokens and delta_tokens:
        ol = longest_suffix_prefix_overlap(existing_tokens, delta_tokens)
        if ol > 0:
            # Delta overlaps with end of existing — only append the non-overlapping part
            delta_tokens = delta_tokens[ol:]
            if not delta_tokens:
                return existing
            delta = " ".join(delta_tokens)

    # Smart join with punctuation awareness
    if existing.endswith((" ", "\n")) or delta.startswith((",", ".", "!", "?", ";", ":")):
        return f"{existing}{delta}"
    return f"{existing} {delta}"


def compute_transcript_update(existing_stable_text: str, current_text: str) -> tuple[str, str]:
    """Returns (delta_text, stable_text).

    Compares existing stable text with the current full text to determine
    what is new (delta) and what the updated stable text should be.
    """
    existing_tokens = tokenize(existing_stable_text)
    current_tokens = tokenize(current_text)

    if not current_tokens:
        return "", normalize_text(existing_stable_text)

    if not existing_tokens:
        t = " ".join(current_tokens)
        return t, t

    # Find common prefix length
    prefix = 0
    for a, b in zip(existing_tokens, current_tokens):
        if token_sig(a) != token_sig(b):
            break
        prefix += 1

    if prefix == len(current_tokens):
        # Current is a subset of existing — no new content
        return "", " ".join(existing_tokens)

    if prefix == len(existing_tokens):
        # Current extends existing
        delta = current_tokens[prefix:]
        return " ".join(delta), " ".join(current_tokens)

    ol = longest_suffix_prefix_overlap(existing_tokens, current_tokens)
    if ol > 0:
        delta = current_tokens[ol:]
        if not delta:
            return "", " ".join(existing_tokens)
        return " ".join(delta), " ".join(existing_tokens + delta)

    delta = " ".join(current_tokens)
    merged = merge_transcripts(" ".join(existing_tokens), delta)
    merged_tokens = tokenize(merged)
    if len(merged_tokens) > len(existing_tokens):
        actual_delta = merged_tokens[len(existing_tokens):]
        return " ".join(actual_delta), merged
    return delta, merged
