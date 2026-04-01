# Agent系统核心说明 / Agent Core Overview

## 中文说明

### 1. 文档目的

这份文档用于向团队说明目前 `/home/xqin5/agenticAI` 中已经搭建好的 agent 系统核心是什么、整体是如何实现的、每个文件夹和模块各自负责什么、我们已经跑通了什么例子，以及接下来希望大家如何在这个核心基础上继续扩展和优化。

当前这套系统还不是最终版的大而全 agent 平台，但已经完成了最关键的一步：

> 我们已经把一个可运行的通用 agent orchestration core 搭起来了，并且已经用本地部署的 LLM 跑通了一个完整的小 case。

这意味着后面不需要再从零开始做 agent 框架，而是可以直接在现有核心上叠加真实任务能力。

---

### 2. 目前这个 agent 系统核心是什么

目前系统的定位不是某一个固定赛道的专用 agent，而是一个通用的总控核心，主要负责以下事情：

- 接收用户任务
- 解析任务类型
- 生成执行计划
- 为每个步骤选择技能
- 执行技能
- 校验结果
- 汇总最终输出
- 记录完整 trace

也就是说，它当前更像一个“agent 的调度中枢”，而不是单独完成所有能力的终端模型。

当前它已经支持两种模式：

- 规则模式：没有 LLM 时也可以稳定运行
- LLM 模式：接上本地部署的 LLM 后，可以让 planning、routing、query parsing、report writing 这些关键步骤由 LLM 真正参与

---

### 3. 我是怎么搭建这个核心的

整体设计思路是按 `blueprint` 来落地，先优先实现最小可运行骨架，再逐步把本地 LLM 接进去。

当前实现的核心链路是：

`TaskSpec -> Policy -> Plan -> Router -> Skill -> Verifier -> FinalResponse -> Trace`

实现顺序大致是：

1. 先定义统一数据结构
2. 再做显式状态机
3. 再做 task policy
4. 再做 skill registry 和内置 skill
5. 再做 verifier 和 finalizer
6. 再接本地 OpenAI-compatible LLM
7. 再修 planner/router 对本地 LLM 输出不稳定的问题
8. 最后通过多轮真实回归把 LLM 规划和关键路由稳定下来

这个实现方式的好处是：

- 先把总控骨架搭稳
- 不依赖某一个具体 benchmark
- 后面加新任务时不用推倒重来
- 容易接更多 skills
- 容易做调试和追踪

---

### 4. 目录和代码结构说明

当前最重要的目录结构如下：

```text
agenticAI/
├── README.md
├── blueprint
├── 代码实现详解.md
├── Agent系统核心说明_双语.md
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

下面按模块说明。

#### 4.1 `agent_core/bootstrap.py`

这是整个系统的装配入口。

它负责：

- 读取 LLM 环境变量
- 创建 OpenAI-compatible LLM client
- 注册所有 skills
- 创建 planner、router、verifier、finalizer
- 返回一个可运行的 `StateMachineRunner`

可以把它理解成 agent 系统的总装配点。

#### 4.2 `agent_core/schemas.py`

这里定义了整个系统统一使用的数据结构。

核心包括：

- `TaskSpec`
- `PlanStep`
- `Artifact`
- `TraceEvent`
- `FinalResponse`
- `RunState`

这是整个系统的数据骨架。后面所有 planner、router、skills、trace 都围绕这些结构工作。

#### 4.3 `agent_core/core/`

这是 orchestration core，本项目最关键的部分。

主要文件包括：

- `parser.py`
  - 把原始 query 解析成 `TaskSpec`
- `planner.py`
  - 负责生成计划
  - 当前支持规则 plan 和 LLM 驱动 plan
- `router.py`
  - 负责在候选 skills 之间选择一个来执行
  - 当前支持规则路由和 LLM 路由
- `verifier.py`
  - 检查输出格式和证据一致性
- `finalizer.py`
  - 整理最终输出
- `state_machine.py`
  - 整个 agent 的主循环
  - 控制状态流转和步骤执行

这部分是当前系统的真正核心。

#### 4.4 `agent_core/policies/`

这里定义任务策略。

当前已经有三类内置 policy：

- `general_qa`
- `calculation_only`
- `mixed_analysis`

它们定义的是：

- 某类任务默认怎么拆步骤
- 某类步骤有哪些 candidate skills

目前 small case 使用的是 `mixed_analysis`。

#### 4.5 `agent_core/skills/`

这里是可插拔的能力层。

当前已经实现的 skills 包括：

- `parser`
  - 规则版 query parser
- `llm_query_parser`
  - LLM 版 query parser
- `retrieval`
  - 当前是 mock retrieval
- `calculator`
  - 规则算术计算器
- `report_writer`
  - 规则版最终报告生成
- `llm_report_writer`
  - LLM 版最终报告生成

skills 的意义是把“能力”和“总控”分离开。总控只决定该做什么，具体能力由 skill 执行。

#### 4.6 `agent_core/services/`

这里负责和外部服务连接。

当前最重要的是：

- `llm_client.py`

它现在已经支持 OpenAI-compatible 接口，也就是说既可以接：

- 你本地 `/home/xqin5/llm` 启动的服务
- 未来别人的公开 API

通过这层封装，我们避免把代码写死在某一种 LLM 服务上。

#### 4.7 `agent_core/examples/`

这里是可直接运行的示例。

当前最重要的是：

- `run_small_case.py`
- `test_local_agent.py`

其中 `test_local_agent.py` 是目前最实用的调试入口，它会打印：

- health check
- planning mode
- 每一步的 selected skill
- routing mode
- final response

#### 4.8 `tests/`

这里是自动化测试。

当前已经有：

- `test_small_case.py`
- `test_local_llm_integration.py`

这两部分保证我们对 small case 和 LLM 集成的核心逻辑有基本回归验证。

#### 4.9 `runs/`

这里保存实际运行结果。

每次运行后会输出：

- `run-xxx_state.json`
- `run-xxx_trace.json`

这部分非常重要，因为它提供了：

- 中间 artifacts
- 执行过程
- planner / router 的模式
- 最终输出

方便后面 debug、复盘、做 benchmark 记录。

---

### 5. 我们跑了什么例子

当前已经跑通的是一个 `mixed_analysis` 的小 case。

测试 query 是：

```text
Based on the office handbook, what is the lunch reimbursement limit, and what is 18 + 24? Return a short report with evidence.
```

这个任务同时包含两类要求：

- 一类是基于文档/政策的检索
- 一类是简单算术计算

所以非常适合用来测试 agent 的总控能力，因为它要求系统同时完成：

- task parsing
- plan generation
- route selection
- retrieval
- calculation
- report synthesis
- evidence binding

也就是说，这个 small case 虽然简单，但它覆盖了总控主链路的关键环节。

---

### 6. 这次跑通后的效果是什么样的

在最近成功的运行里，系统已经达到下面这个状态：

- `planning_mode = llm`
- `step-1 selected_skill = llm_query_parser`
- `step-1 routing_mode = llm`
- `step-4 selected_skill = llm_report_writer`
- `step-4 routing_mode = llm`
- 最终输出 schema 合法
- 最终有 evidence ids

代表性的成功结果可参考：

- `runs/run-39b8452d_state.json`
- `runs/run-a80045c9_state.json`
- `runs/run-c4a8350d_state.json`
- `runs/run-fee90b16_state.json`
- `runs/run-0f026075_state.json`

这些 run 表明：

- LLM 已经真正进入 planning
- LLM 已经真正进入关键 routing
- LLM 已经真正参与 query parsing
- LLM 已经真正参与 final report writing

同时仍然保留 deterministic skills：

- `retrieval`
- `calculator`

这也是当前设计上合理的做法，因为工具型步骤不一定需要完全交给 LLM。

---

### 7. 目前这个核心已经能说明什么

它说明我们现在已经不只是“有一个想法”，而是已经有了一个真实可运行的总控底座。

换句话说，后面团队成员不需要再从零开始讨论“agent 框架怎么搭”，因为下面这些基础能力已经具备：

- 显式状态机
- 统一 schema
- task policy
- planner
- router
- verifier
- finalizer
- trace
- 本地 LLM 接入
- OpenAI-compatible API 兼容

现在更值得做的，不是重写总控，而是往这个核心上叠加真实能力。

---

### 8. 希望大家接下来如何在这个核心上继续完善

希望团队后续是在当前核心基础上继续扩展，而不是分散地重新做多个小框架。

优先建议大家做的是：

#### 8.1 把 mock retrieval 升级成真实 RAG

这是最直接、最有价值的一步。

因为当前 `retrieval` 还是内置字典匹配，后面如果要做 research agent，就应该尽快替换成：

- paper/document chunking
- embedding
- vector search
- reranking

#### 8.2 增加真正面向 research 的 skills

例如：

- paper retrieval
- citation extraction
- claim verification
- experiment summarization
- note generation
- paper comparison
- hypothesis generation

#### 8.3 增强 verifier

现在 verifier 主要做 schema 和 evidence 检查，后面可以加：

- citation verifier
- numeric verifier
- reasoning consistency verifier
- output template verifier

#### 8.4 增加长期 memory 和 session

后面如果要做更长任务，可以继续加：

- session state
- episodic memory
- result cache
- task history

#### 8.5 增加 API 层

后面最好把现在这个 runner 包装成一个服务接口，方便：

- benchmark 批量运行
- 多人协作调用
- 统一前端或评测接口

---

### 9. 当前阶段建议的目标

当前建议团队先不要把目标铺得太散。

最合理的近期目标是：

> 先以 Research Agent 的第一个 task 为目标，围绕比赛需求，把现有核心逐步扩成一个真正可参赛、可迭代的研究型 agent。

这样做有几个好处：

- 目标明确
- 能尽快形成闭环
- 可以用比赛 task 反推缺哪些 skills 和 verifiers
- 可以尽快把 mock 模块替换成真实模块

换句话说，当前这套总控核心已经够用了，下一步重点应该从“框架搭建”转向“任务能力建设”。

---

### 10. 总结

目前 `/home/xqin5/agenticAI` 里的系统，已经完成了 agent 核心最关键的一步：

> 我们已经搭建出一个可运行、可扩展、可接本地 LLM、可兼容 OpenAI-compatible API 的 agent orchestration core。

这个核心当前已经能：

- 解析任务
- 生成计划
- 路由技能
- 执行步骤
- 校验输出
- 记录 trace
- 接入外部 LLM

而且已经通过小 case 验证了：

- LLM planning 可以工作
- LLM routing 可以工作
- LLM query parsing 可以工作
- LLM report writing 可以工作

因此，希望后续团队成员直接以这个核心为基础继续完善我们真正需要的 agent 功能和优化，而不是另起炉灶。

当前最适合的下一步目标，是围绕 **Research Agent 的第一个 task** 去做面向比赛的能力扩展和工程优化。

---

## English Version

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
├── blueprint
├── 代码实现详解.md
├── Agent系统核心说明_双语.md
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
