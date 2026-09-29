# Eval Results

Run: `matrix_20260929_134627` (24 trials)
Environment: pixeltable=0.7.8, fastapi=0.141.1, openai=3.16.2, python=3.12.14

Raw data: `results/matrix_20260929_134627/results.json`; transcripts stay local.

| Story | Context | n | Pass | Func ran | Avg halluc | Mean score |
|---|---|---|---|---|---|---|
| u1 | cold | 3 | all infra | - | - | - |
| u1 | skill | 3 | all infra | - | - | - |
| u3 | cold | 1 (+2 infra) | 100% [21-100%] | 1/1 | 0.0 | 4.3 |
| u3 | skill | 1 (+2 infra) | 100% [21-100%] | 1/1 | 0.0 | 5.0 |
| u4 | cold | 3 | all infra | - | - | - |
| u4 | skill | 1 (+2 infra) | 0% [0-79%] | 1/1 | 0.0 | 3.8 |
| u5 | cold | 3 | all infra | - | - | - |
| u5 | skill | 2 (+1 infra) | 50% [9-91%] | 2/2 | 0.0 | 3.8 |

## Failures

- `u4` skill/rep1: query route response does not contain the inserted sku
- `u5` skill/rep3: no articles table, found: []
