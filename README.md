# DHAI_AgenticAI


Current MVP scope:

- `agent_core/core`: parser, planner, router, verifier, finalizer, state machine
- `agent_core/policies`: `general_qa`, `calculation_only`, `mixed_analysis`
- `agent_core/skills`: `parser`, `llm_query_parser`, `retrieval`, `calculator`, `report_writer`, `llm_report_writer`
- `agent_core/examples/run_small_case.py`: runnable demo
- `tests/test_small_case.py`: regression check
- optional local LLM endpoint integration via `LOCAL_LLM_ENDPOINT`
- optional OpenAI-compatible API integration via `OPENAI_COMPAT_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`

Behavior:

- without `LOCAL_LLM_ENDPOINT`: deterministic rule-based planning and routing
- with `LOCAL_LLM_ENDPOINT` or `OPENAI_COMPAT_BASE_URL`: the runner attempts LLM planning, LLM skill routing, LLM query parsing, and LLM report writing
- if the local endpoint is unavailable or returns invalid JSON: the runner falls back to deterministic planning and routing

Run the demo:

```bash
cd /home/xqin5/agenticAI
PYTHONPATH=/home/xqin5/agenticAI python -m agent_core.examples.run_small_case
```

Run the demo with your local LLM server:

```bash
cd /home/xqin5/llm
conda run -n llm python vllm_server.py --model NousResearch/Llama-2-7b-chat-hf --port 8080
```

Then in another terminal:

```bash
cd /home/xqin5/agenticAI
export LOCAL_LLM_ENDPOINT="http://127.0.0.1:8080"
PYTHONPATH=/home/xqin5/agenticAI python -m agent_core.examples.run_small_case
```

Example with another OpenAI-compatible API:

```bash
cd /home/xqin5/agenticAI
export OPENAI_COMPAT_BASE_URL="https://your-provider.example.com"
export LLM_API_KEY="your_api_key"
export LLM_MODEL="your_model_name"
PYTHONPATH=/home/xqin5/agenticAI python -m agent_core.examples.test_local_agent
```

Run the test:

```bash
cd /home/xqin5/agenticAI
PYTHONPATH=/home/xqin5/agenticAI python -m unittest discover -s tests
```
