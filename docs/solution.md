# Kuku AI Generalist — Problem 1: Find the Promos

**Ayan Dhal** · Working prototype: `prototype/index.html` · Source: repository root  
**Scope:** ~2–3 hours · **Run:** 50 episodes → 193 ranked candidates

## 1. Why this problem, and how I framed it

I chose Problem 1 because it is the most measurable of the three: a promo either stops a scroll in the first three seconds, or it does not. The brief gives timestamped screenplays, so the output can be checked line by line instead of judged as a black box.

My framing is deliberately narrower than "build an AI that picks promos":

> **A recall-oriented candidate generator plus a human-triage tool.** The machine narrows 3,727 segments to 193 candidates and explains every choice; an editor makes the final call.

Assumptions: clips are 20–60s, single-episode, vertical short-form; the screenplay text is the only signal (no audio or video); the promo must make sense without prior context; the editor can reject or re-cut. I did not assume a posting schedule or a target platform beyond short-form.

## 2. Approach and scale

**Pipeline:** parse → boundary-aware window generation → local/Gemini evaluation → validation → de-duplication → global ranking → human review UI.

The important change from a naive baseline is **boundary awareness**. A candidate may only start or end on a dialogue, action or scene boundary, and never strictly inside a spoken line. Durations are chosen from real boundaries rather than a fixed timer, single-scene clips are preferred, and selected clips in an episode cannot overlap by more than 40%. Python owns every timestamp; the model may only supply text and scores. Each candidate embeds its ordered `source_segments`, so the CSV/JSON is self-contained.

**Scale:** 50 episodes, 100 scenes, 3,727 segments, 193 candidates. Parsing and ranking run locally in under a minute; discovery is cached per episode by source hash. The submitted run used the deterministic provider, so API cost and latency were zero. The optional Gemini path uses one request per episode, is capped at 10 requests per run and 5s between calls, and stores provenance per candidate.

**Model swap:** `AI_PROVIDER=local|gemini|auto`; the interface is `analyze(prompt) -> dict | None`. Adding a provider is one file plus one branch in `provider_factory.py`.

## 3. Quality check: what works, and where it picks badly

The tool is judged against its own output. The latest real-pack run produced:

| Metric | Result |
|---|---|
| Ranked candidates | **193** |
| Good / Weak / Bad / Needs review | **46 / 131 / 15 / 1** |
| Score range (mean) | **3.89–7.75 (5.77)** |
| Duration range / distinct values | **20.0–59.6s / 137** |
| Clips ending mid-dialogue | **0** |
| Clips crossing scene boundaries | **15** |
| Hooks of two words or fewer | **2** |
| Duplicates left in ranked list | **0** |
| Gemini requests in submitted run | **0** |

This is a real improvement over the baseline I audited: 250 candidates, all exactly 30s, **0 Good**, 165 repetitive, 152 mid-dialogue cuts, and one identical justification for every row. Boundary snapping removed the mid-line cuts; non-overlap selection plus de-duplication removed the repetitive rows; the scorer now produces a usable spread instead of a ceiling of 5.32.

**Post these first (global score order):**

1. `E027_W0001` — 7.75 — 00:03.40–00:55.60. Opens on a direct accusation ("Who gave this to you?") and ends on a new witness entering the private chamber.
2. `E001_W0001` — 7.57 — 01:15.00–01:47.30. A public humiliation with a clean unanswered question: "And I am what?"
3. `E015_W0001` — 7.53 — 00:08.50–00:55.70. Starts on a physical interruption and ends on a possessive, unresolved line.
4. `E044_W0001` — 7.53 — 00:28.40–01:10.40. A direct emotional accusation; the final "Her?!" is a reaction shot in text.
5. `E034_W0001` — 7.50 — 00:49.10–01:38.00. A truth demand and a townsman's testimony that opens a new question.

**Where it still picks badly — concrete examples:**

- **Rank 193, `E040_W0004` (3.89, Bad Promo).** Opens on "This place has always been unlucky for Juliana" and ends on "Everything must go perfectly." Neither line creates a question, and the window crosses three scenes. The scorer sees low hook (3.7) and low cliffhanger (3.3) but still exports it because the candidate generator is recall-oriented.
- **Rank 192, `E017_W0005` (3.96, Bad Promo).** "You were bleeding last night" is a decent hook, but "Of them?" is too context-dependent to work standalone. The clarity score does not know that the pronoun has no referent.
- **Rank 191, `E040_W0003` (3.98, Bad Promo).** The opening is a 23-word camera direction, not a spoken hook. The scorer rewards action but cannot tell that a description of doors is not a scroll-stopper.

The remaining weaknesses are honest ones: 15 clips still cross a scene boundary, 2 hooks are two words or fewer, and 131 of 193 are weak. The scorer is keyword- and boundary-based; it does not understand irony, performance, or visual payoff. `Good Promo` means "cleared an internal threshold", not "a human approved it".

## 4. AI tools used, and one place they got it wrong

- **Gemini 2.5 Flash** is wired as an optional judge. It was **not used in the submitted run** because no API key was available: all 193 candidates are `DETERMINISTIC_FALLBACK`, `requests_used=0`. The UI and provenance say so; I did not label heuristic output as AI analysis.
- **AI coding assistant** was used to implement, review and debug the pipeline. One place it got it wrong: the first version framed the output as "AI promo discovery" while the final run made zero LLM calls. That was an overclaim, and it is corrected in the UI, README and this document. A second early mistake was the fixed 30-second window, which cut dialogue mid-sentence; that design was replaced with boundary snapping.

When Gemini is enabled, a `false` verdict skips the window instead of silently promoting it; a `true` verdict supplies text and scores; a failed or malformed response falls back to the deterministic provider. AI never supplies timestamps.

## 5. What I would do next

1. **Build a small gold set:** 20–30 clips from 5 episodes, human-labelled good/bad, and report precision@5 and recall per episode. This is the missing measurement, not another scoring tweak.
2. **Add a learned hook/cliff judge** trained on those labels, and use Gemini only for the top ~50 candidates to control cost.
3. **Improve boundaries with audio/visual beats** when those tracks exist; the screenplay text cannot tell a pause from a cut.
4. **Add series-arc and cross-episode promos**; the current output is single-episode by design.
5. **Persist human reviews in a database** rather than a local JSON file, so the triage tool works for a team.

## 6. Reproducibility and deliverables

```powershell
python -m src.cli run --zip data/input/screenplays.zip --provider local --force --raw-outputs raw_outputs
python -m src.cli demo            # synthetic public demo + prototype/index.html
python -m streamlit run app.py    # human review UI
python -m pytest -q               # 29 tests, all passing
```

Deliverables: this 2-page PDF, `raw_outputs/` (unedited ranked JSON/CSV, quality check, rejected duplicates, run metadata), `prototype/index.html` (self-contained synthetic demo), `app.py` (Streamlit triage UI), and a README with exact run steps. The input pack is not committed; `.gitignore` excludes `data/input/`, `data/processed/`, `data/cache/` and `data/exports/`.
