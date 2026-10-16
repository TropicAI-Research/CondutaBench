# CondutaBench

**An open-ended benchmark for guideline-based clinical management in Brazilian Portuguese.**

CondutaBench evaluates whether language models can produce clinical management plans that follow Brazilian medical guidelines. Instead of choosing an answer from a list of options, a model receives a patient scenario and an open-ended question and must explain what should be done. Depending on the case, a response may need to address treatment, monitoring, referral, and actions that should be avoided.

Responses are evaluated with **question-specific rubrics**. Each rubric identifies essential actions, additional recommended actions, clinical errors, and prohibited actions. Criteria have weights that reflect their intended clinical impact. This allows the evaluation to distinguish a partially adequate answer from one that covers all expected actions or includes an incorrect recommendation.

The released benchmark contains **715 questions**, **4,722 rubric criteria**, and material drawn from **14 Brazilian clinical guidelines**. The questions and clinical text are in Portuguese. The rubric types and weights are the final labels used in the paper.

[GitHub repository](https://github.com/TropicAI-Research/CondutaBench) · [Hugging Face dataset](https://huggingface.co/datasets/Tropic-AI/CondutaBench)

## What does CondutaBench measure?

CondutaBench focuses on **guideline-concordant clinical conduct**, rather than multiple-choice medical knowledge. The evaluator asks whether a response:

- Includes all actions classified as essential for the case.
- Covers additional recommendations supported by the selected guideline.
- Includes an error or a prohibited action.
- Contains a recommendation flagged by the rubric as potentially harmful.

Results are reported using five metrics:

| Metric | Meaning |
| --- | --- |
| **Score** | Weighted credit for satisfied criteria, with penalties for errors and prohibited actions, normalized by the total positive weight. Scores are not clipped at zero. |
| **Correct** | All essential criteria are satisfied, with no negative criteria triggered. |
| **Complete** | All positive criteria are satisfied, with no negative criteria triggered. |
| **Negative** | At least one error or prohibited-action criterion is triggered. |
| **Harm** | At least one triggered negative criterion is labeled `pode_piorar`. |

Score is averaged equally across questions. The other metrics are percentages of questions, not percentages of individual criteria. The same calculations are used for per-guideline summaries.

**Scope.** These metrics assess agreement with the selected guideline-based rubrics. They do not measure patient outcomes or establish that a model is safe for clinical use. The dataset is intended for research evaluation, not clinical decision-making.

## Dataset and release contents

The dataset contains three configurations aligned by question `id`. All 715 questions are in the `test` split; no training split is provided.

| File | Contents |
| --- | --- |
| `data/questions.jsonl` | Question ID, guideline ID, topic, clinical scenario, and question |
| `data/rubrics.jsonl` | Reference answer and ordered rubric criteria, including final types, impacts, and weights |
| `data/support.jsonl` | Selected passages from the original guidelines and recorded source-support limitations |
| `run.py` | Generate closed-book model answers and optionally evaluate them |
| `evaluate.py` | Judge saved answers through an API or score existing criterion-level judgments offline |
| `providers.py` | Provider clients for Maritaca, OpenAI, Anthropic, and OpenRouter |
| `SHA256SUMS` | Integrity hashes for release files |

You can also load the dataset from Hugging Face:

```python
from datasets import load_dataset

questions = load_dataset("Tropic-AI/CondutaBench", "questions", split="test")
rubrics = load_dataset("Tropic-AI/CondutaBench", "rubrics", split="test")
support = load_dataset("Tropic-AI/CondutaBench", "support", split="test")
```

The Hugging Face loader requires `pip install datasets`. The generation and evaluation scripts use only the Python standard library and require **Python 3.10 or newer**.

## Quick start

Clone the repository and validate a small closed-book run:

```bash
git clone https://github.com/TropicAI-Research/CondutaBench.git
cd CondutaBench
python3 run.py --provider openai --model MODEL_ID --output outputs/pilot --limit 5 --dry-run
```

Replace `MODEL_ID` with a model supported by your provider. The dry run validates the input without making API calls. To generate answers, set the relevant API key and remove `--dry-run`. The `--limit 5` option selects the first five questions, not a random sample. Without `--limit`, the runner generates answers for all 715 questions.

### 1. Generate model answers

The runner supports four providers. Set the appropriate API key in your shell or secret manager:

| Provider | Environment variable |
| --- | --- |
| Maritaca | `MARITACA_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenRouter | `OPENROUTER_API_KEY` |

Generate answers without judging:

```bash
python3 run.py --provider anthropic --model MODEL_ID --output outputs/anthropic-run
python3 run.py --provider openrouter --model vendor/model --output outputs/openrouter-run
python3 run.py --provider maritaca --model sabia-4 --output outputs/maritaca-run
```

Or generate and judge in the same run, using a separate provider for the judge:

```bash
python3 run.py --provider openai --model MODEL_ID --output outputs/openai-run \
  --evaluate --judge-provider anthropic --judge-model JUDGE_MODEL_ID
```

`run.py` sends only the clinical scenario and question to the evaluated model. It does **not** provide the rubric, reference answer, support passages, tools, or guideline documents. This is a **closed-book evaluation**. The runner writes `predictions.jsonl` and `generation.json`; evaluation results, when requested, are stored in `evaluation/`. Running the same command again resumes the run.

The public runner does not reproduce every model-specific setting in the paper. Generation defaults to a 16,000-token output limit and provider-default temperature and reasoning behavior. You can configure `--max-tokens`, `--temperature`, and `--reasoning-effort` when supported by the provider. Judge settings are independent: `--judge-max-tokens` (8,000 by default), `--judge-temperature`, and `--judge-reasoning-effort`. The Maritaca judge uses temperature zero; other providers omit temperature unless requested. OpenAI/OpenRouter use `reasoning.effort`, Anthropic uses adaptive thinking with `output_config.effort`, and Maritaca does not accept the reasoning-effort flag here. Unsupported parameter combinations fail explicitly. Output limits may include reasoning tokens.

### 2. Evaluate your own answers

You can use answers generated outside the repository. Supply the `scenario` and `question` fields from `data/questions.jsonl` to your model, then save one answer per question in a JSONL file:

```json
{"id":"anf001","answer":"Your model's answer in Portuguese."}
```

Use **one file per model and access condition**. Question IDs must be unique, and all 715 IDs are required by default. Empty answers are allowed and will be evaluated. Use separate files and output directories for repeated generations.

Check the file without API calls:

```bash
python3 evaluate.py --predictions predictions.jsonl --output outputs/model-a --dry-run
```

Then run the default evaluation, after setting `MARITACA_API_KEY`:

```bash
python3 evaluate.py --predictions predictions.jsonl --output outputs/model-a
```

The default judge is **Sabiá-4-Thinking**, with temperature zero, an 8,000-token output limit, and automatic service tier. It receives the scenario, question, reference answer, rubric, and candidate answer. To use another judge:

```bash
python3 evaluate.py --predictions predictions.jsonl --output outputs/openrouter-judge \
  --judge-provider openrouter --judge-model vendor/model
```

For an intentional subset, add `--allow-subset`. Coverage is recorded in the output summary; subset results must not be presented as full-benchmark scores. API evaluation may incur provider charges.

The evaluator caches successful judgments and resumes when rerun with the same output directory. Use a **new output directory** whenever answers, judge/provider settings, or judge-visible benchmark content change. Earlier Maritaca-only caches also require a fresh directory. Calls are sequential, errors stop the run rather than assigning a score of zero, and only one process should write to an output directory. Credentials and raw API payloads are not copied into the cache.

### 3. Score existing judgments offline

If you already have criterion-level judgments, you can calculate metrics without calling an API:

```bash
python3 evaluate.py --judgments judgments.jsonl --output outputs/offline
```

Each JSONL record must contain `id` and `hits`. The `hits` object must include every zero-based criterion index as a string, mapped to JSON `true` or `false`. The API evaluator's `judgments.jsonl` can also be used here. For a negative criterion, `true` means the response **contains the error or prohibited action**.

The evaluator writes per-question results to `scores.jsonl` and overall and per-guideline summaries to `summary.json`.

## Rubric labels and source evidence

Criterion types use these values:

| Type | Meaning |
| --- | --- |
| `essencial` | Essential clinical action |
| `positivo` | Additional recommended action |
| `erro_grave` | Clinical error |
| `acao_proibida` | Prohibited action |

Impact labels determine criterion weights:

| Impact | Weight |
| --- | ---: |
| `reduz_mortalidade` | +5 |
| `melhora_qualidade_vida` | +3 |
| `baixo_impacto` | +1 |
| `desvio_sem_dano` | −2 |
| `pode_piorar` | −5 |

Criterion order is significant. The `original_reference` field preserves the reference attached to the frozen rubric. Separately, `support.jsonl` provides selected passages from the original guidelines and any recorded limitations. The passages are **question-level evidence** and do not imply that each individual criterion is fully supported. Criterion-specific limitations can include `criterion_index` and `selected_passages`; other limitations apply to the question as a whole. The absence of a recorded limitation is not proof of complete support.

Page numbers refer to the original guideline extraction. Passage matching was checked against source documents during internal export, while the public audit checks passage structure and integrity without the full guideline documents. Guideline IDs are stable identifiers, not full authoritative titles.

**Full-context and agentic evaluation:** The complete guideline documents are **not distributed** in this package. Researchers wishing to evaluate models with direct guideline access or tool-based navigation must obtain the source documents separately and implement their own access interface. Neither `run.py` nor `evaluate.py` implements an agent. Do not expose reference answers, rubrics, criterion-specific support passages, or judgments to the model under evaluation. Report the access condition, provider, model, and generation settings alongside results.

## Validate the release

From the repository root, run:

```bash
sha256sum -c SHA256SUMS
python3 -B -m unittest discover -s tests -v
python3 -B audit_release.py
```

These checks cover file integrity, schema, the distribution-file allowlist, and common secret or internal-path patterns. They do not replace a final human review of publication contents. Publish only the reviewed release files, not evaluation outputs, credentials, virtual environments, caches, or the parent project repository.

## License and citation

The benchmark's original content is licensed under [CC BY 4.0](LICENSE-DATA), and the code under the [MIT License](LICENSE). Selected passages from third-party clinical guidelines remain subject to their original authorship and rights; these licenses do not relicense the underlying guideline material.

The paper will be publicly available soon. Citation details will be added after publication.

Provider documentation: [OpenAI Responses](https://developers.openai.com/api/docs/guides/text) · [Anthropic Messages](https://platform.claude.com/docs/en/api/messages/create) · [OpenRouter Chat Completions](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion).
