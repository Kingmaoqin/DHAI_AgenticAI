### 1. Purpose of This Document

This document explains what has already been built inside `/home/xqin5/agenticAI`, how the current agent core is implemented, what each folder and module is responsible for, what example has already been run successfully, and how the team can continue extending this core for our actual agent goals.

The current system is not yet the final full-featured agent platform, but the most important step has already been completed:

> We now have a working general-purpose agent orchestration core, and we have already run a complete small case with a locally deployed LLM.

This means future work does not need to start from scratch. We can build directly on top of the current core.

---

### 2. What This Agent Core Is

The current system is not designed as a single-task or benchmark-specific agent. Instead, it is a general orchestration core responsible for:

- receiving user tasks
- interpreting task type
- generating plans
- selecting skills for each step
- executing those skills
- verifying outputs
- composing final responses
- recording full traces

In other words, this is the control layer of the agent system rather than a single model that does everything by itself.

The system currently supports two modes:

- rule-based mode: stable execution even without an LLM
- LLM mode: once connected to a local LLM, planning, routing, query parsing, and report writing can be LLM-driven

---

### 3. How the Core Was Built

The implementation follows the direction described in `blueprint`: first build the smallest runnable skeleton, then progressively connect the local LLM.

The core execution chain is:

`TaskSpec -> Policy -> Plan -> Router -> Skill -> Verifier -> FinalResponse -> Trace`

The implementation order was roughly:

1. define unified data schemas
2. build an explicit state machine
3. implement task policies
4. implement a skill registry and built-in skills
5. add verifiers and a finalizer
6. connect a local OpenAI-compatible LLM
7. fix planner/router robustness against unstable local model outputs
8. validate with repeated real runs until LLM planning and critical routing became stable

This approach has several advantages:

- the orchestration skeleton is built first
- it is not tied to a single benchmark
- future tasks can reuse the same core
- new skills can be plugged in easily
- debugging and tracing remain manageable

---

### 4. Folder and Module Responsibilities

The most important structure is:

```text
agenticAI/
├── README.md
├── agent_core/
│   ├── bootstrap.py
│   ├── schemas.py
│   ├── core/
│   ├── policies/
│   ├── skills/
│   ├── services/
│   ├── examples/
│   └── eval/
├── tests/
└── runs/
```

#### 4.1 `agent_core/bootstrap.py`

This is the assembly entry point of the whole system.

It is responsible for:

- reading LLM environment variables
- creating the OpenAI-compatible LLM client
- registering all skills
- creating the planner, router, verifier, and finalizer
- returning a runnable `StateMachineRunner`

#### 4.2 `agent_core/schemas.py`

This file defines the unified data structures used by the entire system:

- `TaskSpec`
- `PlanStep`
- `Artifact`
- `TraceEvent`
- `FinalResponse`
- `RunState`

These schemas are the structural backbone of the agent.

#### 4.3 `agent_core/core/`

This is the orchestration core and the most important part of the project.

Main files:

- `parser.py`
  - converts raw queries into `TaskSpec`
- `planner.py`
  - generates plans
  - currently supports both rule-based and LLM-driven planning
- `router.py`
  - chooses one skill from step candidates
  - supports both rule-based and LLM routing
- `verifier.py`
  - validates output schema and evidence linkage
- `finalizer.py`
  - produces the final response object
- `state_machine.py`
  - the main execution loop and state controller

#### 4.4 `agent_core/policies/`

This folder defines task policies.

Current built-in policies:

- `general_qa`
- `calculation_only`
- `mixed_analysis`

These policies define default step decompositions and candidate skills for each task type.

#### 4.5 `agent_core/skills/`

This is the pluggable capability layer.

Current built-in skills:

- `parser`
- `llm_query_parser`
- `retrieval`
- `calculator`
- `report_writer`
- `llm_report_writer`

The point of skills is to separate orchestration from capability implementation.

#### 4.6 `agent_core/services/`

This folder is for external service integration.

The main file is:

- `llm_client.py`

It now supports OpenAI-compatible APIs, which means it can connect to:

- our local service in `/home/xqin5/llm`
- other public OpenAI-compatible APIs in the future

#### 4.7 `agent_core/examples/`

This folder contains runnable examples.

Most important scripts:

- `run_small_case.py`
- `test_local_agent.py`

`test_local_agent.py` is the most useful current debugging entry point because it prints:

- health check
- planning mode
- selected skill per step
- routing mode
- final response

#### 4.8 `tests/`

This folder contains automated tests:

- `test_small_case.py`
- `test_local_llm_integration.py`

These tests provide basic regression coverage for the small case and LLM integration.

#### 4.9 `runs/`

This folder stores real run results.

Each run produces:

- `run-xxx_state.json`
- `run-xxx_trace.json`

This is important for:

- debugging
- replay and inspection
- benchmark records
- analyzing planner/router behavior

---

### 5. What Example We Ran

The current successful example is a `mixed_analysis` small case.

The test query is:

```text
Based on the office handbook, what is the lunch reimbursement limit, and what is 18 + 24? Return a short report with evidence.
```

This task combines:

- policy/document retrieval
- arithmetic computation

So it is a good test for the orchestration core because it requires:

- task parsing
- plan generation
- route selection
- retrieval
- calculation
- report synthesis
- evidence grounding

Although the case is small, it exercises the critical agent control path.

---

### 6. What the Successful Result Looks Like

In the latest successful runs, the system has achieved:

- `planning_mode = llm`
- `step-1 selected_skill = llm_query_parser`
- `step-1 routing_mode = llm`
- `step-4 selected_skill = llm_report_writer`
- `step-4 routing_mode = llm`
- valid final schema
- valid evidence ids

Representative successful runs include:

- `runs/run-39b8452d_state.json`
- `runs/run-a80045c9_state.json`
- `runs/run-c4a8350d_state.json`
- `runs/run-fee90b16_state.json`
- `runs/run-0f026075_state.json`

These runs show that:

- LLM planning is working
- LLM routing is working for critical steps
- LLM query parsing is working
- LLM report writing is working

At the same time, deterministic tools are still preserved for:

- `retrieval`
- `calculator`

This is a reasonable design choice because tool-like steps do not need to be replaced by the LLM.

---

### 7. What This Core Already Demonstrates

It shows that we no longer only have an idea. We now have a real working orchestration foundation.

That means the team no longer needs to restart the discussion from “how should we build an agent framework?”

The following foundations already exist:

- explicit state machine
- unified schemas
- task policies
- planner
- router
- verifier
- finalizer
- trace
- local LLM integration
- OpenAI-compatible API support

The more valuable next step is to add real task capabilities on top of this core.

---

### 8. How the Team Should Continue Building on Top of This Core

The team should continue extending the current core instead of creating separate small frameworks from scratch.

Recommended priorities:

#### 8.1 Upgrade mock retrieval into real RAG

This is the most immediate and valuable next step.

Current retrieval is still mock dictionary matching. For a research agent, it should be upgraded into:

- paper/document chunking
- embedding
- vector search
- reranking

#### 8.2 Add real research-oriented skills

Examples:

- paper retrieval
- citation extraction
- claim verification
- experiment summarization
- note generation
- paper comparison
- hypothesis generation

#### 8.3 Strengthen verifiers

Current verifiers mainly check schema and evidence linkage. Later we can add:

- citation verifier
- numeric verifier
- reasoning consistency verifier
- output template verifier

#### 8.4 Add long-term memory and session support

For longer tasks, we can later add:

- session state
- episodic memory
- result cache
- task history

#### 8.5 Add an API layer

Eventually, the current runner should be wrapped into a service interface so it can support:

- benchmark batch runs
- collaborative access
- unified frontend or evaluation endpoints

---

### 9. Recommended Near-Term Goal

At this stage, we should not spread the scope too widely.

The most reasonable near-term goal is:

> Use the first Research Agent task as the immediate target, and extend the current core into a competition-ready research agent system.

This is beneficial because:

- the target is concrete
- it creates a fast development loop
- the competition task reveals which skills and verifiers are missing
- mock modules can be replaced by real ones quickly

In other words, the orchestration core is already sufficient for the current stage. The main focus should now shift from framework construction to task capability construction.

---

### 10. Summary

The current system in `/home/xqin5/agenticAI` has already completed the most important first step of the agent project:

> We have built a working, extensible, locally-LLM-enabled, OpenAI-compatible agent orchestration core.

This core can already:

- parse tasks
- generate plans
- route skills
- execute steps
- verify outputs
- record traces
- integrate external LLMs

And through the small case, we have already verified that:

- LLM planning works
- LLM routing works
- LLM query parsing works
- LLM report writing works

Therefore, the team should directly continue from this core and use it as the foundation for adding the agent capabilities and optimizations we actually need.

The most suitable next goal is to focus on the **first Research Agent task** and expand this core toward a competition-oriented research agent.
