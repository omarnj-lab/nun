# KhaṭṭVision v1 · can it identify the verse? (2026-10-01)

Input: `quranic_ocr_predictions.csv` (v1 adapter rev 2cdaa0f, greedy, 448² max area) on the 567 Quranic DuwatBench images,
split by exposure: 371 seen in training, 196 held-out (66 validation + 130 test).

Method (`verse_id_eval.py`): locate both the gold text and the model's reading in the full Quran (6,236 ayahs from QuranEnc,
Uthmani, normalised, single ayahs + 2–3-ayah windows, fuzzy partial matching), compare at verse-text level (repeated verses count
as correct), primary = longest non-Basmala segment. 87% of held-out gold texts are locatable (the rest are titles, signatures,
non-Quran text) → 171 held-out images scored.

| | Held-out (val+test) | Test only | Seen in training |
|---|---|---|---|
| Verse identified (top-1) | **38.6%** | 39.5% | 64.7% |
| Answer when match score ≥ 90: share answered | 66.7% | 68.1% | 71.0% |
| … precision of those answers | **50.9%** | 48.1% | 75.4% |
| … confidently WRONG (share of all images) | **32.7%** | 35.3% | 17.5% |

By style (held-out, top-1): Thuluth 0.37 (n=91) · Diwani 0.30 (n=33, 52% confidently wrong) · Nasta'liq 0.50 (n=16) · Kufic 0.27 (n=11) · Ruq'ah 0.40 (n=10) · Naskh 0.80 (n=5).
58 of the 171 held-out golds are a Basmala alone; on the other 113 the model finds the right verse 34.5% of the time.

**Failure mode: memorised fallback.** When it cannot read a panel, it writes a famous phrase from its training labels:
Ayat al-Kursi (10×), «الله أكبر» (8×), «لا إله إلا الله محمد رسول الله» (6×), «فبأي آلاء ربكما تكذبان» (5×), «سبحان الله وبحمده»,
«لا حول ولا قوة إلا بالله», Basmala, «يس». These 8 outputs are 42% of the wrong answers; 32 of 105 wrong readings are word-for-word
copies of a training panel's label. Because these are real verses/phrases, a closed-corpus search matches them perfectly:
**the match score cannot tell a right reading from a memorised wrong one.**

Conclusion: v1 alone cannot drive an automatic "✓ verified" answer (≈1 in 3 visitors would see the wrong verse).

## Update 2026-10-02 · inference at 896² (same adapter, RTX 5090 32 GB, no OOM)

Held-out transcription: char accuracy 12% → 34%, exact 31% → 36%, chrF 42.6 → 57.9 (train-seen unchanged → resolution was the gain).

| Held-out, 171 locatable | 448² | 896² | 896² + 448² agree | + suspect-phrase filter |
|---|---|---|---|---|
| Answered | 67% | 66% | 36% | 9% |
| Precision of answers | 51% | 65% | 79% | ~93% |
| Confidently wrong (all images) | 33% | 23% | 7.6% | 0.6% |

Verse identified top-1: 38.6% → 46.2% (fixed 28, broken 15). Remaining errors are the memorised fallback, consistent across resolutions.
As a curator aid (suggestions from both readings): right verse in top-1 47%, top-5 51%, top-10 60%.

**Decision:** v1 cannot auto-verify unknown panels at a useful coverage. Nūn identifies panels from a **human-confirmed collection**
(curator adds a panel → v1 suggests the verse → an Arabic reader confirms → visitors' photos are matched to the confirmed panel).
