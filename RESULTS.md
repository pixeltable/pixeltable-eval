# Eval Results

**Run:** `matrix_20260929_134627` | pixeltable=0.7.8, fastapi=0.141.1, openai=3.16.2, python=3.12.14

- **Skill lift:** cold 100% -> skill 50% pass rate (n=1/4).
- **Functional lift:** cold 100% -> skill 50% on executed cells (n=1/4).
- **Looks-right-but-broken:** 1 cell(s) passed static checks yet failed execution -- what a good skill should reduce.
- **Spend:** $6.07 total, median 9 turns.
- 19 trial(s) excluded as infrastructure errors.

![pass rates](results/chart.svg)

| Story | Context | n | Pass | Func ran | Mean score |
|---|---|---|---|---|---|
| u1 | cold | 3 | all infra | - | - |
| u1 | skill | 3 | all infra | - | - |
| u3 | cold | 1 (+2 infra) | 100% [21-100%] | 1/1 | 4.3 |
| u3 | skill | 1 (+2 infra) | 100% [21-100%] | 1/1 | 5.0 |
| u4 | cold | 3 | all infra | - | - |
| u4 | skill | 1 (+2 infra) | 0% [0-79%] | 1/1 | 3.8 |
| u5 | cold | 3 | all infra | - | - |
| u5 | skill | 2 (+1 infra) | 50% [9-91%] | 2/2 | 3.8 |

## Action items

Recurring failure reasons are candidates for skill, docs, or grader fixes. Investigate any reason that repeats.

- `u4`: query route response does not contain the inserted sku (1x)
- `u5`: no articles table, found: [] (1x)

Raw data: `results/matrix_20260929_134627/results.json`; transcripts stay local.
