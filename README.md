# Kuku Promo Discovery

Turn a pack of timestamped microdrama screenplays into ranked 20–60 second promo candidates, with the exact source segments, an explainable score, and an honest quality-check report.

This repository is the **Problem 1: Find the Promos** submission. It is a recall-oriented candidate generator plus a human-triage prototype. It is **not** an autonomous promo editor: the final choice stays with an editor.

**Latest real-pack run:** 50 episodes, 100 scenes and 3,727 segments → **184 ranked candidates** (40 Good / 121 Weak / 22 Bad / 1 Needs Review), 20.0–59.9s, **17/17 hard brief checks passed**. The run used the deterministic provider: 0 LLM calls.

---

## Open the prototype

Two ways, both work without the confidential input pack:

1. **Static prototype (no server):** open [`prototype/index.html`](prototype/index.html) in a browser. It is self-contained and uses synthetic demo data.
2. **Streamlit app:**
   ```powershell
   .\.venv\Scripts\python.exe -m streamlit run app.py
   ```
   Then open <http://localhost:8501>. If real outputs are not present, the app automatically falls back to `demo/`.

The public demo is synthetic. The real input pack and its outputs are not committed or published.

---

## Quick start (full pipeline)

```powershell
# 1. Install
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Run the whole pipeline: ZIP -> parsed -> candidates -> ranked exports
.\.venv\Scripts\python.exe -m src.cli run `
  --zip data/input/screenplays.zip `
  --provider local `
  --force `
  --raw-outputs raw_outputs

# 3. Open the review app
.\.venv\Scripts\python.exe -m streamlit run app.py
```

For the synthetic public demo:

```powershell
.\.venv\Scripts\python.exe -m src.cli demo
```

That writes `demo/`, rebuilds `prototype/index.html`, and packages demo outputs.

Re-rank existing candidates without re-parsing:

```powershell
.\.venv\Scripts\python.exe -m src.cli rank
```

By default the generator is recall-oriented and keeps weak candidates so the
quality-check report has something honest to inspect. Use `--min-score 6.5`
to keep only clips above the internal Good threshold:

```powershell
.\.venv\Scripts\python.exe -m src.cli run --zip data/input/screenplays.zip --provider local --min-score 6.5 --force
```

Run the tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

---

## What the pipeline does

```
data/input/screenplays.zip
        │
        ▼
ingestion/          parse episodes, scenes and every timestamped segment
        │
        ▼
discovery/           boundary-aware window generation
        │            starts and ends only on dialogue/action/scene boundaries
        ▼
AI or fallback       Gemini (optional) or deterministic local evaluation
        │            AI supplies text/scores only; Python owns timestamps
        ▼
validation/          duration, bounds, segment provenance, timestamp consistency
        │
        ▼
deduplication        remove overlapping windows, export them separately
        │
        ▼
ranking              global score order, quality labels, "post these first"
        │
        ▼
exports/             ranked JSON + self-contained CSV + quality-check report
        │
        ▼
app.py / prototype   human triage, review decisions, downloads
```

### Key design decisions

- **Boundary-aware, fully covered windows.** A window can only start or end on a dialogue, action or scene boundary, never strictly inside a spoken line, and must be fully covered by source segments. This is why the output has 130 distinct durations instead of hundreds of clips of exactly 30 seconds.
- **Non-overlapping selection.** The generator selects single-scene candidates first and only fills remaining slots with cross-scene clips. Duplicates are removed from the ranked list, not merely labelled.
- **Python owns time.** The model may write a title or explanation, but it cannot invent or change a timestamp.
- **Self-contained export.** Every candidate carries `source_segments` with ordered start/end timestamps, so the CSV/JSON can be checked without opening the input pack.
- **Honest labels.** `Good Promo` means the clip cleared an internal threshold. It is not a human approval and not a prediction of ad performance.
- **Global ranking.** Rank 1 has the highest score; the old per-episode round-robin is gone. This makes "post these first" defensible.

---

## Output files

After a run, `data/exports/` (and `raw_outputs/`) contains:

| File | Purpose |
|---|---|
| `ranked_promos.json` | Full ranked output, including ordered `source_segments` |
| `ranked_promos.csv` | Flat export with scores, reasons, and a `segment_timeline` column |
| `batch4_summary.json` | Run summary, label counts, top 5 "post first" |
| `quality_check.json` / `.md` | Honest failure analysis and bad-pick examples |
| `requirements_check.json` / `.md` | 17 machine-checked hard requirements (coverage, duration, hooks, timestamps, source segments, labels, ranking) |
| `rejected_candidates.json` | Overlapping duplicates removed from the ranked list |
| `discovery_summary.json` | Provider status and per-episode discovery results |
| `promo_analysis_metadata.json` | Per-candidate analysis provenance |
| `dataset_summary.json` | Parse-level counts and warnings |

Each ranked candidate includes:

- `promo_id`, `rank`, `episode_number`, `start_timestamp`, `end_timestamp`, `duration_seconds`
- `opening_hook`, `hook_type`, `main_dramatic_moment`, `ending_cliffhanger_or_payoff`, `cliffhanger_type`
- `why_it_works`, `promotional_justification`, `rank_reason`
- six explainable scores and `final_score`
- `source_segment_ids` and ordered `source_segments`
- `validation_status`, `human_review_label`, `analysis_mode`, `score_source`

---

## Quality check (the part that matters)

The tool is deliberately checked against its own output. The report identifies:

- label distribution (`Good` / `Weak` / `Bad`)
- clips ending mid-dialogue
- clips crossing scene boundaries
- hooks of two words or fewer
- hooks starting after three seconds
- closure endings
- duplicate candidates removed
- concrete bad-pick examples with the score breakdown that caused them

It also runs a separate **requirements audit** against the exported files. The audit is deliberately boring and hard: every episode must be covered, every clip must be 20–60s, every timestamp must agree with its seconds field, every source timeline must be ordered and cover the cut, every hook must land within 3s, no clip may cut mid-dialogue, ranks must be contiguous and score-ordered, labels must match thresholds, and the CSV must match the JSON. The current real-pack run passes **17/17**.

The current run is summarised in [`docs/solution.md`](docs/solution.md), `raw_outputs/quality_check.md` and `raw_outputs/requirements_check.md`. The short version: boundary snapping removed mid-dialogue and late-hook failures, but the ranker still picks some weak hooks and 17 cross-scene clips. Those failures are reported, not hidden.

---

## AI tools used

- **Gemini 2.5 Flash** is wired as an optional judge (`src/ai/gemini_provider.py`). It is used only when `GEMINI_API_KEY` is set and `AI_PROVIDER` is `gemini` or `auto`.
- **Local deterministic fallback** is the default in the submitted run because no API key was available. Every candidate in `raw_outputs/` is marked `DETERMINISTIC_FALLBACK`.
- **opencode (DeepSeek V4.1 Flash)** was used as the AI coding assistant to implement, review and debug the pipeline. One place it got it wrong: the first framing called the output "AI promo discovery" even though the final run used zero LLM calls. That overclaim was corrected in the UI, README and solution doc.

Do not claim the submitted run used an LLM when it did not. The provenance field is the source of truth.

### Swap the model

The provider interface is one method: `analyze(prompt) -> dict | None`.

```powershell
# deterministic, offline
$env:AI_PROVIDER="local"

# Gemini
$env:AI_PROVIDER="gemini"
$env:GEMINI_API_KEY="..."
$env:GEMINI_MODEL="gemini-2.5-flash"
```

To add another provider, copy `GeminiProvider`, implement `analyze()` and `status()`, and add one branch in `src/ai/provider_factory.py`. Timestamps and source evidence stay in Python.

---

## Prototype and deployment

The Streamlit app is deployable as-is. For Streamlit Community Cloud:

1. Push the repository (without `data/input/`, `data/processed/`, `data/exports/`).
2. Set the main file to `app.py`.
3. Add `GEMINI_API_KEY` only if you want the AI path; otherwise leave `AI_PROVIDER=local`.
4. The app falls back to `demo/` when real outputs are absent.

The static prototype is the safest public link because it contains only synthetic demo content. After cloning, open `prototype/index.html` or serve it:

```powershell
python -m http.server 8000
# http://localhost:8000/prototype/
```

A public URL requires the submitter's own hosting account; the repository includes everything needed for that deployment. See [`docs/DEPLOY.md`](docs/DEPLOY.md) for GitHub Pages, Streamlit Cloud and Docker steps.

---

## Confidentiality

- `.gitignore` excludes `data/input/*`, `data/processed/*`, `data/cache/*` and `data/exports/*`.
- `demo/` is synthetic and safe to publish.
- `raw_outputs/` contains excerpts from the real pack. It is **gitignored** and should be included in the evaluator's submission zip, not a public repository.
- `submission/` is gitignored because it bundles the real outputs.
- Do not commit `.env` or `screenplays.zip`.

Before publishing, run:

```powershell
git status --short
```

and confirm no file under `data/input/` or `data/processed/` is staged.

---

## Limitations / next steps

- The scorer is keyword- and boundary-based; it does not understand performance, irony, or visual payoff.
- 17 of 184 clips in the current run still cross a scene boundary. Single-scene clips are preferred, not guaranteed.
- 2 hooks are two words or fewer, and 121 of 184 candidates are weak. That is expected from a recall-oriented pass.
- The score ceiling is 7.57/10; a labelled gold set is needed before claiming precision.
- One parsing warning remains: `E022_S01_SEG0023` extends past its scene boundary, so that candidate is marked `NEEDS_REVIEW`.
- The current output is single-episode and continuous; multi-episode or stitched promos are not generated.
- Next step: 20–30 human-labelled clips, precision@5, a learned or LLM judge, and audio/visual beat detection.

---

## Repository map

```
app.py                      Streamlit human-triage app
prototype/index.html        self-contained public demo
src/cli.py                  end-to-end CLI
src/demo_data.py            synthetic demo screenplays
src/discovery/              window generation, discovery, dedup, ranking
src/scoring/scorer.py       explainable scoring
src/validation/             timestamp/provenance validation
src/quality/                hard brief-requirements audit
src/exports/                JSON/CSV exporters
src/ingestion/              parser and dataset processor
docs/solution.md            two-page solution document source
docs/solution.pdf           submitted two-page PDF
raw_outputs/                unedited run outputs (evaluator only)
tests/                      39 unit tests
```
