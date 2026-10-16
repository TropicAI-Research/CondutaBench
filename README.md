# CondutaBench

Portuguese clinical-management benchmark: **715 questions**, **4,722 rubric criteria** covering **14 guidelines**. The rubric labels are the final labels used in the paper; supporting passages were consolidated on October 13, 2026. Clinical text remains in Portuguese.

[GitHub](https://github.com/TropicAI-Research/CondutaBench) · [Hugging Face dataset](https://huggingface.co/datasets/Tropic-AI/CondutaBench)

## Quick start

```bash
git clone https://github.com/TropicAI-Research/CondutaBench.git
cd CondutaBench
python3 run.py --provider openai --model MODEL_ID --output outputs/pilot --limit 5 --dry-run
```

Replace `MODEL_ID` with your model ID. The dry run validates inputs without API calls. Set the provider's API key and remove `--dry-run` when ready to generate answers.

## Load from Hugging Face

The dataset provides three aligned configurations, joined by `id`: `questions`, `rubrics`, and `support`. All 715 items belong to the evaluation set; no training partition is provided.

```python
from datasets import load_dataset

questions = load_dataset("Tropic-AI/CondutaBench", "questions", split="test")
rubrics = load_dataset("Tropic-AI/CondutaBench", "rubrics", split="test")
support = load_dataset("Tropic-AI/CondutaBench", "support", split="test")
```

The optional loader requires `pip install datasets`. The generation and evaluation scripts themselves use only the Python standard library.

## Contents

| File | Contents |
| --- | --- |
| `data/questions.jsonl` | Question ID, guideline ID, topic, clinical scenario and question |
| `data/rubrics.jsonl` | Reference answer and ordered criteria, final types, impacts and weights |
| `data/support.jsonl` | Selected original-guideline passages and recorded support limitations |
| `run.py` | Generate closed-book answers and optionally evaluate them |
| `evaluate.py` | API judging of saved answers and offline scoring |
| `providers.py` | Shared clients for Maritaca, OpenAI, Anthropic and OpenRouter |
| `SHA256SUMS` | Integrity hashes for the distribution files |

No installation is needed beyond **Python 3.10 or newer**. Run commands from this folder. No project checkout or private files are required.

## Run a model directly

You do not need to prepare JSONL. Set the API key for each provider you use in your shell or secret manager:

| Provider | API key environment variable |
| --- | --- |
| `maritaca` | `MARITACA_API_KEY` |
| `openai` | `OPENAI_API_KEY` |
| `anthropic` | `ANTHROPIC_API_KEY` |
| `openrouter` | `OPENROUTER_API_KEY` |

Replace `MODEL_ID` / `JUDGE_MODEL_ID` with exact model IDs available to your account. OpenRouter IDs use `vendor/model`. For example, generate answers and immediately judge them with a different provider:

```bash
python3 run.py --provider openai --model MODEL_ID --output outputs/openai-run \
  --evaluate --judge-provider anthropic --judge-model JUDGE_MODEL_ID
```

Generate only (works with any of the four providers):

```bash
python3 run.py --provider anthropic --model MODEL_ID --output outputs/anthropic-run
python3 run.py --provider openrouter --model vendor/model --output outputs/openrouter-run
python3 run.py --provider maritaca --model sabia-4 --output outputs/maritaca-run
```

Start with `--limit 5 --dry-run` to validate without charges, then remove `--dry-run` for a five-question pilot. `--limit` selects the first N dataset questions, not a random sample. Use a new output directory for the full run. Without `--limit`, all 715 questions are generated.

`run.py` sends only the scenario and question in a single user message: **closed-book**, without rubric leakage, tools or source documents. It saves answers automatically in `predictions.jsonl`, generation settings in `generation.json`, and evaluation results under `evaluation/`. Repeat the same command to resume. This is a simple generation interface, not a reproduction of every model-specific generation setup in the paper.

Generation defaults to a 16,000-token output ceiling and provider-default temperature/reasoning. Use `--max-tokens`, `--temperature`, and `--reasoning-effort` to configure it. Judge options are independent: `--judge-max-tokens` (8,000 by default), `--judge-temperature`, and `--judge-reasoning-effort`. Maritaca judging retains temperature zero; other providers omit temperature unless explicitly supplied, for compatibility with reasoning models.

Reasoning effort maps to `reasoning.effort` for OpenAI/OpenRouter and adaptive thinking with `output_config.effort` for Anthropic. Use only effort values supported by your selected model. Maritaca uses the selected model's reasoning behavior and does not accept that flag here. Not every model accepts temperature or adaptive thinking; unsupported combinations fail explicitly rather than silently changing settings. Output limits can include reasoning tokens; raise the limit if a response is incomplete.

## Use your own generated answers

Use `scenario` and `question` from `data/questions.jsonl` as model inputs. Do **not** give the evaluated model `rubrics.jsonl`, reference answers, criterion-specific support passages or judgments. Full guideline documents are not distributed in this package. Full-context or agentic evaluations require separately obtained source documents. Keep the access condition and model configuration consistent and report them with results. The generation runner implements closed-book access; neither script implements an agent.

Save **one model and one access condition per JSONL file**, with one answer per question:

```json
{"id":"anf001","answer":"Your model's answer in Portuguese."}
```

IDs must be unique. An empty answer is allowed and will be judged. By default all 715 IDs are required. Repeated generations should use separate prediction files and output directories; this script reports single-generation metrics, not pass@k.

## Evaluate

Validate the format and coverage first, without calling any API:

```bash
python3 evaluate.py --predictions predictions.jsonl --output outputs/model-a --dry-run
```

Set `MARITACA_API_KEY` in your shell environment or secret manager. Do not save credentials inside this folder. Then run:

```bash
python3 evaluate.py --predictions predictions.jsonl --output outputs/model-a
```

The default judge is **Sabiá-4-Thinking**, with temperature 0, an 8,000-token output limit and automatic service tier. The prompt uses the scenario, question, reference answer, final rubric and candidate answer. Use `--judge-provider` and `--judge-model` to select another judge. Requests go to the selected provider and may incur charges under your account. Report the provider, model and settings with results. For example:

```bash
python3 evaluate.py --predictions predictions.jsonl --output outputs/openrouter-judge \
  --judge-provider openrouter --judge-model vendor/model
```

For an intentional smaller pilot, add `--allow-subset`. The summary always records coverage. Subset scores must not be reported as full-benchmark scores.

Successful judgments are saved after each request. Repeating the same command resumes from the cache. Changed answers, provider, judge settings or judge-visible benchmark content require a fresh output directory. Caches from the earlier Maritaca-only script require a fresh directory as well. Requests are sequential; failed requests stop the run rather than being silently retried or assigned zero. Use only one process per output directory. Responses, credentials and raw API payloads are not copied into the cache.

## Offline scoring

To score existing criterion-level judgments without API calls, provide JSONL records containing `id` and `hits`. Keys are zero-based criterion indices encoded as strings. Include every index exactly once; values must be JSON `true` or `false`.

```bash
python3 evaluate.py --judgments judgments.jsonl --output outputs/offline
```

The API mode's `judgments.jsonl` is also valid input for this command. For negative criteria, `true` means the answer **committed the error or prohibited action**; it is not a successful outcome.

The evaluator writes per-question `scores.jsonl` and `summary.json` with overall and per-guideline metrics:

- **Score:** 100 times the sum of weights of triggered criteria divided by the sum of positive weights. Negative values are retained; scores are not clipped.
- **Correct:** every essential criterion is satisfied and no negative criterion is triggered.
- **Complete:** every positive-weight criterion is satisfied and no negative criterion is triggered.
- **Negative:** at least one negative criterion is triggered.
- **Harm:** a triggered negative criterion has impact `pode_piorar`.

Aggregate Score is the unweighted mean across questions. Other aggregate metrics are percentages of questions, not percentages of criteria. The same aggregation is used within each guideline.

## Data schema and source support

Criterion types are `essencial` (essential), `positivo` (positive), `erro_grave` (error), and `acao_proibida` (prohibited action). Impacts determine weights: `reduz_mortalidade` +5, `melhora_qualidade_vida` +3, `baixo_impacto` +1, `desvio_sem_dano` −2, and `pode_piorar` −5. Criterion order is significant.

`original_reference` preserves the reference stored with the frozen rubric. `support.jsonl` supplies the subsequently selected passages separately, without modifying criterion wording or labels. Its `passages` are question-level evidence, not an assertion that every criterion is fully supported. Each entry in `limitations` records a known source gap; criterion-specific entries include `criterion_index` and `selected_passages`, while a question-level note can apply to several criteria. Absence of a recorded limitation is not a certificate of complete support. Page numbers refer to the original source extraction. Passage matching against the source documents is checked during the internal export; the public audit checks passage structure and integrity without requiring those documents.

Guideline IDs are stable identifiers, not authoritative document titles. Only selected support excerpts are included, not the complete guideline text files. This package is for research evaluation, not clinical decision-making. Third-party excerpts retain their original authorship and rights. Original benchmark content is licensed under [CC BY 4.0](LICENSE-DATA); code is licensed under the [MIT License](LICENSE). These licenses do not relicense third-party guideline excerpts, which retain their original authorship and rights.

## Verify the package

```bash
sha256sum -c SHA256SUMS
python3 -B -m unittest discover -s tests -v
python3 -B audit_release.py
```

Publish only the reviewed distribution files. Do not publish the parent repository, evaluation outputs, credentials, local virtual environments or cache directories. The audit checks the file allowlist, integrity, schema and common secret/internal-path patterns; it does not replace a final human review of publication contents.

Provider interfaces follow the official [OpenAI Responses guide](https://developers.openai.com/api/docs/guides/text), [Anthropic Messages reference](https://platform.claude.com/docs/en/api/messages/create), and [OpenRouter Chat Completions reference](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion).

## Citation

```bibtex
@misc{laitz2026condutabench,
  title = {CondutaBench: From Clinical Guidelines to Agentic Evaluation in Brazilian Portuguese},
  author = {Laitz, Thiago and Mazza, Flávia and Bonás, Mariana Kerche and Bonás, Giovana Kerche and Santos, João Guilherme Alves and Almeida, Thales Sales and Nogueira, Rodrigo and Pedrini, Helio},
  year = {2026},
  url = {https://github.com/TropicAI-Research/CondutaBench}
}
```
