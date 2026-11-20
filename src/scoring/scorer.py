"""
Explainable, deterministic scoring for promo windows.

The scorer is intentionally conservative: it rewards clips that open on a
self-contained dramatic beat and cut on unresolved tension, and penalises
clips that begin mid-conversation, open on a one-word line, or end on a
closed / resolved beat.

The same scorer is used by the window generator and by the final ranker so
the score shown to a reviewer is the score that selected the clip.
"""

from __future__ import annotations

import re
from typing import Any

WEIGHTS = {
    "hook_strength": 0.25,
    "emotional_impact": 0.15,
    "suspense_curiosity": 0.15,
    "cliffhanger_payoff": 0.20,
    "standalone_clarity": 0.15,
    "promotional_relevance": 0.10,
}

# The brief requires the hook to land in the first three seconds of the clip.
HOOK_WINDOW_SECONDS = 3.0

CONFLICT_WORDS = {
    "betray", "betrayal", "betrayed", "liar", "lie", "lied", "revenge",
    "kill", "murder", "danger", "threat", "hate", "fight", "enemy",
    "war", "attack", "secret", "truth", "prove", "punish", "destroy",
    "escape", "shame", "disgrace", "ruin", "steal", "cheat", "affair",
    "cruel", "cruelty", "wrong", "stop", "never",
}

EMOTION_WORDS = {
    "love", "heart", "cry", "tears", "fear", "afraid", "pain", "hurt",
    "sorry", "please", "alone", "death", "die", "happy", "marry",
    "wife", "husband", "mother", "father", "family", "child", "son",
    "daughter", "broken", "grief", "shame", "humiliation", "beg",
    "beautiful", "darling", "sweetheart", "devastated", "desperate",
}

SUSPENSE_WORDS = {
    "secret", "truth", "who", "why", "how", "never", "wait", "unless",
    "before", "betray", "hidden", "discover", "reveal", "promise",
    "swear", "mystery", "actually", "remember", "forgot", "missing",
    "dead", "alive", "pregnant", "inheritance", "will", "letter",
}

REVEAL_MARKERS = {
    "because", "i am", "you are", "he is", "she is", "they are",
    "marrying", "pregnant", "dead", "alive", "your son", "your daughter",
    "your father", "your mother", "secret", "truth", "affair",
    "divorce", "inheritance", "will", "betray", "never",
}

UNRESOLVED_MARKERS = {
    "what", "who", "why", "how", "if", "unless", "never", "stop", "wait",
    "don't", "do not", "you don't know", "there is something", "i know",
    "tell me", "look at me", "one more thing", "before", "until",
    "but", "however", "suddenly", "or else", "you will", "i will",
    "you cannot", "you can't", "not yet", "too late",
}

CLOSURE_MARKERS = {
    "i love you", "thank you", "goodbye", "it's over", "it is over",
    "i'm sorry", "i am sorry", "forgive me", "we're safe", "we are safe",
    "happily", "i do", "you may kiss", "welcome home", "it's done",
    "it is done", "i forgive you", "you're welcome", "good night",
}

IMPERATIVES = {
    "stop", "look", "tell", "get", "come", "leave", "give", "don't",
    "do", "listen", "wait", "take", "put", "shut", "stay", "go",
    "help", "save", "marry", "sign", "apologize", "kneel", "stand",
    "sit", "bring", "show", "answer", "speak", "quiet", "run",
}

CONTEXT_STARTERS = {
    "and", "but", "so", "then", "because", "he", "she", "they", "it",
    "that", "this", "you", "we", "i", "as", "while", "when", "after",
    "before", "if", "well", "oh", "ah", "yes", "no",
}

GENERIC_VOCATIVES = {
    "father", "mother", "sir", "madam", "my lord", "my lady", "your grace",
    "your highness", "your majesty", "doctor", "please", "no", "yes",
    "what", "why", "who", "alexander", "gerald", "juliana", "clarissa",
}

ACTION_POWER_WORDS = {
    "slap", "slaps", "push", "pushes", "shove", "shoves", "grab", "grabs",
    "kneel", "kneels", "collapse", "collapses", "scream", "screams",
    "cry", "cries", "tears", "turn", "turns", "drop", "drops",
    "shatter", "shatters", "blood", "gun", "knife", "faint", "faints",
    "reveal", "reveals", "tear", "tears", "rip", "rips", "throw",
}

HOOK_TYPE_BY_WORD = (
    ("question", ("?",)),
    ("revelation", ("because", "i am", "you are", "he is", "she is",
                    "marrying", "pregnant", "dead", "alive", "secret",
                    "truth", "betray")),
    ("conflict", ("stop", "liar", "hate", "kill", "destroy", "never",
                  "how dare", "shame", "disgrace", "ruin", "cruel")),
)


def _get(segment: Any, key: str, default: Any = None) -> Any:
    if isinstance(segment, dict):
        return segment.get(key, default)
    return getattr(segment, key, default)


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text.strip('"')


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z']+", text.lower()))


def _score(value: float) -> float:
    return round(max(0.0, min(10.0, value)), 2)


def _contains(text: str, vocabulary: set[str]) -> int:
    words = _words(text)
    return len(words & vocabulary)


def _first_word(text: str) -> str:
    match = re.match(r"[A-Za-z']+", _clean(text))
    return match.group(0).lower() if match else ""


def _is_imperative(text: str) -> bool:
    return _first_word(text) in IMPERATIVES


def _is_generic_vocative(text: str) -> bool:
    cleaned = _clean(text).lower().strip(" .,!?")
    words = cleaned.split()
    if len(words) > 3:
        return False
    return cleaned in GENERIC_VOCATIVES or (
        len(words) == 1 and words[0] in GENERIC_VOCATIVES
    )


def _hook_type(text: str, segment_type: str) -> str:
    if not text:
        return "unknown"
    lowered = text.lower()
    for label, markers in HOOK_TYPE_BY_WORD:
        if any(marker in lowered for marker in markers):
            return label
    if segment_type == "ACTION":
        return "action"
    return "conflict"


def _cliffhanger_type(text: str, segment_type: str) -> str:
    if not text:
        return "unknown"
    lowered = text.lower()
    if any(marker in lowered for marker in CLOSURE_MARKERS):
        return "closure"
    if "?" in text:
        return "question"
    if any(marker in lowered for marker in UNRESOLVED_MARKERS):
        return "unresolved"
    if any(marker in lowered for marker in REVEAL_MARKERS):
        return "revelation"
    if "..." in text:
        return "unresolved"
    if segment_type == "ACTION":
        return "reaction"
    return "weak"


def _select_segments(
    start: float,
    end: float,
    segments: list[Any],
) -> list[Any]:
    selected = [
        s for s in segments
        if float(_get(s, "start_seconds", 0)) < end
        and float(_get(s, "end_seconds", 0)) > start
    ]
    selected.sort(key=lambda s: float(_get(s, "start_seconds", 0)))
    return selected


def first_beat_start(selected: list[Any]) -> float | None:
    """Start time of the earliest dialogue/action beat, if any."""

    starts = [
        float(_get(s, "start_seconds", 0))
        for s in selected
        if str(_get(s, "segment_type", "")).upper() in ("DIALOGUE", "ACTION")
    ]
    return min(starts) if starts else None


def _pick_first_beat(
    selected: list[Any],
    start: float,
    window: float = HOOK_WINDOW_SECONDS,
) -> Any | None:
    """Prefer a dialogue/action beat that begins within the hook window."""

    early = [
        s for s in selected
        if float(_get(s, "start_seconds", 0)) <= start + window
    ]
    for preferred in ("DIALOGUE", "ACTION"):
        for segment in early:
            if str(_get(segment, "segment_type", "")).upper() == preferred:
                return segment
    return selected[0] if selected else None


def _pick_last_beat(selected: list[Any], end: float) -> Any | None:
    """Prefer a dialogue/action beat that ends in the final 5 seconds."""
    late = [
        s for s in selected
        if float(_get(s, "end_seconds", 0)) >= end - 5.0
    ]
    for preferred in ("DIALOGUE", "ACTION"):
        for segment in reversed(late):
            if str(_get(segment, "segment_type", "")).upper() == preferred:
                return segment
    return selected[-1] if selected else None


def _segment_label(segment: Any) -> str:
    if segment is None:
        return ""
    speaker = str(_get(segment, "speaker", "") or "").strip()
    content = _clean(_get(segment, "content", ""))
    if speaker and str(_get(segment, "segment_type", "")).upper() == "DIALOGUE":
        return f"{speaker}: {content}"
    return content


def _main_moment(selected: list[Any]) -> str:
    beats = [
        s for s in selected
        if str(_get(s, "segment_type", "")).upper() in ("DIALOGUE", "ACTION")
    ]
    if not beats:
        return _clean(" ".join(_get(s, "content", "") for s in selected))[:220]

    def intensity(segment: Any) -> tuple[int, int]:
        text = _clean(_get(segment, "content", ""))
        hits = (
            _contains(text, CONFLICT_WORDS)
            + _contains(text, EMOTION_WORDS)
            + _contains(text, SUSPENSE_WORDS)
        )
        return hits, len(text)

    best = max(beats, key=intensity)
    return _segment_label(best)[:220]


def score_window(
    start: float,
    end: float,
    segments: list[Any],
) -> tuple[dict[str, float], dict[str, Any]]:
    """Score a candidate interval and return scores plus editorial metadata."""

    selected = _select_segments(start, end, segments)
    if not selected:
        return {key: 0.0 for key in (*WEIGHTS, "final_score")}, {
            "opening_hook": "",
            "ending_cliffhanger": "",
            "main_dramatic_moment": "",
            "hook_type": "unknown",
            "cliffhanger_type": "unknown",
            "categories": [],
        }

    combined = " ".join(_clean(_get(s, "content", "")) for s in selected)
    all_words = _words(combined)

    dialogue = [
        s for s in selected
        if str(_get(s, "segment_type", "")).upper() == "DIALOGUE"
    ]
    actions = [
        s for s in selected
        if str(_get(s, "segment_type", "")).upper() == "ACTION"
    ]
    speakers = {
        str(_get(s, "speaker", "")).strip()
        for s in dialogue
        if _get(s, "speaker")
    }
    directions = " ".join(
        _clean(_get(s, "emotion_or_direction", "")) for s in selected
    )
    direction_words = _words(directions)

    first_beat = _pick_first_beat(selected, start)
    last_beat = _pick_last_beat(selected, end)

    first_text = _clean(_get(first_beat, "content", "")) if first_beat else ""
    last_text = _clean(_get(last_beat, "content", "")) if last_beat else ""
    first_type = str(_get(first_beat, "segment_type", "")).upper() if first_beat else ""
    last_type = str(_get(last_beat, "segment_type", "")).upper() if last_beat else ""

    # ------------------------------------------------------------
    # Hook: can the first three seconds stop a scroll?
    # ------------------------------------------------------------
    hook = 2.5
    if first_type == "DIALOGUE":
        hook += 1.4
    elif first_type == "ACTION":
        hook += 0.8

    first_words = _clean(first_text).split()
    hook_word_count = len(first_words)
    if "?" in first_text:
        hook += 1.9
    if "!" in first_text:
        hook += 0.7
    if "..." in first_text:
        hook += 0.4
    if _is_imperative(first_text):
        hook += 1.3
    hook += min(1.8, _contains(first_text, CONFLICT_WORDS) * 0.7)
    if 3 <= hook_word_count <= 18:
        hook += 1.3
    elif hook_word_count <= 2:
        hook -= 2.2
    elif hook_word_count > 30:
        hook -= 0.4
    if _first_word(first_text) in CONTEXT_STARTERS:
        hook -= 1.5
    if _is_generic_vocative(first_text):
        hook -= 2.2
    if any(marker in first_text.lower() for marker in REVEAL_MARKERS):
        hook += 1.4
    if first_type == "ACTION" and _contains(first_text, ACTION_POWER_WORDS):
        hook += 1.2

    # ------------------------------------------------------------
    # Cliffhanger: does the final beat leave a question open?
    # ------------------------------------------------------------
    cliff = 2.5
    if last_type == "DIALOGUE":
        cliff += 0.8
    if "?" in last_text:
        cliff += 2.0
    if "!" in last_text:
        cliff += 0.5
    if "..." in last_text:
        cliff += 1.0
    if any(marker in last_text.lower() for marker in UNRESOLVED_MARKERS):
        cliff += 1.5
    if any(marker in last_text.lower() for marker in CLOSURE_MARKERS):
        cliff -= 3.0
    if len(_clean(last_text).split()) <= 2:
        cliff -= 0.8
    if any(marker in last_text.lower() for marker in REVEAL_MARKERS):
        cliff += 0.8
    if last_type == "ACTION" and _contains(last_text, ACTION_POWER_WORDS):
        cliff += 1.2

    # ------------------------------------------------------------
    # Emotional impact
    # ------------------------------------------------------------
    emotional_hits = _contains(combined, EMOTION_WORDS)
    emotional_hits += _contains(directions, EMOTION_WORDS)
    emotion = 2.5 + min(4.0, emotional_hits * 0.55)
    if any(
        marker in directions.lower()
        for marker in ("cry", "scream", "angry", "terrified", "shaking", "weeping")
    ):
        emotion += 1.2
    if len(speakers) >= 2:
        emotion += 0.7
    if _contains(combined, ACTION_POWER_WORDS):
        emotion += 0.7

    # ------------------------------------------------------------
    # Suspense / curiosity
    # ------------------------------------------------------------
    suspense_hits = _contains(combined, SUSPENSE_WORDS)
    questions = combined.count("?")
    suspense = 2.5 + min(4.0, suspense_hits * 0.55)
    suspense += min(1.8, questions * 0.5)
    if _contains(combined, CONFLICT_WORDS) >= 2:
        suspense += 0.9
    if any(marker in combined.lower() for marker in ("secret", "truth", "reveal")):
        suspense += 0.9

    # ------------------------------------------------------------
    # Standalone clarity
    # ------------------------------------------------------------
    duration = max(0.0, end - start)
    dialogue_ratio = len(dialogue) / max(1, len(selected))
    first_word = _first_word(first_text)
    clarity = 4.0
    if first_type == "ACTION" or first_word not in CONTEXT_STARTERS:
        clarity += 1.0
    if len(speakers) >= 2:
        clarity += 1.0
    if dialogue_ratio >= 0.30:
        clarity += 0.8
    if len({str(_get(s, "segment_type", "")).upper() for s in selected}) >= 2:
        clarity += 0.5
    if 25 <= duration <= 50:
        clarity += 0.6
    if first_word in CONTEXT_STARTERS:
        clarity -= 1.6
    if hook_word_count <= 2:
        clarity -= 1.6
    if len(speakers) > 5:
        clarity -= 0.8
    scene_ids = {str(_get(s, "scene_id", "")) for s in selected}
    if len(scene_ids) > 1:
        clarity -= 1.2

    # ------------------------------------------------------------
    # Promotional relevance
    # ------------------------------------------------------------
    categories = sum([
        bool(all_words & CONFLICT_WORDS),
        bool(all_words & EMOTION_WORDS),
        bool(all_words & SUSPENSE_WORDS),
        bool(actions),
    ])
    promo_hits = _contains(combined, CONFLICT_WORDS | EMOTION_WORDS | SUSPENSE_WORDS)
    relevance = 2.0 + min(3.5, categories * 1.0) + min(2.5, promo_hits * 0.25)
    if dialogue and actions:
        relevance += 1.0
    if 25 <= duration <= 50:
        relevance += 0.5

    scores = {
        "hook_strength": _score(hook),
        "emotional_impact": _score(emotion),
        "suspense_curiosity": _score(suspense),
        "cliffhanger_payoff": _score(cliff),
        "standalone_clarity": _score(clarity),
        "promotional_relevance": _score(relevance),
    }
    scores["final_score"] = round(
        sum(scores[key] * weight for key, weight in WEIGHTS.items()), 2
    )

    categories_found = sorted(
        name for name, vocabulary in (
            ("conflict", CONFLICT_WORDS),
            ("emotion", EMOTION_WORDS),
            ("suspense", SUSPENSE_WORDS),
            ("reveal", REVEAL_MARKERS),
        )
        if all_words & vocabulary
    )

    return scores, {
        "opening_hook": _segment_label(first_beat),
        "ending_cliffhanger": _segment_label(last_beat),
        "main_dramatic_moment": _main_moment(selected),
        "hook_type": _hook_type(first_text, first_type),
        "cliffhanger_type": _cliffhanger_type(last_text, last_type),
        "categories": categories_found,
        "duration": round(duration, 2),
        "speakers": sorted(speakers),
        "scene_count": len(scene_ids),
        "ends_mid_dialogue": any(
            float(_get(s, "start_seconds", 0)) < end
            < float(_get(s, "end_seconds", 0)) - 0.01
            for s in dialogue
        ),
    }


def score_candidate(candidate: dict, segments: list[dict]) -> dict:
    """Return the six explainable 0-10 scores and the weighted final score."""

    start = float(candidate.get("start_seconds", 0))
    end = float(candidate.get("end_seconds", 0))
    scores, _ = score_window(start, end, segments)
    return scores


def build_why_it_works(
    opening_hook: str,
    ending_cliffhanger: str,
    hook_type: str,
    cliffhanger_type: str,
    duration: float,
    categories: list[str] | None = None,
) -> str:
    """A single, specific sentence explaining why the cut should work."""

    opening = _clean(opening_hook)[:70] or "a strong opening beat"
    return (
        f"Opens on a {hook_type} hook (\"{opening}\") and cuts at "
        f"{duration:.0f}s on {cliffhanger_type} tension."
    )


def build_promotional_justification(
    opening_hook: str,
    ending_cliffhanger: str,
    hook_type: str,
    cliffhanger_type: str,
    duration: float,
    categories: list[str] | None = None,
) -> str:
    """The longer, evidence-grounded explanation kept alongside the one-liner."""

    opening = _clean(opening_hook)[:120] or "a strong opening beat"
    ending = _clean(ending_cliffhanger)[:120] or "an unresolved final beat"
    category_text = ""
    if categories:
        category_text = f" The scene carries {', '.join(categories[:3])} signals."

    return (
        f"Opens on {hook_type} dialogue/action: \"{opening}\". "
        f"The {duration:.0f}s cut lands on {cliffhanger_type} tension: "
        f"\"{ending}\".{category_text}"
    )
