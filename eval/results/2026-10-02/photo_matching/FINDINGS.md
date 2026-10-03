# Photo-matching test · findings (PLAN_NOW step 1)

**Question:** can a visitor's photo be matched to the right panel in our collection, and is a panel that is NOT in
the collection rejected (never guess)?

**Setup** (`scripts/match_test.py`, matcher `nun/match/matcher.py`):
- Collection: 150 Commons panel photos (`data/panels/raw`).
- Visitor photos: **simulated**, 3 per panel (easy / medium / hard: perspective up to 15%, rotation up to 15°, wall
  around the panel, up to 30% of the panel cut off, light 0.4–1.4×, glare, blur, noise, JPEG 40–90). A stand-in:
  every simulated photo starts from the collection's own pixels, so real repeat photos (other day, other lens) are
  harder. Real photos dropped into `data/match_test/real_queries/` are scored too (0 so far).
- Unknown panels (must be rejected): 598 other Commons calligraphy photos + 195 FIC images (internal only), after
  removing 51 that are the same image as a collection photo.
- Method: DINOv2-small shortlist (top 10) → RootSIFT + RANSAC homography → accept only if **≥ 20 inliers AND ≥ 40%
  centre coverage** (inliers spread over the middle 60% of the panel, where the text is).

**Results** (inliers ≥ 20, centre coverage ≥ 0.4):

| | Easy | Medium | Hard |
|---|---|---|---|
| Matched to the right panel | **100%** | **98.7%** | **92.7%** |
| Matched to a WRONG panel | 0 | 0 | 0 |
| Rejected ("couldn't identify") | 0% | 1.3% | 7.3% |

- Unknown panels accepted: **3 of 793, and all 3 are the same physical panel as a collection photo** (another
  photographer's photo of the same carved panel, the same tile with a different colour balance, the same inscription
  inside a wider wall photo): checked by eye, so **0 genuine false matches**. They are also the test's only REAL
  repeat photos, and all three matched.
- Embedding alone (no verification) picks the right panel 95% / 91% / 84% of the time and cannot say "unknown".
- Latency: 0.42 s p50, 0.56 s p95 per photo (RTX 5090; collection of 150; index build 24 s).

**What changed during the test (and why it matters):** with inlier counts alone, 42 unknown images were accepted,
up to 1,569 inliers. Looking at them showed different name roundels built on the **same ornamental frame
template**, and black-on-white text pages matching by chance. Buildings reuse frames, borders and tile patterns, so
a matcher that matches the frame would show the wrong verse. The centre-coverage check (agreement must also cover the
text area) removed all of them while keeping 92–100% of correct matches.

**Limits:** simulated photos; a single collection photo per panel; collection of 150. Before Oct 4: replace the
simulated queries with the team's own repeat photos (2–3 phone photos per panel on another day, other distance and
angle) and re-run; if real photos fall below these numbers, add a second collection photo per panel.

## Update 2026-10-03 · the team's panels and first real phone photos
Collection 171 = 150 Commons + 21 team panels (18 demo artworks with team-checked text, 3 real wall panels;
`data/real_test/`, git-ignored). Same thresholds (≥ 20 inliers, ≥ 40% centre coverage).

| Real phone photo | Result | Inliers | Centre coverage |
|---|---|---|---|
| Ayat al-Kursi wall panel, photo 1 | right panel | 1,272 | 0.94 |
| Ayat al-Kursi wall panel, photo 2 | right panel | 2,180 | 1.00 |
| testing-only panel (93:5) | right panel | **40** | **0.44**: only just above the 0.40 threshold |
| testing-only panel (3:170) | right panel | 103 | 0.69 |
| panel NOT in the collection (48:1) | rejected (correct) | 5 | 0.06 |

**5/5 correct** (4 right, 1 correctly rejected). Simulated photos with 171 panels: 100% / 98.2% / 94.2%
(easy/medium/hard), 0 wrong; the 21 team panels 21/21 at every level. Unknown panels accepted: the same 3 as before,
all the same physical panel (checked). p50 0.50 s.
Watch: the 93:5 photo passed by a small margin. More real photos per panel (other distances, light) will show
whether 0.40 is too tight; a second collection photo of each team panel is the cheap fix.
