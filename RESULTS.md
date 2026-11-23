# Eval Results

**Run:** `matrix_20260929_201635` | pixeltable=0.7.8, fastapi=0.141.1, openai=3.16.2, python=3.12.14

- **Skill lift:** cold 82% -> skill 71% pass rate (n=11/14).
- **Functional lift:** cold 78% -> skill 77% on executed cells (n=9/13).
- **Looks-right-but-broken:** 4 cell(s) passed static checks yet failed execution -- what a good skill should reduce.
- **Spend:** $13.63 total, median 19 turns.
- 15 trial(s) excluded as infrastructure errors.

![pass rates](results/chart.svg)

| Story | Context | n | Pass | Func ran | Mean score |
|---|---|---|---|---|---|
| u1 | cold | 5 | 60% [23-88%] | 3/5 | 3.9 |
| u1 | skill | 5 | 20% [4-62%] | 4/5 | 3.0 |
| u3 | cold | 1 (+4 infra) | 100% [21-100%] | 1/1 | 4.7 |
| u3 | skill | 2 (+3 infra) | 100% [34-100%] | 2/2 | 4.8 |
| u4 | cold | 5 | 100% [57-100%] | 5/5 | 5.0 |
| u4 | skill | 5 | 100% [57-100%] | 5/5 | 5.0 |
| u5 | cold | 5 | all infra | - | - |
| u5 | skill | 2 (+3 infra) | 100% [34-100%] | 2/2 | 5.0 |

## Action items

Recurring failure reasons are candidates for skill, docs, or grader fixes. Investigate any reason that repeats.

- `u1`: pxt schema update failed: pxt: 422 no model_base() found in /private/var/folders/s4/0zdx499s6sv3_0jll6ccdbh00000gn/T/pxt (2x)
- `u1`: below pass threshold (2x)
- `u1`: Paragraph splitting is not currently supported for PDF documents. Please contact us at https://github.com/pixeltable/pix (1x)
- `u1`: no code or file/command evidence extracted (1x)

Raw data: `results/matrix_20260929_201635/results.json`; transcripts stay local.
