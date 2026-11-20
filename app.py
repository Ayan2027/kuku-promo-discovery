"""Streamlit human-triage prototype for Kuku promo discovery.

The app is intentionally read-only with respect to the input pack. It loads
ranked outputs, shows the exact source segments behind each candidate, and
stores reviewer decisions in session state (optionally mirrored to disk when
the deployment filesystem is writable).
"""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent
DEMO_DIR = ROOT / "demo"
DATA_DIR = ROOT / "data"

st.set_page_config(
    page_title="Kuku Promo Discovery",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

DECISIONS = ["Not Reviewed", "Approved", "Rejected", "Needs Edit"]


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temp_path.replace(path)


def resolve_source():
    """Prefer real outputs when present, otherwise use the public demo."""

    force_demo = os.getenv("DEMO_MODE", "").strip().lower() in {"1", "true", "demo"}
    real_exports = DATA_DIR / "exports" / "ranked_promos.json"
    demo_exports = DEMO_DIR / "exports" / "ranked_promos.json"

    if not force_demo and real_exports.exists():
        return DATA_DIR / "processed", DATA_DIR / "exports", "local data pack"
    if demo_exports.exists():
        return DEMO_DIR / "processed", DEMO_DIR / "exports", "synthetic demo"
    return DATA_DIR / "processed", DATA_DIR / "exports", "missing"


PROCESSED_DIR, EXPORTS_DIR, SOURCE_LABEL = resolve_source()
RANKED_FILE = EXPORTS_DIR / "ranked_promos.json"
EPISODES_FILE = PROCESSED_DIR / "parsed_screenplays.json"
QUALITY_FILE = EXPORTS_DIR / "quality_check.json"
SUMMARY_FILE = EXPORTS_DIR / "batch4_summary.json"
AUDIT_FILE = EXPORTS_DIR / "requirements_check.json"
REVIEWS_FILE = PROCESSED_DIR / "human_reviews.json"


def load_candidates():
    data = read_json(RANKED_FILE, [])
    if isinstance(data, dict):
        data = data.get("candidates", [])
    return data


def load_episodes():
    data = read_json(EPISODES_FILE, [])
    if isinstance(data, dict):
        data = data.get("episodes", [])
    return data


def load_reviews():
    if "reviews" not in st.session_state:
        st.session_state.reviews = read_json(REVIEWS_FILE, {}) or {}
    return st.session_state.reviews


def save_review(promo_id, decision, notes):
    reviews = dict(load_reviews())
    reviews[promo_id] = {
        "decision": decision,
        "notes": notes.strip(),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }
    st.session_state.reviews = reviews
    try:
        write_json(REVIEWS_FILE, reviews)
        return True
    except OSError:
        # Streamlit Community Cloud can be read-only. Session state still
        # keeps the review for the current session and the download button
        # provides a durable copy.
        return False


def get_review_decision(candidate, reviews):
    return reviews.get(candidate.get("promo_id"), {}).get(
        "decision", "Not Reviewed"
    )


def get_segments(candidate, episode_map):
    embedded = candidate.get("source_segments") or []
    if embedded:
        return sorted(embedded, key=lambda s: float(s.get("start_seconds", 0)))

    episode = episode_map.get(int(candidate.get("episode_number", 0)), {})
    segment_map = {
        segment.get("segment_id"): segment
        for segment in episode.get("segments", [])
    }
    result = [
        segment_map[sid]
        for sid in candidate.get("source_segment_ids", [])
        if sid in segment_map
    ]
    return sorted(result, key=lambda s: float(s.get("start_seconds", 0)))


def score(candidate):
    return float((candidate.get("score_breakdown") or {}).get("final_score", 0))


def build_table(candidates, reviews):
    rows = []
    for candidate in candidates:
        scores = candidate.get("score_breakdown") or {}
        rows.append({
            "Rank": candidate.get("rank"),
            "Promo ID": candidate.get("promo_id"),
            "Episode": candidate.get("episode_number"),
            "Score": scores.get("final_score", 0),
            "Start": candidate.get("start_timestamp"),
            "End": candidate.get("end_timestamp"),
            "Duration": candidate.get("duration_seconds"),
            "Label": candidate.get("human_review_label"),
            "Validation": candidate.get("validation_status"),
            "Hook type": candidate.get("hook_type"),
            "Ending type": candidate.get("cliffhanger_type"),
            "Human decision": get_review_decision(candidate, reviews),
        })
    return pd.DataFrame(rows)


def render_candidate(candidate, episode_map, reviews, key_prefix=""):
    scores = candidate.get("score_breakdown") or {}
    st.markdown(f"### {candidate.get('title', 'Untitled')}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rank", candidate.get("rank"))
    col2.metric("Score", scores.get("final_score", 0))
    col3.metric("Duration", f"{candidate.get('duration_seconds', 0)}s")
    col4.metric("Episode", candidate.get("episode_number"))

    st.write(
        f"**Time:** {candidate.get('start_timestamp')} – "
        f"{candidate.get('end_timestamp')}"
    )
    st.write(
        f"**Machine label:** {candidate.get('human_review_label')} · "
        f"**Validation:** {candidate.get('validation_status')} · "
        f"**Analysis:** {candidate.get('analysis_mode')} · "
        f"**Score source:** {candidate.get('score_source')}"
    )
    if candidate.get("rank_reason"):
        st.caption(candidate["rank_reason"])

    st.markdown("#### Why it works")
    st.write(candidate.get("why_it_works") or candidate.get("promotional_justification"))

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Opening hook**")
        st.info(candidate.get("opening_hook") or "Not available")
    with col2:
        st.markdown("**Ending / cliffhanger**")
        st.warning(candidate.get("ending_cliffhanger_or_payoff") or "Not available")

    st.markdown("**Main dramatic moment**")
    st.write(candidate.get("main_dramatic_moment") or "Not available")

    st.markdown("#### Score breakdown")
    dimensions = [
        ("Hook Strength", "hook_strength"),
        ("Emotional Impact", "emotional_impact"),
        ("Suspense / Curiosity", "suspense_curiosity"),
        ("Cliffhanger / Payoff", "cliffhanger_payoff"),
        ("Standalone Clarity", "standalone_clarity"),
        ("Promotional Relevance", "promotional_relevance"),
    ]
    st.bar_chart(pd.DataFrame([
        {"Dimension": label, "Score": scores.get(key, 0)}
        for label, key in dimensions
    ]).set_index("Dimension"))

    st.markdown("#### Source screenplay evidence (ordered)")
    segments = get_segments(candidate, episode_map)
    if segments:
        st.dataframe(
            pd.DataFrame([
                {
                    "Segment ID": segment.get("segment_id"),
                    "Type": segment.get("segment_type"),
                    "Speaker": segment.get("speaker") or "",
                    "Start": segment.get("start_timestamp"),
                    "End": segment.get("end_timestamp"),
                    "Content": segment.get("content"),
                }
                for segment in segments
            ]),
            width="stretch",
            hide_index=True,
        )
    else:
        st.warning("No matching source segments were found.")

    issues = candidate.get("validation_issues") or []
    if issues:
        st.markdown("#### Validation warnings")
        for issue in issues:
            st.warning(issue)


# ---------------------------------------------------------
# DATA
# ---------------------------------------------------------

try:
    candidates = load_candidates()
    episodes = load_episodes()
    reviews = load_reviews()
    quality = read_json(QUALITY_FILE, {}) or {}
    summary = read_json(SUMMARY_FILE, {}) or {}
    audit = read_json(AUDIT_FILE, {}) or {}
except Exception as exc:
    st.error(f"Unable to load project data: {exc}")
    st.stop()

st.title("🎬 Kuku Promo Discovery")
st.caption(
    "Boundary-aware candidate generation, explainable ranking, "
    "and human triage. Scores are heuristics, not measured ad performance."
)
if SOURCE_LABEL == "synthetic demo":
    st.info(
        "You are viewing the **synthetic public demo** (8 hand-written "
        "episodes). The real input pack and its outputs are intentionally "
        "not published. The real-pack run produced 184 ranked candidates, "
        "40 of them above the internal Good threshold."
    )
elif SOURCE_LABEL == "missing":
    st.error(
        "No ranked output found. Run `python -m src.cli demo` for the public "
        "demo or `python -m src.cli run --zip ...` for the full pipeline."
    )
    st.stop()

episode_map = {
    int(episode["episode_number"]): episode for episode in episodes
}

# ---------------------------------------------------------
# FILTERS
# ---------------------------------------------------------

st.sidebar.header("🔎 Filters")
st.sidebar.caption(f"Data source: {SOURCE_LABEL}")

episode_numbers = sorted({int(c["episode_number"]) for c in candidates})
selected_episodes = st.sidebar.multiselect(
    "Episodes", options=episode_numbers, default=episode_numbers
)

all_scores = [score(c) for c in candidates] or [0.0]
score_range = st.sidebar.slider(
    "Score range",
    min_value=0.0,
    max_value=10.0,
    value=(0.0, 10.0),
    step=0.1,
)

validation_options = sorted({
    str(c.get("validation_status", "UNKNOWN")) for c in candidates
})
selected_validation = st.sidebar.multiselect(
    "Technical validation", options=validation_options, default=validation_options
)

machine_labels = sorted({
    str(c.get("human_review_label", "Unlabelled")) for c in candidates
})
selected_labels = st.sidebar.multiselect(
    "Quality label", options=machine_labels, default=machine_labels
)

selected_decisions = st.sidebar.multiselect(
    "Human review decision", options=DECISIONS, default=DECISIONS
)

search_text = st.sidebar.text_input(
    "Search title, hook, dialogue or reason",
    placeholder="Search screenplay moments…",
)

filtered = []
for candidate in candidates:
    searchable = " ".join([
        str(candidate.get("title", "")),
        str(candidate.get("opening_hook", "")),
        str(candidate.get("main_dramatic_moment", "")),
        str(candidate.get("ending_cliffhanger_or_payoff", "")),
        str(candidate.get("why_it_works", "")),
        str(candidate.get("dialogue", "")),
        str(candidate.get("characters", "")),
    ]).lower()

    if int(candidate["episode_number"]) not in selected_episodes:
        continue
    if not score_range[0] <= score(candidate) <= score_range[1]:
        continue
    if candidate.get("validation_status") not in selected_validation:
        continue
    if candidate.get("human_review_label") not in selected_labels:
        continue
    if get_review_decision(candidate, reviews) not in selected_decisions:
        continue
    if search_text.strip() and search_text.lower() not in searchable:
        continue
    filtered.append(candidate)

# ---------------------------------------------------------
# OVERVIEW
# ---------------------------------------------------------

tab_overview, tab_candidates, tab_quality, tab_review, tab_export = st.tabs([
    "📊 Overview",
    "🎞️ Candidates",
    "🧪 Quality Check",
    "📝 Human Review",
    "📥 Exports",
])

with tab_overview:
    st.subheader("Run overview")
    labels = quality.get("label_counts", {})
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Ranked promos", len(candidates))
    col2.metric("Episodes", len(episode_numbers))
    col3.metric("Good", labels.get("Good Promo", 0))
    col4.metric("Weak", labels.get("Weak Promo", 0))
    col5.metric("Bad", labels.get("Bad Promo", 0))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Duplicates removed", quality.get("duplicates_removed", 0))
    col2.metric(
        "Mid-dialogue cuts", quality.get("clips_ending_mid_dialogue", 0)
    )
    col3.metric("Mean score", quality.get("score_mean", 0))
    col4.metric(
        "Distinct durations", quality.get("duration_distinct_values", 0)
    )

    if audit:
        audit_status = audit.get("status", "UNKNOWN")
        st.caption(
            f"Brief requirements check: **{audit_status}** — "
            f"{audit.get('passed_checks', 0)}/"
            f"{audit.get('total_checks', 0)} hard checks passed "
            f"(duration, episode coverage, hooks, timestamps, source "
            f"segments, labels, ranking)."
        )

    st.divider()
    st.subheader("Post these first")
    st.caption(
        "Global score order. The first five are the clearest editorial bets, "
        "not a claim of measured performance."
    )
    top = summary.get("recommended_first") or [
        {
            "rank": c.get("rank"),
            "promo_id": c.get("promo_id"),
            "episode_number": c.get("episode_number"),
            "score": score(c),
            "reason": c.get("rank_reason"),
            "start": c.get("start_timestamp"),
            "end": c.get("end_timestamp"),
        }
        for c in candidates[:5]
    ]
    for item in top:
        st.markdown(
            f"**#{item['rank']} · {item['promo_id']} · Episode "
            f"{item['episode_number']} · {item['score']}/10**  \n"
            f"{item['start']}–{item['end']}  \n"
            f"{item['reason']}"
        )

    st.divider()
    st.subheader("Review progress")
    approved = sum(
        get_review_decision(c, reviews) == "Approved" for c in candidates
    )
    rejected = sum(
        get_review_decision(c, reviews) == "Rejected" for c in candidates
    )
    needs_edit = sum(
        get_review_decision(c, reviews) == "Needs Edit" for c in candidates
    )
    reviewed = approved + rejected + needs_edit
    st.progress(reviewed / len(candidates) if candidates else 0)
    st.caption(
        f"{reviewed} of {len(candidates)} candidates reviewed "
        f"({reviewed / len(candidates) if candidates else 0:.1%})"
    )
    st.bar_chart(pd.DataFrame([
        {"Decision": "Approved", "Count": approved},
        {"Decision": "Rejected", "Count": rejected},
        {"Decision": "Needs Edit", "Count": needs_edit},
        {"Decision": "Not Reviewed", "Count": len(candidates) - reviewed},
    ]).set_index("Decision"))

    st.info(quality.get("note", "Scores are heuristic ranking signals."))

# ---------------------------------------------------------
# CANDIDATES
# ---------------------------------------------------------

with tab_candidates:
    st.subheader("Ranked promo candidates")
    if not filtered:
        st.warning("No candidates match the selected filters.")
    else:
        st.dataframe(
            build_table(filtered, reviews),
            width="stretch",
            hide_index=True,
        )

        options = {
            (
                f"Rank {c.get('rank')} | Episode {c.get('episode_number')} | "
                f"{c.get('title', 'Untitled')} | {score(c)}/10 | "
                f"{c.get('promo_id')}"
            ): c
            for c in filtered
        }
        selected_key = st.selectbox(
            "Select a candidate to inspect", options=list(options.keys())
        )
        render_candidate(options[selected_key], episode_map, reviews)

# ---------------------------------------------------------
# QUALITY CHECK
# ---------------------------------------------------------

with tab_quality:
    st.subheader("Quality check — where it picks badly")
    st.caption(
        "This section is deliberately adversarial. The tool is a recall-oriented "
        "candidate generator, not an autonomous promo editor."
    )

    labels = quality.get("label_counts", {})
    st.bar_chart(pd.DataFrame([
        {"Label": key, "Count": value} for key, value in labels.items()
    ]).set_index("Label"))

    checks = [
        ("Clips ending mid-dialogue", "clips_ending_mid_dialogue"),
        ("Clips crossing scene boundaries", "clips_crossing_scene_boundaries"),
        ("Hooks of two words or fewer", "hooks_two_words_or_less"),
        ("Hooks starting after 3 seconds", "hooks_beyond_3_seconds"),
        ("Closure endings", "closure_endings"),
        ("Duplicates removed from ranked list", "duplicates_removed"),
        ("Distinct durations", "duration_distinct_values"),
    ]
    st.dataframe(
        pd.DataFrame([
            {"Check": label, "Value": quality.get(key, 0)}
            for label, key in checks
        ]),
        width="stretch",
        hide_index=True,
    )

    if audit:
        st.markdown("#### Hard brief requirements")
        st.caption(
            "These are admissibility checks, not quality judgements. A "
            "failed check means the output is not usable as specified."
        )
        checks_rows = audit.get("checks") or []
        st.dataframe(
            pd.DataFrame([
                {
                    "Requirement": check.get("requirement"),
                    "Result": "PASS" if check.get("passed") else "FAIL",
                    "Detail": check.get("detail"),
                }
                for check in checks_rows
            ]),
            width="stretch",
            hide_index=True,
        )

    st.markdown("#### Concrete bad picks")
    bad = quality.get("bad_pick_examples") or []
    if bad:
        for item in bad:
            st.markdown(
                f"**Rank {item['rank']} · {item['promo_id']} · "
                f"{item['score']}/10 · {item['label']}**  \n"
                f"Hook: “{item.get('opening_hook', '')}”  \n"
                f"Ending: “{item.get('ending', '')}”  \n"
                f"{item['why_it_fails']}"
            )
    else:
        st.info(
            "No candidate fell below the weak threshold in this run. That is "
            "not proof of quality; it means the scorer needs a harder gold set."
        )

    st.markdown("#### Known limitations")
    st.markdown(
        "- The scorer is keyword- and boundary-based. It does not understand "
        "irony, performance, or visual payoff.\n"
        "- A clip can still cross a scene boundary when the strongest beat "
        "spans two scenes.\n"
        "- `Good Promo` means it cleared an internal threshold, not that a "
        "human editor approved it.\n"
        "- The public demo is synthetic; the real-pack outputs are for the "
        "evaluator only."
    )

# ---------------------------------------------------------
# HUMAN REVIEW
# ---------------------------------------------------------

with tab_review:
    st.subheader("Human review workspace")
    if not filtered:
        st.warning("No candidates available for review with these filters.")
    else:
        review_options = {
            (
                f"Rank {c.get('rank')} | Episode {c.get('episode_number')} | "
                f"{c.get('title', 'Untitled')} | {c.get('promo_id')}"
            ): c
            for c in filtered
        }
        review_key = st.selectbox(
            "Choose a promo to review",
            options=list(review_options.keys()),
            key="review_candidate",
        )
        candidate = review_options[review_key]
        promo_id = candidate["promo_id"]
        current = reviews.get(promo_id, {})

        render_candidate(candidate, episode_map, reviews)

        st.markdown("#### Reviewer decision")
        with st.form("human_review_form"):
            decision = st.selectbox(
                "Decision",
                options=DECISIONS,
                index=DECISIONS.index(current.get("decision", "Not Reviewed"))
                if current.get("decision") in DECISIONS else 0,
            )
            notes = st.text_area(
                "Reviewer notes",
                value=current.get("notes", ""),
                placeholder=(
                    "Explain why this promo is approved, rejected, or needs editing…"
                ),
                height=120,
            )
            submitted = st.form_submit_button(
                "💾 Save human review", type="primary"
            )
            if submitted:
                persisted = save_review(promo_id, decision, notes)
                if persisted:
                    st.success("Review saved to disk and session.")
                else:
                    st.warning(
                        "Review saved for this session. The deployment "
                        "filesystem is read-only; use the Exports tab to "
                        "download the review JSON."
                    )
                st.rerun()

# ---------------------------------------------------------
# EXPORTS
# ---------------------------------------------------------

with tab_export:
    st.subheader("Exports")
    current_reviews = load_reviews()
    approved_candidates = [
        c for c in candidates
        if get_review_decision(c, current_reviews) == "Approved"
    ]

    st.metric("Human-approved promos", len(approved_candidates))

    if approved_candidates:
        approved_json = json.dumps(
            [
                {
                    **candidate,
                    "human_review": current_reviews.get(
                        candidate.get("promo_id"), {}
                    ),
                }
                for candidate in approved_candidates
            ],
            indent=2,
            ensure_ascii=False,
        )
        st.download_button(
            "Download approved promos (JSON)",
            data=approved_json,
            file_name="approved_promos.json",
            mime="application/json",
        )

        buffer = io.StringIO()
        columns = [
            "promo_id", "rank", "episode_number", "title",
            "start_timestamp", "end_timestamp", "duration_seconds",
            "opening_hook", "ending_cliffhanger_or_payoff",
            "why_it_works", "final_score",
        ]
        writer = csv.DictWriter(buffer, fieldnames=columns)
        writer.writeheader()
        for candidate in approved_candidates:
            scores = candidate.get("score_breakdown") or {}
            row = {key: candidate.get(key, "") for key in columns}
            row["final_score"] = scores.get("final_score", "")
            writer.writerow(row)

        st.download_button(
            "Download approved promos (CSV)",
            data=buffer.getvalue().encode("utf-8-sig"),
            file_name="approved_promos.csv",
            mime="text/csv",
        )
    else:
        st.info(
            "No candidates have been approved yet. Review candidates in the "
            "Human Review tab first."
        )

    st.download_button(
        "Download all ranked promos (CSV)",
        data=(EXPORTS_DIR / "ranked_promos.csv").read_bytes()
        if (EXPORTS_DIR / "ranked_promos.csv").exists() else b"",
        file_name="ranked_promos.csv",
        mime="text/csv",
    )

    st.markdown("#### Review history")
    if current_reviews:
        st.dataframe(
            pd.DataFrame([
                {
                    "Promo ID": promo_id,
                    "Decision": review.get("decision"),
                    "Notes": review.get("notes"),
                    "Reviewed At": review.get("reviewed_at"),
                }
                for promo_id, review in current_reviews.items()
            ]),
            width="stretch",
            hide_index=True,
        )
        st.download_button(
            "Download review history (JSON)",
            data=json.dumps(current_reviews, indent=2, ensure_ascii=False),
            file_name="human_reviews.json",
            mime="application/json",
        )
    else:
        st.caption("No human reviews have been saved yet.")

