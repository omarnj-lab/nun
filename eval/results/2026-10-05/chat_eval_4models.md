# Chat evaluation

28 questions (12 verse, 12 official RULES §3.5, 4 trick/multilingual), full pipeline (router → «بينات» retrieval → answer → guards → answer check). Rubric judge: claude-opus-5.

| model | rubric % | official pass | claims caught (answers) | language ok % | fatwa referral | median s | p90 s | errors |
|---|---|---|---|---|---|---|---|---|
| qwen3.6:latest | 76.8 | 9/12 | 19 (9) | 100.0 | yes | 2.45 | 3.03 | 0 |
| gpt-oss:20b | 26.8 | 2/12 | 40 (18) | 100.0 | yes | 8.18 | 22.29 | 0 |
| TuwaiqAI-Instruct:latest | 78.6 | 8/12 | 14 (9) | 100.0 | yes | 2.67 | 2.95 | 0 |
| claude-opus-5 | 94.6 | 10/12 | 10 (10) | 100.0 | yes | 10.69 | 13.35 | 0 |
