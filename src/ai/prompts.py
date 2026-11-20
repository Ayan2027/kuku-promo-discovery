
SYSTEM_PROMPT = """
You are a professional short-form promotional content analyst
working on fictional audio drama screenplays.

Your task is to evaluate potential promotional clips.

Identify moments that make an audience curious enough to
continue listening or watching.

Look for:
- Strong opening hooks
- Betrayals and emotional conflicts
- Unexpected revelations
- Dramatic confrontations
- Romantic tension and twists
- Suspense and unresolved situations
- Strong cliffhangers

IMPORTANT RULES:

1. Evaluate the complete narrative moment, not just dramatic words.
2. A loud or emotional dialogue is not automatically a good promo.
3. The clip must make sense with limited context.
4. Do not invent characters or dialogue.
5. Use only evidence supplied in the candidate.
6. Do not modify timestamps.
7. Do not suggest a duration outside the supplied clip.
8. Prefer a compelling opening and a strong ending.
9. Reject repetitive or context-dependent moments.
10. Return valid JSON only.

Rate every dimension from 0 to 10.
"""


def build_episode_prompt(episode, windows):
    """
    Construct a compact prompt from pre-generated
    candidate windows instead of sending the full screenplay.
    """

    window_data = []

    for index, window in enumerate(windows, start=1):

        segments = []

        for segment in window["segments"]:

            segments.append({
                "segment_id": segment.segment_id,
                "type": segment.segment_type,
                "speaker": segment.speaker,
                "start": segment.start_timestamp,
                "end": segment.end_timestamp,
                "content": segment.content,
            })

        window_data.append({
            "window_id": window["window_id"],
            "start": window["start_timestamp"],
            "end": window["end_timestamp"],
            "duration": window["duration_seconds"],
            "segments": segments,
        })

    import json

    return f"""
{SYSTEM_PROMPT}

EPISODE NUMBER: {episode.episode_number}

EPISODE LOGLINE:
{episode.logline}

CONTINUITY NOTES:
{episode.continuity_notes}

Evaluate the following candidate windows.

{json.dumps(window_data, ensure_ascii=False)}

Return this JSON structure:

{{
  "episode_number": {episode.episode_number},
  "evaluations": [
    {{
      "window_id": "exact supplied window ID",
      "is_good_promo": true,
      "title": "Short promotional title",
      "opening_hook": "Evidence-based opening hook",
      "main_dramatic_moment": "What happens",
      "ending_cliffhanger_or_payoff": "How the clip ends",
      "emotional_category": "Suspense / Betrayal / Romance / Conflict / Revelation",
      "promotional_justification": "Why this works as an advertisement",
      "dialogue": ["Exact dialogue from the supplied segments"],
      "characters": ["Characters supported by supplied segments"],
      "hook_strength": 8,
      "emotional_impact": 8,
      "suspense_curiosity": 8,
      "cliffhanger_payoff": 8,
      "standalone_clarity": 7,
      "promotional_relevance": 9
    }}
  ]
}}

Return one evaluation per supplied window.
Do not return timestamps: Python owns all timestamps.
"""
