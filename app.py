
import json
import csv
import io
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import streamlit as st


# ---------------------------------------------------------
# PATHS AND CONFIGURATION
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parent
EXPORTS_DIR = ROOT / "data" / "exports"
PROCESSED_DIR = ROOT / "data" / "processed"

RANKED_FILE = EXPORTS_DIR / "ranked_promos.json"
EPISODES_FILE = PROCESSED_DIR / "parsed_screenplays.json"
REVIEWS_FILE = PROCESSED_DIR / "human_reviews.json"

DECISIONS = [
    "Not Reviewed",
    "Approved",
    "Rejected",
    "Needs Edit",
]

st.set_page_config(
    page_title="Kuku Promo Discovery",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------
# DATA HELPERS
# ---------------------------------------------------------

def read_json(path, default=None):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temp_path.replace(path)


def normalize_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_episodes():
    data = read_json(EPISODES_FILE, [])
    if isinstance(data, dict):
        data = data.get("episodes", [])
    return data


def load_candidates():
    data = read_json(RANKED_FILE, [])
    if isinstance(data, dict):
        data = data.get("candidates", [])
    return data


def load_reviews():
    data = read_json(REVIEWS_FILE, {})
    if not isinstance(data, dict):
        return {}
    return data


def save_review(promo_id, decision, notes):
    reviews = load_reviews()
    reviews[promo_id] = {
        "decision": decision,
        "notes": notes.strip(),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(REVIEWS_FILE, reviews)


def get_segments_for_candidate(candidate, episode_map):
    episode = episode_map.get(int(candidate["episode_number"]), {})
    segment_map = {
        segment.get("segment_id"): segment
        for segment in episode.get("segments", [])
    }

    result = []
    for segment_id in candidate.get("source_segment_ids", []):
        segment = segment_map.get(segment_id)
        if segment:
            result.append(segment)

    return sorted(
        result,
        key=lambda x: float(x.get("start_seconds", 0)),
    )


def get_review_decision(candidate, reviews):
    review = reviews.get(candidate.get("promo_id"), {})
    return review.get("decision", "Not Reviewed")


def build_candidate_table(candidates, reviews):
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
            "Validation": candidate.get("validation_status"),
            "Machine Label": candidate.get("human_review_label"),
            "Human Decision": get_review_decision(candidate, reviews),
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------
# INITIAL DATA LOADING
# ---------------------------------------------------------

st.title("🎬 Kuku Promo Discovery")
st.caption(
    "AI-assisted screenplay promo discovery, ranking and human review"
)

try:
    candidates = load_candidates()
    episodes = load_episodes()
    reviews = load_reviews()
except Exception as exc:
    st.error(f"Unable to load project data: {exc}")
    st.stop()

if not candidates:
    st.error(
        "No ranked candidates found. Run "
        "`python -m src.discovery.run_batch4` first."
    )
    st.stop()

episode_map = {
    int(episode["episode_number"]): episode
    for episode in episodes
}

# ---------------------------------------------------------
# SIDEBAR FILTERS
# ---------------------------------------------------------

st.sidebar.header("🔎 Filters")

episode_numbers = sorted({
    int(c["episode_number"]) for c in candidates
})

selected_episodes = st.sidebar.multiselect(
    "Episodes",
    options=episode_numbers,
    default=episode_numbers,
)

min_score_available = min(
    float(c.get("score_breakdown", {}).get("final_score", 0))
    for c in candidates
)
max_score_available = max(
    float(c.get("score_breakdown", {}).get("final_score", 0))
    for c in candidates
)

score_range = st.sidebar.slider(
    "Minimum and maximum score",
    min_value=0.0,
    max_value=10.0,
    value=(
        float(min_score_available),
        float(max_score_available),
    ),
    step=0.1,
)

validation_options = sorted({
    str(c.get("validation_status", "UNKNOWN"))
    for c in candidates
})

selected_validation = st.sidebar.multiselect(
    "Technical validation",
    options=validation_options,
    default=validation_options,
)

machine_labels = sorted({
    str(c.get("human_review_label", "Unlabelled"))
    for c in candidates
})

selected_machine_labels = st.sidebar.multiselect(
    "Machine recommendation",
    options=machine_labels,
    default=machine_labels,
)

selected_decisions = st.sidebar.multiselect(
    "Human review decision",
    options=DECISIONS,
    default=DECISIONS,
)

search_text = st.sidebar.text_input(
    "Search title, hook or dialogue",
    placeholder="Search screenplay moments...",
)

# ---------------------------------------------------------
# APPLY FILTERS
# ---------------------------------------------------------

filtered_candidates = []

for candidate in candidates:
    episode_number = int(candidate["episode_number"])
    score = float(
        candidate.get("score_breakdown", {}).get("final_score", 0)
    )

    searchable = " ".join([
        str(candidate.get("title", "")),
        str(candidate.get("opening_hook", "")),
        str(candidate.get("main_dramatic_moment", "")),
        str(candidate.get("ending_cliffhanger_or_payoff", "")),
        str(candidate.get("dialogue", "")),
        str(candidate.get("characters", "")),
    ]).lower()

    if episode_number not in selected_episodes:
        continue
    if not score_range[0] <= score <= score_range[1]:
        continue
    if candidate.get("validation_status") not in selected_validation:
        continue
    if candidate.get("human_review_label") not in selected_machine_labels:
        continue
    if get_review_decision(candidate, reviews) not in selected_decisions:
        continue
    if search_text.strip() and search_text.lower() not in searchable:
        continue

    filtered_candidates.append(candidate)

# ---------------------------------------------------------
# OVERVIEW METRICS
# ---------------------------------------------------------

total_candidates = len(candidates)
approved_count = sum(
    get_review_decision(c, reviews) == "Approved" for c in candidates
)
rejected_count = sum(
    get_review_decision(c, reviews) == "Rejected" for c in candidates
)
pending_count = sum(
    get_review_decision(c, reviews) == "Not Reviewed" for c in candidates
)
needs_edit_count = sum(
    get_review_decision(c, reviews) == "Needs Edit" for c in candidates
)

tab_overview, tab_candidates, tab_review, tab_export = st.tabs([
    "📊 Overview",
    "🎞️ Candidates",
    "📝 Human Review",
    "📥 Exports",
])

with tab_overview:
    st.subheader("Project Overview")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Candidates", total_candidates)
    col2.metric("Episodes", len(episode_map))
    col3.metric("Approved", approved_count)
    col4.metric("Awaiting Review", pending_count)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rejected", rejected_count)
    col2.metric("Needs Edit", needs_edit_count)
    col3.metric(
        "Technically Valid",
        sum(c.get("validation_status") == "VALID" for c in candidates),
    )
    col4.metric("Filtered Results", len(filtered_candidates))

    st.divider()

    st.subheader("Human Review Progress")

    reviewed_count = (
        approved_count + rejected_count + needs_edit_count
    )
    progress = reviewed_count / total_candidates if total_candidates else 0

    st.progress(progress)
    st.caption(
        f"{reviewed_count} of {total_candidates} candidates reviewed "
        f"({progress:.1%})"
    )

    decision_data = pd.DataFrame([
        {"Decision": "Approved", "Count": approved_count},
        {"Decision": "Rejected", "Count": rejected_count},
        {"Decision": "Needs Edit", "Count": needs_edit_count},
        {"Decision": "Not Reviewed", "Count": pending_count},
    ])

    st.subheader("Review Decision Distribution")
    st.bar_chart(decision_data.set_index("Decision"))

    st.subheader("Top Ranked Candidates")

    overview_table = build_candidate_table(candidates[:10], reviews)
    st.dataframe(overview_table, use_container_width=True, hide_index=True)

    st.info(
        "Scores are deterministic heuristic ranking signals. "
        "They do not represent measured promotional performance."
    )


# ---------------------------------------------------------
# CANDIDATE EXPLORER
# ---------------------------------------------------------

with tab_candidates:
    st.subheader("Ranked Promo Candidates")

    if not filtered_candidates:
        st.warning("No candidates match the selected filters.")
    else:
        table = build_candidate_table(filtered_candidates, reviews)
        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
        )

        candidate_options = {
            (
                f"Rank {c.get('rank')} | Episode {c.get('episode_number')} | "
                f"{c.get('title', 'Untitled')} | "
                f"{c.get('score_breakdown', {}).get('final_score', 0)}/10"
            ): c
            for c in filtered_candidates
        }

        selected_key = st.selectbox(
            "Select a candidate to inspect",
            options=list(candidate_options.keys()),
        )

        selected_candidate = candidate_options[selected_key]

        st.divider()
        st.markdown(f"### {selected_candidate.get('title', 'Untitled')}")

        col1, col2, col3 = st.columns(3)
        col1.metric("Episode", selected_candidate["episode_number"])
        col2.metric(
            "Score",
            selected_candidate.get("score_breakdown", {}).get("final_score", 0),
        )
        col3.metric(
            "Duration",
            f"{selected_candidate.get('duration_seconds', 0)} sec",
        )

        st.write(
            f"**Time:** {selected_candidate.get('start_timestamp')} – "
            f"{selected_candidate.get('end_timestamp')}"
        )
        st.write(
            f"**Machine recommendation:** "
            f"{selected_candidate.get('human_review_label')}"
        )
        st.write(
            f"**Technical validation:** "
            f"{selected_candidate.get('validation_status')}"
        )

        st.markdown("#### Promo Narrative")
        st.write("**Opening hook**")
        st.write(selected_candidate.get("opening_hook", "Not available"))

        st.write("**Main dramatic moment**")
        st.write(
            selected_candidate.get(
                "main_dramatic_moment", "Not available"
            )
        )

        st.write("**Ending / cliffhanger**")
        st.write(
            selected_candidate.get(
                "ending_cliffhanger_or_payoff", "Not available"
            )
        )

        st.write("**Promotional justification**")
        st.write(
            selected_candidate.get(
                "promotional_justification", "Not available"
            )
        )

        st.markdown("#### Score Breakdown")
        score_data = selected_candidate.get("score_breakdown", {})

        score_rows = [
            {"Dimension": "Hook Strength", "Score": score_data.get("hook_strength", 0)},
            {"Dimension": "Emotional Impact", "Score": score_data.get("emotional_impact", 0)},
            {"Dimension": "Suspense / Curiosity", "Score": score_data.get("suspense_curiosity", 0)},
            {"Dimension": "Cliffhanger / Payoff", "Score": score_data.get("cliffhanger_payoff", 0)},
            {"Dimension": "Standalone Clarity", "Score": score_data.get("standalone_clarity", 0)},
            {"Dimension": "Promotional Relevance", "Score": score_data.get("promotional_relevance", 0)},
        ]

        st.bar_chart(pd.DataFrame(score_rows).set_index("Dimension"))

        st.markdown("#### Source Screenplay Evidence")
        source_segments = get_segments_for_candidate(
            selected_candidate,
            episode_map,
        )

        if source_segments:
            source_rows = []
            for segment in source_segments:
                source_rows.append({
                    "Segment ID": segment.get("segment_id"),
                    "Type": segment.get("segment_type"),
                    "Speaker": segment.get("speaker") or "",
                    "Start": segment.get("start_timestamp"),
                    "End": segment.get("end_timestamp"),
                    "Content": segment.get("content"),
                    "Source Line": segment.get("source_line"),
                })

            st.dataframe(
                pd.DataFrame(source_rows),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning("No matching source segments were found.")

        issues = selected_candidate.get("validation_issues") or []
        if issues:
            st.markdown("#### Validation Warnings")
            for issue in issues:
                st.warning(issue)


# ---------------------------------------------------------
# HUMAN REVIEW
# ---------------------------------------------------------

with tab_review:
    st.subheader("Human Review Workspace")

    review_candidates = [
        c for c in filtered_candidates
    ]

    if not review_candidates:
        st.warning("No candidates available for review with these filters.")
    else:
        review_options = {
            (
                f"Rank {c.get('rank')} | Episode {c.get('episode_number')} | "
                f"{c.get('title', 'Untitled')} | "
                f"{c.get('promo_id')}"
            ): c
            for c in review_candidates
        }

        review_key = st.selectbox(
            "Choose a promo to review",
            options=list(review_options.keys()),
            key="review_candidate",
        )

        candidate = review_options[review_key]
        promo_id = candidate["promo_id"]

        current_review = reviews.get(promo_id, {})
        current_decision = current_review.get(
            "decision", "Not Reviewed"
        )
        current_notes = current_review.get("notes", "")

        st.markdown(f"### {candidate.get('title', 'Untitled')}")
        st.write(
            f"Episode {candidate.get('episode_number')} | "
            f"{candidate.get('start_timestamp')} – "
            f"{candidate.get('end_timestamp')}"
        )
        st.write("**Opening:**", candidate.get("opening_hook", ""))
        st.write("**Ending:**", candidate.get("ending_cliffhanger_or_payoff", ""))

        st.write(
            "**Machine label:**",
            candidate.get("human_review_label", "Not labelled"),
        )
        st.write(
            "**Heuristic score:**",
            candidate.get("score_breakdown", {}).get("final_score", 0),
        )

        with st.form("human_review_form"):
            decision = st.selectbox(
                "Your review decision",
                options=DECISIONS,
                index=DECISIONS.index(current_decision)
                if current_decision in DECISIONS else 0,
            )

            notes = st.text_area(
                "Reviewer notes",
                value=current_notes,
                placeholder=(
                    "Explain why this promo is approved, rejected, "
                    "or needs editing..."
                ),
                height=120,
            )

            submitted = st.form_submit_button(
                "💾 Save Human Review",
                type="primary",
            )

            if submitted:
                save_review(promo_id, decision, notes)
                st.success("Human review saved successfully.")
                st.rerun()


# ---------------------------------------------------------
# EXPORTS
# ---------------------------------------------------------

with tab_export:
    st.subheader("Export Human-Reviewed Promos")

    current_reviews = load_reviews()

    approved_candidates = [
        c for c in candidates
        if get_review_decision(c, current_reviews) == "Approved"
    ]

    st.metric("Human-Approved Promos", len(approved_candidates))

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
            "⬇️ Download Approved Promos (JSON)",
            data=approved_json,
            file_name="approved_promos.json",
            mime="application/json",
        )

        csv_buffer = io.StringIO()
        columns = [
            "promo_id",
            "rank",
            "episode_number",
            "title",
            "start_timestamp",
            "end_timestamp",
            "duration_seconds",
            "opening_hook",
            "main_dramatic_moment",
            "ending_cliffhanger_or_payoff",
            "promotional_justification",
        ]

        writer = csv.DictWriter(csv_buffer, fieldnames=columns)
        writer.writeheader()

        for candidate in approved_candidates:
            writer.writerow({
                key: candidate.get(key, "")
                for key in columns
            })

        st.download_button(
            "⬇️ Download Approved Promos (CSV)",
            data=csv_buffer.getvalue().encode("utf-8-sig"),
            file_name="approved_promos.csv",
            mime="text/csv",
        )
    else:
        st.info(
            "No candidates have been approved yet. "
            "Review candidates in the Human Review tab first."
        )

    st.markdown("#### Review History")

    if current_reviews:
        history_rows = []
        for promo_id, review in current_reviews.items():
            history_rows.append({
                "Promo ID": promo_id,
                "Decision": review.get("decision"),
                "Notes": review.get("notes"),
                "Reviewed At": review.get("reviewed_at"),
            })

        st.dataframe(
            pd.DataFrame(history_rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("No human reviews have been saved yet.")
