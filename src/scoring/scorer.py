
import re
from typing import Any


WEIGHTS = {
    "hook_strength": 0.20,
    "emotional_impact": 0.20,
    "suspense_curiosity": 0.20,
    "cliffhanger_payoff": 0.15,
    "standalone_clarity": 0.15,
    "promotional_relevance": 0.10,
}

CONFLICT_WORDS = {
    "betray", "betrayal", "lie", "liar", "revenge", "kill", "murder",
    "danger", "threat", "hate", "fight", "enemy", "war", "attack",
    "secret", "truth", "prove", "punish", "destroy", "escape",
}
EMOTION_WORDS = {
    "love", "heart", "cry", "tears", "fear", "afraid", "pain", "hurt",
    "sorry", "please", "alone", "death", "die", "happy", "marry",
    "wife", "husband", "mother", "father", "family",
}
SUSPENSE_WORDS = {
    "secret", "truth", "who", "why", "how", "never", "wait", "unless",
    "unless", "before", "betray", "hidden", "discover", "reveal",
    "promise", "swear", "mystery", "actually",
}
CLIFFHANGER_WORDS = {
    "but", "however", "suddenly", "wait", "stop", "no", "never",
    "what", "who", "why", "how", "truth", "secret", "discover",
    "impossible", "dead", "alive", "tomorrow",
}
PROMO_WORDS = CONFLICT_WORDS | EMOTION_WORDS | SUSPENSE_WORDS


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(x) for x in value)
    return str(value)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z']+", text.lower()))


def _score(value: float) -> float:
    return round(max(0.0, min(10.0, value)), 2)


def _contains_any(words: set[str], vocabulary: set[str]) -> int:
    return len(words & vocabulary)


def score_candidate(candidate: dict, segments: list[dict]) -> dict:
    """Return six explainable 0–10 heuristic scores and weighted final score."""
    start = float(candidate.get("start_seconds", 0))
    end = float(candidate.get("end_seconds", 0))

    selected = [
        s for s in segments
        if float(s.get("start_seconds", 0)) < end
        and float(s.get("end_seconds", 0)) > start
    ]
    selected.sort(key=lambda s: float(s.get("start_seconds", 0)))

    if not selected:
        return {key: 0.0 for key in (*WEIGHTS, "final_score")}

    contents = [_text(s.get("content")) for s in selected]
    combined = " ".join(contents)
    all_words = _words(combined)
    first_text = contents[0] if contents else ""
    last_text = contents[-1] if contents else ""
    first_words = _words(first_text)
    last_words = _words(last_text)

    dialogue = [
        s for s in selected
        if str(s.get("segment_type", "")).upper() == "DIALOGUE"
    ]
    actions = [
        s for s in selected
        if str(s.get("segment_type", "")).upper() == "ACTION"
    ]
    speakers = {
        str(s.get("speaker", "")).strip()
        for s in dialogue if s.get("speaker")
    }
    directions = " ".join(_text(s.get("emotion_or_direction")) for s in selected)
    direction_words = _words(directions)

    # Hook: strong opening language, dialogue, questions, and conflict cues.
    hook = 2.0
    if selected[0].get("segment_type", "").upper() == "DIALOGUE":
        hook += 2.0
    if "?" in first_text:
        hook += 1.5
    if "!" in first_text:
        hook += 1.0
    hook += min(3.0, _contains_any(first_words, CONFLICT_WORDS) * 0.8)
    if len(first_text.split()) >= 5:
        hook += 0.5

    # Emotional impact: emotional language and screenplay direction.
    emotional_hits = _contains_any(all_words, EMOTION_WORDS)
    emotional_hits += _contains_any(direction_words, EMOTION_WORDS)
    emotion = 1.5 + min(5.5, emotional_hits * 0.65)
    if any(x in directions.lower() for x in
           ("cry", "scream", "angry", "terrified", "shaking", "weeping")):
        emotion += 1.5
    if len(speakers) >= 2:
        emotion += 0.5

    # Suspense: mystery, questions, uncertainty, conflict.
    suspense_hits = _contains_any(all_words, SUSPENSE_WORDS)
    questions = combined.count("?")
    suspense = 1.5 + min(5.0, suspense_hits * 0.65)
    suspense += min(2.0, questions * 0.5)
    if _contains_any(all_words, CONFLICT_WORDS) >= 2:
        suspense += 1.0

    # Cliffhanger/payoff: ending language and punctuation.
    ending_hits = _contains_any(last_words, CLIFFHANGER_WORDS)
    cliffhanger = 2.0 + min(4.5, ending_hits * 1.0)
    if last_text.rstrip().endswith(("?", "!", "...")):
        cliffhanger += 1.5
    if any(x in last_text.lower() for x in
           ("you will", "i know", "you are", "what if", "but then")):
        cliffhanger += 1.0

    # Standalone clarity: enough dialogue/context and multiple story elements.
    duration = max(0.0, end - start)
    dialogue_ratio = len(dialogue) / max(1, len(selected))
    clarity = 2.0 + min(3.0, len(dialogue) * 0.35)
    clarity += min(2.0, len(speakers) * 0.8)
    clarity += min(2.0, dialogue_ratio * 2.0)
    if len(selected) >= 3:
        clarity += 0.5
    if duration >= 20:
        clarity += 0.5

    # Promo relevance: dramatic themes, dialogue/action mix, and story variety.
    promo_hits = _contains_any(all_words, PROMO_WORDS)
    categories = sum([
        bool(all_words & CONFLICT_WORDS),
        bool(all_words & EMOTION_WORDS),
        bool(all_words & SUSPENSE_WORDS),
        bool(actions),
    ])
    relevance = 1.0 + min(5.0, promo_hits * 0.35) + categories * 0.8
    if dialogue and actions:
        relevance += 0.8

    scores = {
        "hook_strength": _score(hook),
        "emotional_impact": _score(emotion),
        "suspense_curiosity": _score(suspense),
        "cliffhanger_payoff": _score(cliffhanger),
        "standalone_clarity": _score(clarity),
        "promotional_relevance": _score(relevance),
    }
    scores["final_score"] = round(
        sum(scores[key] * weight for key, weight in WEIGHTS.items()), 2
    )
    return scores
