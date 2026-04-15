from __future__ import annotations

import difflib
import re
import unicodedata

def normalize_text(text: str) -> str:
    """Normalize Unicode and collapse repeated whitespace."""
    text = unicodedata.normalize("NFC", text)
    return " ".join(text.split())

def tokenize(text: str) -> list[str]:
    n = normalize_text(text)
    return n.split() if n else []

def token_sig(t: str) -> str:
    """Build a normalized token signature for fuzzy comparison."""
    return re.sub(r"[^\w]", "", t).casefold()

def longest_suffix_prefix_overlap(left: list[str], right: list[str]) -> int:
    """Return the longest exact overlap between the left suffix and right prefix."""
    max_search = min(len(left), len(right), 50)
    for ol in range(max_search, 0, -1):
        if all(token_sig(a) == token_sig(b) for a, b in zip(left[-ol:], right[:ol])):
            return ol
    return 0

def _smart_join(existing: str, delta: str) -> str:
    """Join text fragments while preserving punctuation spacing."""
    existing = existing.rstrip()
    delta = delta.lstrip()
    if not existing: return delta
    if not delta: return existing
    if delta.startswith((",", ".", "!", "?", ";", ":")):
        return f"{existing}{delta}"
    return f"{existing} {delta}"

def compute_transcript_update(existing_stable_text: str, current_full_text: str) -> tuple[str, str]:
    """
    Return `(delta_text, stable_text)` for the latest transcription window.

    The function aligns the new window against the stable transcript, removes
    overlapping text, filters out repeated leading text, and keeps only the
    newly confirmed delta.
    """
    existing_tokens = tokenize(existing_stable_text)
    window_tokens = tokenize(current_full_text)

    if not window_tokens:
        return "", normalize_text(existing_stable_text)
    if not existing_tokens:
        t = " ".join(window_tokens)
        return t, t

    tail_size = 60
    existing_tail = existing_tokens[-tail_size:]
    len_ext = len(existing_tail)
    len_win = len(window_tokens)

    sig_existing = [token_sig(t) for t in existing_tail]
    sig_window = [token_sig(t) for t in window_tokens]

    matcher = difflib.SequenceMatcher(None, sig_existing, sig_window)
    blocks = matcher.get_matching_blocks()

    best_block = None
    best_score = -999999

    for b in blocks:
        if b.size == 0:
            continue
        
        is_end_of_ext = (b.a + b.size == len_ext)
        is_start_of_win = (b.b == 0)
        
        if b.size < 2 and not (is_end_of_ext or is_start_of_win):
            continue

        dist_from_end_ext = len_ext - (b.a + b.size)
        dist_from_start_win = b.b
        
        score = (b.size * 20) - (dist_from_end_ext * 2) - dist_from_start_win
        
        if score > best_score:
            best_score = score
            best_block = b

    if best_block and best_score > 0:
        delta_start = best_block.b + best_block.size
        delta_tokens = window_tokens[delta_start:]
    else:
        ol = longest_suffix_prefix_overlap(existing_tokens, window_tokens)
        if ol > 0:
            delta_tokens = window_tokens[ol:]
        else:
            delta_tokens = window_tokens

    delta_text = " ".join(delta_tokens)
    stable_text = _smart_join(" ".join(existing_tokens), delta_text)
    
    return delta_text, stable_text
