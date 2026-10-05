# Verse recognition from calligraphy photos: Nūn vs vision LLMs vs KhaṭṭVision

**Set:** 195 labelled panels from the team's internal test set (freeislamiccalligraphy.com; images are internal only
and are not published anywhere: only these numbers are). Styles: Naskh 60, Thuluth 59, Diwani 59, Diwani-jelli 11,
Kufic 5, Muhaqaq 1. None of these panels is in Nūn's product collection.
**Task:** name the Quran verse in the image, or say it cannot. Same prompt for both LLMs (`eval/recognition_compare.py`);
the images were sent without file names. Run 2026-10-05.

| system | correct | shows a verse | precision | **wrong verse shown** |
|---|---|---|---|---|
| **Nūn as deployed** (match against its collection, else abstain) | 0% | 0% | – | **0.0%** |
| KhaṭṭVision v1 (our model: reading → corpus search, score ≥ 90) | 34.9% | 68% | 52% | 32.8% |
| GPT-5.5 | 57.9% | 93% | 62% | 35.4% |
| Claude Opus 5 | 84.6% | 95% | 89% | 10.3% |

By style (correct / wrong shown): Naskh — KhaṭṭVision 83% / 5%, GPT 100% / 0%, Claude 100% / 0%; Thuluth — 12% / 49%,
34% / 56%, 64% / 27%; Diwani — 15% / 34%, 53% / 37%, 95% / 2%.

**Agreement rules** (`eval/recognition_agreement.py`): show a verse only when two independent sources agree.

| rule | covers | precision | wrong shown |
|---|---|---|---|
| Claude + GPT agree | 61% | 96% | 2.6% |
| Claude + KhaṭṭVision reading agree (fuzzy ≥ 80 with the verse text) | 37% | 97% | 1.0% |
| Claude + (GPT or reading) | 63% | 95% | 3.1% |
| any of the above, **Naskh only** | 85–100% | 100% | **0%** |

**Reading this honestly**
- General vision LLMs name a wrong verse 10–35% of the time when used alone; Nūn's verified-match design shows a
  wrong verse 0 times in 195 (and the right card on its own collection: see `eval/results/2026-10-03/photo_matching`).
- Claude Opus 5 reads calligraphy far better than our v1 model, especially Diwani and Thuluth.
- These panels are public on the web: the LLMs may have seen them in training, so their scores may be optimistic.
- Wrong-verse rates are the safety number that matters for religious content: an unverified verse is never shown.
