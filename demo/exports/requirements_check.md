# Problem 1 requirements check

**Status: PASS** — 17/17 checks passed.

| Check | Requirement | Result | Detail |
|---|---|---|---|
| has_candidates | The run produces at least one promo. | PASS | 9 ranked candidates. |
| all_episodes_covered | Every parsed episode contributes at least one candidate. | PASS | All episodes covered. |
| duration_20_60 | Every promo is 20-60 seconds long. | PASS | 9 clips in range. |
| timestamp_consistency | Start, end and duration agree in every candidate. | PASS | All timestamps are internally consistent. |
| source_segments_present | Every candidate names its ordered source segments. | PASS | All candidates embed source segments. |
| source_timeline_covers_clip | Embedded segments are ordered and cover the full clip. | PASS | All source timelines are ordered and clipped to the cut. |
| hook_present | Every promo states its opening hook. | PASS | All hooks present. |
| cliffhanger_present | Every promo states its cliffhanger or ending beat. | PASS | All endings present. |
| why_it_works_one_line | Every promo carries a one-line reason. | PASS | All one-line reasons present. |
| hook_within_3s | Every promo opens on a hook within the first 3 seconds. | PASS | All hooks land within 3.0s. |
| no_mid_dialogue_cut | No promo cuts in the middle of a spoken line. | PASS | No mid-dialogue cuts. |
| unique_ids | Promo IDs are unique. | PASS | 9 IDs, 9 unique. |
| ranking_is_global | Ranks are contiguous and ordered by score. | PASS | Global score order. |
| labels_match_scores | Quality labels agree with the configured thresholds. | PASS | Labels are threshold-consistent. |
| no_invalid_candidates | No candidate fails structural validation. | PASS | No invalid candidates. |
| csv_matches_json | The CSV contains exactly the ranked JSON candidates. | PASS | CSV and JSON match. |
| quality_report_present | The quality report exists and matches the run. | PASS | Quality report matches. |
