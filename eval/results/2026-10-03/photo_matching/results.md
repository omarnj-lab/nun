# Photo-matching test

```json
{
  "collection": 171,
  "queries": {
    "easy": 171,
    "medium": 171,
    "hard": 171,
    "real": 4
  },
  "negatives": {
    "commons": 598,
    "fic_internal": 195
  },
  "negatives_dropped_as_same_image": 51,
  "max_inliers_on_a_negative": 1570,
  "chosen_thresholds_zero_false_accepts": null,
  "embedding_only_top1": {
    "easy": 0.9591,
    "medium": 0.9181,
    "hard": 0.8421
  },
  "latency_s": {
    "p50": 0.496,
    "p95": 0.652
  },
  "index_build_s": 36.5,
  "real_photos": [
    {
      "query": "real_ayat_alkursi__1.jpg",
      "expected": "real_ayat_alkursi",
      "matched": "real_ayat_alkursi",
      "inliers": 1272,
      "coverage": 0.94,
      "verdict": "right",
      "public": true
    },
    {
      "query": "real_ayat_alkursi__2.jpg",
      "expected": "real_ayat_alkursi",
      "matched": "real_ayat_alkursi",
      "inliers": 2180,
      "coverage": 1.0,
      "verdict": "right",
      "public": true
    },
    {
      "query": "testing-only photo",
      "expected": "(withheld)",
      "matched": "(withheld)",
      "inliers": 40,
      "coverage": 0.44,
      "verdict": "right",
      "public": false
    },
    {
      "query": "testing-only photo",
      "expected": "(withheld)",
      "matched": "(withheld)",
      "inliers": 103,
      "coverage": 0.69,
      "verdict": "right",
      "public": false
    },
    {
      "query": "testing-only photo",
      "expected": "(withheld)",
      "matched": "(withheld)",
      "inliers": 5,
      "coverage": 0.06,
      "verdict": "rejected (correct)",
      "public": false
    }
  ]
}
```

| inliers_min | coverage_min | false_accepts | correct_easy | correct_medium | correct_hard | wrong_easy | wrong_medium | wrong_hard | correct_real | wrong_real |
|---|---|---|---|---|---|---|---|---|---|---|
| 15 | 0.0 | 83 | 1.0 | 1.0 | 0.9649 | 0 | 0 | 0 | 1.0 | 0 |
| 15 | 0.25 | 17 | 1.0 | 1.0 | 0.9649 | 0 | 0 | 0 | 1.0 | 0 |
| 15 | 0.4 | 3 | 1.0 | 0.9825 | 0.9415 | 0 | 0 | 0 | 1.0 | 0 |
| 15 | 0.5 | 3 | 0.9942 | 0.9766 | 0.9357 | 0 | 0 | 0 | 0.75 | 0 |
| 15 | 0.6 | 2 | 0.9298 | 0.9064 | 0.8655 | 0 | 0 | 0 | 0.75 | 0 |
| 15 | 0.75 | 2 | 0.9064 | 0.8713 | 0.807 | 0 | 0 | 0 | 0.5 | 0 |
| 20 | 0.0 | 58 | 1.0 | 1.0 | 0.9649 | 0 | 0 | 0 | 1.0 | 0 |
| 20 | 0.25 | 14 | 1.0 | 1.0 | 0.9649 | 0 | 0 | 0 | 1.0 | 0 |
| 20 | 0.4 | 3 | 1.0 | 0.9825 | 0.9415 | 0 | 0 | 0 | 1.0 | 0 |
| 20 | 0.5 | 3 | 0.9942 | 0.9766 | 0.9357 | 0 | 0 | 0 | 0.75 | 0 |
| 20 | 0.6 | 2 | 0.9298 | 0.9064 | 0.8655 | 0 | 0 | 0 | 0.75 | 0 |
| 20 | 0.75 | 2 | 0.9064 | 0.8713 | 0.807 | 0 | 0 | 0 | 0.5 | 0 |
| 30 | 0.0 | 38 | 1.0 | 1.0 | 0.9649 | 0 | 0 | 0 | 1.0 | 0 |
| 30 | 0.25 | 14 | 1.0 | 1.0 | 0.9649 | 0 | 0 | 0 | 1.0 | 0 |
| 30 | 0.4 | 3 | 1.0 | 0.9825 | 0.9415 | 0 | 0 | 0 | 1.0 | 0 |
| 30 | 0.5 | 3 | 0.9942 | 0.9766 | 0.9357 | 0 | 0 | 0 | 0.75 | 0 |
| 30 | 0.6 | 2 | 0.9298 | 0.9064 | 0.8655 | 0 | 0 | 0 | 0.75 | 0 |
| 30 | 0.75 | 2 | 0.9064 | 0.8713 | 0.807 | 0 | 0 | 0 | 0.5 | 0 |
| 40 | 0.0 | 29 | 0.9883 | 0.9942 | 0.9591 | 0 | 0 | 0 | 1.0 | 0 |
| 40 | 0.25 | 14 | 0.9883 | 0.9942 | 0.9591 | 0 | 0 | 0 | 1.0 | 0 |
| 40 | 0.4 | 3 | 0.9883 | 0.9825 | 0.9357 | 0 | 0 | 0 | 1.0 | 0 |
| 40 | 0.5 | 3 | 0.9883 | 0.9766 | 0.9298 | 0 | 0 | 0 | 0.75 | 0 |
| 40 | 0.6 | 2 | 0.9298 | 0.9064 | 0.8596 | 0 | 0 | 0 | 0.75 | 0 |
| 40 | 0.75 | 2 | 0.9064 | 0.8713 | 0.807 | 0 | 0 | 0 | 0.5 | 0 |
| 60 | 0.0 | 22 | 0.9825 | 0.9766 | 0.9298 | 0 | 0 | 0 | 0.75 | 0 |
| 60 | 0.25 | 14 | 0.9825 | 0.9766 | 0.9298 | 0 | 0 | 0 | 0.75 | 0 |
| 60 | 0.4 | 3 | 0.9825 | 0.9649 | 0.924 | 0 | 0 | 0 | 0.75 | 0 |
| 60 | 0.5 | 3 | 0.9825 | 0.9591 | 0.924 | 0 | 0 | 0 | 0.75 | 0 |
| 60 | 0.6 | 2 | 0.9298 | 0.8947 | 0.8596 | 0 | 0 | 0 | 0.75 | 0 |
| 60 | 0.75 | 2 | 0.9064 | 0.8713 | 0.807 | 0 | 0 | 0 | 0.5 | 0 |
