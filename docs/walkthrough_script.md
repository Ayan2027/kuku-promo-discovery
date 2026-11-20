# 3-minute walkthrough script (optional)

**Goal:** show the problem framing, the prototype, and one honest failure in under three minutes.

| Time | Screen | Narration |
|---|---|---|
| 0:00–0:20 | `docs/solution.pdf` page 1 | "I chose Problem 1 because it is measurable: a promo either stops a scroll in three seconds or it does not. I framed the tool as a candidate generator plus human triage, not an autonomous editor." |
| 0:20–0:45 | `prototype/index.html` overview | "This is the public synthetic demo. The real run parsed 50 episodes and 3,727 segments into 184 candidates. These are the top five to post first, in global score order." |
| 0:45–1:15 | Candidate detail, `E001_W0001` | "Every card explains the hook, the ending, the six scores, and the exact source segments. Python owns the timestamps; the model only writes text." |
| 1:15–1:40 | Source-segment table | "This is the key safety property: the editor can audit the clip line by line. The clip starts on a public accusation and cuts on "And I am what?"" |
| 1:40–2:05 | Quality check tab | "The tool is judged against its own output. 40 clips cleared the Good threshold, 121 are weak, 22 are bad, and one needs review. Zero clips cut mid-dialogue and zero open after three seconds, down from 152 mid-dialogue cuts in the baseline." |
| 2:05–2:30 | Bad pick `E040_W0004` | "Here is a bad pick. The hook is low-energy and the window crosses three scenes. The scorer sees that, but the candidate generator is recall-oriented, so the editor still has to reject it." |
| 2:30–2:50 | README / CLI | "The whole pipeline is one command. `AI_PROVIDER=local` is fully offline; `AI_PROVIDER=gemini` swaps the judge without changing timestamps or the UI." |
| 2:50–3:00 | `docs/solution.pdf` page 2 | "The next step is a 20–30 clip gold set and precision@5. That is the missing measurement, not another scoring tweak." |

**Recording tips**

- Record at 1280×720 or larger; hide bookmarks and personal tabs.
- Use the synthetic demo, never the confidential input pack.
- Keep the mouse still while speaking; cut between tabs instead of scrolling.
- End on the quality-check table, not on the happy path.
