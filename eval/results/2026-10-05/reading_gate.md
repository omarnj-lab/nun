# Reading path gate: KhaṭṭVision reads a panel that is not in the collection → nearest Quran passage

**Set:** the same 195 internal panels as `recognition_compare.md` (not in Nūn's collection; images internal only).
**Pipeline (as deployed):** KhaṭṭVision v1 structured call (its own script style, theme and text regions) →
`nun/retrieval/verse_search.py` (nearest 1–3-ayah passage) → `nun/reading.py` gate. Run 2026-10-05, local GPU only.

What KhaṭṭVision itself got right: script style 68% overall (Naskh 85%, Thuluth 86%, Diwani 36%); called the panel
Quranic 88% of the time (all 195 are Quranic).

Gate sweep (theme = quranic, style = Naskh, score ≥ 90, lines agree, minimum letters varied):

| min letters | verses shown | right | wrong | wrong (% of all panels) |
|---|---|---|---|---|
| 15 | 37 | 31 | 6 | 3.1% |
| 20 | 31 | 28 | 3 | 1.5% |
| 25 | 29 | 27 | 2 | 1.0% |
| **30 (deployed)** | **26** | **25** | **1** | **0.5%** |
| 40 | 20 | 19 | 1 | 0.5% |

The wrong readings at short lengths are famous phrases the model recalls instead of reading (55:13, 2:156, 112:4 for
112:3). The remaining error at 30 letters is 7:184 shown as 30:8 — two verses that open with the same words.

**With the gate, KhaṭṭVision identifies 25 of 60 Naskh panels (42%) with 1 error, and shows no verse for ornate scripts**,
where it states the script and text regions instead. Without the gate (nearest passage for every reading) the same
model showed a wrong verse on 32.8% of panels (`recognition_compare.md`).
