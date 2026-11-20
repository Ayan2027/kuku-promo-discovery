# Kuku AI Generalist — Problem 1: Find the Promos

**Ayan Dhal** · Prototype: `prototype/index.html` (self-contained) · Review UI: `app.py`
**Run:** 50 episodes → 3,727 segments → 184 ranked candidates · **Cost:** $0, no LLM calls

## 1. Why this problem, and how I framed it

I chose Problem 1 because it is the most measurable of the three: a promo either stops a scroll in the first three seconds or it does not. The brief supplies timestamped screenplays, so every pick can be checked line by line instead of judged as a black box.

My framing is narrower than “build an AI that picks promos”:

> **A recall-oriented candidate generator plus a human-triage tool.** The machine narrows 3,727 segments to 184 candidates and explains every choice; an editor makes the final call.

Assumptions: clips are 20–60s and single-episode; the screenplay text is the only signal (no audio or video); a promo must make sense without prior context; the editor can reject or re-cut. I did not assume a posting schedule or a target platform beyond short-form. The current tool does not build multi-episode or stitched promos.

## 2. How it works

**Pipeline:** parse → boundary-aware window generation → local/Gemini evaluation → validation → de-duplication → global ranking → human review.

The important design choice is **boundary awareness**. A candidate may only start or end on a dialogue, action or scene boundary, never strictly inside a spoken line. Durations come from real boundaries, not a fixed timer. A window must also be fully covered by source segments, so scene metadata cannot create dead air; and the first story beat must land within the required three seconds. Python owns every timestamp; the model may only supply text and scores. Each candidate embeds its ordered `source_segments`, so the CSV/JSON is self-contained.

The submitted run used the deterministic provider: all 184 candidates are `DETERMINISTIC_FALLBACK`, `requests_used=0`. The optional Gemini judge is one request per episode, capped at 10 requests per run. A `false` verdict skips a window instead of silently promoting it; a failed response falls back to the deterministic path. Adding a provider is one file plus one branch in `provider_factory.py`.

## 3. Which promos to post first, and why

Global score order, not a per-episode rotation. The first five are the clearest editorial bets:

1. `E001_W0001` — 7.57 — 01:15.00–01:47.30. Public humiliation opens on “Long enough to know he was never going to marry you” and cuts on “And I am what?”.
2. `E015_W0001` — 7.53 — 00:08.50–00:55.70. Opens on “Stop! What are you doing?!” and ends on the unresolved “My mother's plants…”.
3. `E044_W0001` — 7.53 — 00:28.40–01:10.40. A direct emotional accusation, then the reaction “Her?!”.
4. `E034_W0001` — 7.50 — 00:49.10–01:38.00. “Tell the truth” opens a testimony that ends on an unfinished story.
5. `E002_W0001` — 7.39 — 00:24.00–01:19.00. A confrontation about being replaced, cut before the answer lands.

These rank first because they combine a self-contained first three seconds, escalating conflict, and an ending that opens a question rather than closing one.

## 4. Quality check: what works, and where it picks badly

The output is checked two ways: an automated **requirements audit** (17 hard checks on the exported files) and an honest **editorial quality report**.

| Metric | Result |
|---|---|
| Ranked candidates | **184** |
| Episodes covered | **50 / 50** |
| Good / Weak / Bad / Needs review | **40 / 121 / 22 / 1** |
| Score range (mean) | **3.65–7.57 (5.66)** |
| Duration range / distinct values | **20.0–59.9s / 130** |
| Hard requirements passed | **17 / 17** |
| Mid-dialogue cuts / late hooks | **0 / 0** |
| Cross-scene clips / hooks ≤2 words | **17 / 2** |
| Gemini calls in this run | **0** |

**Concrete bad picks:**

- **Rank 184, `E019_W0005` (3.65).** Opens on “This was our home” and ends on “Take it.” Neither line creates a question. The scorer rates hook 3.7 and ending 2.5 but still exports it because the generator is recall-oriented.
- **Rank 183, `E040_W0004` (3.89).** “This place has always been unlucky” is low-energy, “Everything must go perfectly” is closure, and the window crosses three scenes.
- **Rank 182, `E018_W0005` (3.91).** The hook is the one-word “Alexander!”, so it scores 0.2/10. A one-word cry can work on screen, but the text scorer cannot tell a scream from a shrug.

Honest limits: 17 clips still cross a scene boundary; 2 hooks are two words or fewer; 121 of 184 are weak; one candidate needs review because a source segment extends past its scene (`E022_S01_SEG0023`). The scorer is keyword- and boundary-based. It does not understand irony, performance, or visual payoff. `Good Promo` means “cleared an internal threshold”, not “a human approved it”. The public demo is synthetic; the real-pack outputs are in `raw_outputs/` for the evaluator.

## 5. AI tools used, and one place they got it wrong

- **opencode (DeepSeek V4.1 Flash)** was used as the AI coding assistant to implement, review and debug the pipeline.
- **Gemini 2.5 Flash** is wired as an optional judge. It was **not used** in the submitted run: no API key was configured, all 184 candidates are `DETERMINISTIC_FALLBACK`, and `requests_used=0`. The UI and provenance say so.
- One place the assistant got it wrong: its first framing called the output “AI promo discovery” while the run made zero LLM calls. That was an overclaim; it is corrected in the UI, README and this document. An earlier design also used a fixed 30-second window that cut dialogue mid-sentence; it was replaced with boundary snapping.

What I kept as code/rules: timestamps, boundary generation, coverage, scoring, validation, de-duplication, ranking and the hard requirements audit. What AI may do: optional per-episode text and scores. A human still approves every promo.

## 6. Scaling to every show

The pipeline is per-episode and cached by a hash of the source text. This run parses and ranks 50 episodes in about a minute on a laptop with zero API cost. For weekly shows the batch CLI is the unit of scale; for hundreds or thousands of episodes, run episodes in parallel, keep the deterministic audit as a gate, and send only the top ~50 candidates to an LLM judge. The expensive model never touches timestamps, so its cost is bounded by candidate volume, not screenplay volume. Human review remains the final step, and its decisions can later become a labelled gold set.

## 7. What I would do next

1. **Build a gold set:** 20–30 clips from 5 episodes, human-labelled good/bad, then report precision@5 and recall per episode. This is the missing measurement, not another scoring tweak.
2. **Add a learned hook/cliff judge** trained on those labels; use Gemini only for the top ~50 candidates.
3. **Improve boundaries with audio/visual beats** when those tracks exist.
4. **Add cross-episode and stitched promos**; the current output is single-episode by design.
5. **Persist human reviews in a database** so the triage tool works for a team.

## 8. Reproducibility and deliverables

```powershell
python -m src.cli run --zip data/input/screenplays.zip `
  --provider local --force --raw-outputs raw_outputs
python -m src.cli demo            # synthetic public demo + prototype/index.html
python -m streamlit run app.py    # human review UI
python -m pytest -q               # 39 tests, all passing
```

Deliverables: this 2-page PDF, `raw_outputs/` (ranked JSON/CSV, quality check, requirements audit, rejected duplicates, run metadata), `prototype/index.html` (self-contained synthetic demo), `app.py` (Streamlit triage UI), and a README with exact run steps. The input pack is not committed.
