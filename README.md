# DHAI_AgenticAI

A general-purpose agentic AI framework with two main components:

1. **`agent_core`** — Rule-based and LLM-driven orchestration engine (state machine, planner, router, skills)
2. **`purple_agent`** — A2A-compatible agent server for the [AgentBeats](https://agentbeats.dev/) competition platform

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  A2A Protocol Layer (purple_agent)                   │
│  ┌─────────┐  ┌────────────┐  ┌──────────────────┐  │
│  │ Server  │→ │ Executor   │→ │ Multimodal Conv. │  │
│  │ (A2A)   │  │ (lifecycle)│  │ (video/img/pdf)  │  │
│  └─────────┘  └────────────┘  └──────────────────┘  │
│                      ↓                               │
│  ┌──────────────────────────────────────────────┐    │
│  │ Agent Logic (currently: LLM single-pass)     │    │
│  │ (future: agent_core state machine)           │    │
│  └──────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  Orchestration Core (agent_core)                     │
│  TaskSpec → Policy → Plan → Router → Skill           │
│         → Verifier → FinalResponse → Trace           │
└──────────────────────────────────────────────────────┘
```

---

## Components

### agent_core (Orchestration Engine)

- `agent_core/core`: parser, planner, router, verifier, finalizer, state machine
- `agent_core/policies`: `general_qa`, `calculation_only`, `mixed_analysis`
- `agent_core/skills`: `parser`, `llm_query_parser`, `retrieval`, `calculator`, `report_writer`, `llm_report_writer`
- `agent_core/services`: OpenAI-compatible LLM client
- `agent_core/examples/run_small_case.py`: runnable demo

Behavior:
- Without LLM endpoint: deterministic rule-based planning and routing
- With `LOCAL_LLM_ENDPOINT` or `OPENAI_COMPAT_BASE_URL`: LLM-driven planning, routing, query parsing, and report writing
- Automatic fallback to deterministic mode if LLM is unavailable

### purple_agent (A2A Competition Agent)

An [A2A protocol](https://a2a-protocol.org/) compatible agent server built for the AgentBeats platform. Supports:

- **Multimodal input**: video (.mp4 → frame extraction), images (.jpg → JPEG), PDFs (.pdf → text), text files
- **Auto-detected LLM provider**: OpenAI, OpenRouter (auto-detected from API key prefix)
- **Pluggable agent logic**: currently single-pass LLM, designed to be replaced with `agent_core` state machine
- **Google ADK integration**: uses `google.adk.agents.Agent` + LiteLLM for model access

---

## Quick Start

### Run agent_core demo

```bash
cd /path/to/DHAI_AgenticAI
PYTHONPATH=. python -m agent_core.examples.run_small_case
```

### Run purple_agent (A2A server)

```bash
cd purple_agent
cp .env.sample .env
# Edit .env with your API keys

uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install -e "."

PYTHONPATH=src python -m agent.server --host 127.0.0.1 --port 9019
```

### Run tests

```bash
# Smoke test (agent card + simple text query)
PYTHONPATH=src python tests/test_smoke.py

# A2A protocol tests (text, file attachment, reasoning)
python tests/test_a2a_direct.py
```

### Test with FieldWorkArena (requires HF_TOKEN)

```bash
# 1. Apply for dataset access at:
#    https://en-documents.research.global.fujitsu.com/fieldworkarena/
# 2. Add HF_TOKEN to .env
# 3. Clone FieldWorkArena-GreenAgent alongside this repo
# 4. Run: python tests/test_e2e.py
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI or OpenRouter API key |
| `HF_TOKEN` | For FWA | Hugging Face access token (FieldWorkArena dataset) |
| `LLM_PROVIDER` | No | Override LLM provider (default: auto-detect) |
| `LLM_MODEL` | No | Override model name (default: gpt-4o) |
| `LLM_BASE_URL` | No | Override API base URL |
| `LOCAL_LLM_ENDPOINT` | No | Local LLM endpoint for agent_core |

---

## Project Structure

```
DHAI_AgenticAI/
├── agent_core/                    # Orchestration engine
│   ├── bootstrap.py               # System assembly entry point
│   ├── schemas.py                 # Unified data structures
│   ├── core/                      # State machine, planner, router, verifier
│   ├── policies/                  # Task policies (QA, calculation, mixed)
│   ├── skills/                    # Pluggable capabilities
│   ├── services/                  # LLM client
│   ├── examples/                  # Runnable demos
│   └── eval/                      # Evaluation harness
├── purple_agent/                  # A2A competition agent
│   ├── pyproject.toml             # Dependencies
│   ├── .env.sample                # Environment template
│   ├── prompts/                   # Agent prompt configs (YAML)
│   ├── src/agent/
│   │   ├── server.py              # A2A server entry point
│   │   ├── executor.py            # Request handler + task lifecycle
│   │   ├── agent_logic.py         # Agent builder (auto-detect provider)
│   │   └── multimodal.py          # Video/image/PDF/text conversion
│   ├── scenarios/fwa/             # FieldWorkArena test config
│   └── tests/                     # Smoke, A2A direct, and E2E tests
├── tests/                         # agent_core regression tests
├── blueprint                      # Original design notes
└── AgentReadme.md                 # Detailed agent core documentation
```

---

## Target Benchmarks

- **FieldWorkArena** (Sprint 2): Multimodal field-work tasks in factories, warehouses, retail
- **OfficeQA** (Finance Agent): Document-grounded reasoning over U.S. Treasury Bulletin PDFs

---

## Team

| Member | Responsibility |
|--------|---------------|
| Xinyu | Main agent logic, orchestration, state machine |
| Ruiheng | Retrieval, A2A integration, runtime readiness |
| Farnoosh | Tool specification, offline extraction, unit normalization |
| Xi | Benchmark analysis, evaluation, optimization feedback |
