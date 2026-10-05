# Chat evaluation

3 questions (3 verse, 0 official RULES §3.5, 0 trick/multilingual), full pipeline (router → «بينات» retrieval → answer → guards → answer check). Rubric judge: claude-opus-5.

| model | rubric % | official pass | claims caught (answers) | language ok % | fatwa referral | median s | p90 s | errors |
|---|---|---|---|---|---|---|---|---|
| qwen3.6:latest | 66.7 | 0/0 | 0 (0) | 100.0 | yes | 4.68 | 4.68 | 0 |
