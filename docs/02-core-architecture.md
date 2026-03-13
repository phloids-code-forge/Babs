## Section 1: The Supervisor-Worker Hierarchy & Hardware Allocation

Design a strict multi-agent topology using a local model serving engine inside Docker containers.

**Model Serving Engine:**

**RESOLVED: vLLM with community NVFP4 patches is the day-one engine.**

The MSI EdgeXpert runs the GB10 at SM 12.1 compute capability, which is unique to the DGX Spark platform. SM 12.1 lacks hardware support for a specific PTX instruction required by NVFP4 quantization. The community has resolved this with software patches that provide a bit-manipulation E2M1 conversion path, route SM 12.1 to SM 12.0 optimized code paths, and enable the Marlin MoE backend for NVFP4. These patches make NVFP4 ~20% faster than AWQ on the Spark. With the Supervisor model now being NVIDIA Nemotron 3 Super (NVIDIA's own model, natively pre-trained in NVFP4 for Blackwell), first-party or near-first-party vLLM support is expected. The HuggingFace model card provides vLLM and SGLang serving configurations directly.

- **Day-one stack:** vLLM with community NVFP4 patches (Avarok `dgx-vllm` image or equivalent bleeding-edge build at deployment time, e.g., vLLM 0.17.0+ with SM121 MXFP4 patches). The architect must verify the current recommended community image on the DGX Spark developer forums before deployment.
- **Planned addition: SGLang.** SGLang's RadixAttention (radix-tree-based KV cache that reuses shared prefixes across requests) is architecturally desirable for the Supervisor, which maintains persistent system prompts and multi-turn conversation threads. Prefix caching yields 75-90% cache hit rates on multi-turn workloads and 10-20% additional throughput gains. SGLang also offers ~3x faster constrained decoding for structured output (JSON/XML) via compressed FSM. The Nemotron 3 Super HuggingFace model card includes SGLang serving instructions (`sglang v0.5.9`), so SGLang compatibility is confirmed. Evaluate SGLang for the Supervisor at deployment time, potentially running both engines: SGLang for the Supervisor (prefix caching, structured output) and vLLM for Workers (broader model support, well-tested model loading/unloading).
- Both engines expose OpenAI-compatible APIs. The orchestration layer routes requests by endpoint URL, making the serving engine transparent to higher layers.

**The Supervisor (Babs):**

- **Leading candidate: NVIDIA Nemotron 3 Super 120B-A12B (NVFP4 quantization).**
- This is a hybrid Mamba-Transformer Latent Mixture-of-Experts architecture. 120B total parameters, 12B active parameters per token. Mamba-2 layers handle long-range sequence modeling efficiently, Transformer attention layers handle precision reasoning, and LatentMoE routes tokens through a compressed latent space before expert computation, activating 4x as many experts for the same inference cost as standard MoE.
- **Natively pre-trained in NVFP4** from the first gradient update on NVIDIA Blackwell hardware. Unlike post-training-quantized models, there is no quality loss from compression. This is NVIDIA's own model built for their own hardware, eliminating the SM121 kernel compatibility issues that affected third-party NVFP4 quants.
- **NVFP4 quantized weight footprint: approximately 67GB**, leaving approximately 61GB of the 115GB budget for KV cache, services, and Worker models. This is ~8.6GB more headroom than the previous Qwen3.5 candidate.
- **Native 1M-token context window** with strong long-context accuracy (96%+ on RULER at 256K, 95.7% at 512K, 91.75% at 1M). The Mamba layers provide fundamentally better memory efficiency for long sequences compared to standard quadratic-attention transformers. The Memory Ledger must account for KV cache at 32K, 64K, 128K, and 256K context lengths. FP8 KV cache quantization is recommended (model card default). The architect should recommend a practical maximum context length given the overall memory budget.
- **Strong tool calling and agentic performance.** Scores 61.15 average on TauBench V2 (airline/retail/telecom agent benchmarks). Designed and trained specifically for multi-agent orchestration workflows with proficient tool calling across large tool pools. For a Supervisor that orchestrates Workers via structured tool calls, this is critical.
- **Granular reasoning budget control.** Three inference modes: full reasoning (chain-of-thought enabled), low-effort reasoning (significantly fewer reasoning tokens), and budget-controlled reasoning (hard token ceiling on the reasoning trace). This maps directly to Intelligence Routing: no reasoning for Class A (Cached Response Pool or thinking disabled), low-effort for routine Class B, full reasoning for Class B/C interactions requiring depth. This is a significant improvement over binary thinking on/off.
- **Built-in Multi-Token Prediction (MTP)** for native speculative decoding without a separate draft model. MTP uses a shared-weight design across prediction heads, generating multiple future tokens per forward pass. This reduces the need for an external speculative decoding setup (Eagle3 or similar) as a latency contingency.
- **Up to 7.5x higher inference throughput than Qwen3.5-122B** on the 8k input / 16k output benchmark (NVIDIA-reported). Real-world gains will vary, but the architectural efficiency advantage is substantial.
- **NVIDIA Nemotron Open Model License.** Permissive, commercial use permitted, customization and deployment on own infrastructure permitted.
- **Primary alternative: gpt-oss-120b (MXFP4 quantization).** 117B total parameters, 5.1B active per token. Strong reasoning (near o4-mini parity), good tool use, Apache 2.0. Uses the harmony response format (requires serving engine support). Community benchmarks on the Spark show ~59 tok/s single-node, ~81 tok/s on two-node cluster with recent patches. The harmony format may constrain system prompt engineering; validate this if evaluating gpt-oss-120b as a Supervisor candidate.
- **FP8 escape hatch:** If Nemotron 3 Super quality or stability issues emerge under NVFP4, the FP8 variant is available. The FP8 model is larger and would be tight against the 115GB ceiling. The architect should determine whether FP8 is feasible with reduced context length and no concurrent Worker, or whether Nemotron 3 Nano 30B-A3B NVFP4 (community-confirmed on the Spark at 65+ tok/s) should serve as the fallback Supervisor.

**The Workers:**

Workers execute tasks that the Supervisor has already decomposed and specified. They receive structured instructions, relevant Procedural Memory entries, and constrained context. They do not plan, reason about task decomposition, or maintain personality. They execute.

- **Default coding/reasoning Worker: Qwen3.5-9B.**
  - Dense model from the Qwen3.5 small series, optimized for reasoning via scaled RL training. Matches or surpasses GPT-OSS-120B (13x its size) on GPQA Diamond (81.7 vs 71.5) and HMMT math (83.2 vs 76.7).
  - ~5-6GB in NVFP4 or INT4 quantization. Fast token generation on the Spark.
  - Loaded on demand, unloaded when task completes. Not permanently resident.
  - Zero personality (Temperature ~0.0). Execute strictly via structured API formatting.

- **Lightweight utility model: Qwen3.5-4B.**
  - Multimodal base model designed for lightweight agent tasks: classification, routing, triage, UI navigation, document analysis.
  - ~2-3GB in quantized form. Small enough to remain always-resident alongside the Supervisor without meaningful memory pressure.
  - Use cases: incoming message classification for the routing layer, quick metadata extraction, intent detection, lightweight structured output generation where spinning up a larger Worker is unnecessary.

- **Heavy Worker (on-demand): Qwen3.5-35B-A3B.**
  - 35B total, 3B active. Surpasses previous-generation Qwen3-235B-A22B despite activating a fraction of the parameters.
  - ~15-18GB in NVFP4/INT4. Loaded on demand for complex tasks that exceed the 9B Worker's capability.
  - At 70+ tok/s on community-patched vLLM (or 86+ tok/s in INT4 via Marlin), fast enough for interactive use.

- **Evaluation alternatives:** gpt-oss-20b (21B total, 3.6B active), NVIDIA Nemotron 3 Nano 30B-A3B (NVFP4-native, hybrid Mamba-Transformer MoE, community-confirmed on the Spark at 65+ tok/s, same architectural family as the Supervisor). Benchmark at deployment time against the Qwen3.5 candidates for each Worker role.

**Supervisor Direct-Handling Rule:**

The Supervisor evaluates each incoming request and handles it directly when the task is within its capability and no delegation benefit exists. Delegation to a Worker occurs only when the task requires:

- **Sandboxed code execution.** The task needs to run in an isolated Jupyter kernel or Docker container.
- **Long-running iteration.** The task involves a write-lint-test-fix loop that would tie up the Supervisor's context window and make it unresponsive to phloid.
- **Parallel decomposition.** The task benefits from splitting into multiple subtasks that run concurrently.
- **Freeing the Supervisor for responsiveness.** phloid is actively chatting and a background task would block the conversation.

For a single-user system, the Supervisor is idle most of the time. Delegating simple tasks to a less capable Worker model is a quality downgrade for no reason. The routing classifier must account for Supervisor availability (is it currently in a conversation? is it mid-inference?) before dispatching to Workers. If the Supervisor is free, it handles the task itself.

This rule applies across all interaction classes. Class A and most Class B interactions are always Supervisor-direct. Class C tasks are delegated when they involve iteration loops or sandboxed execution. Class D background tasks (Reflection Loop, consolidation) use Workers for mechanical steps and the Supervisor for evaluative steps, as specified in Section 12.

**Dynamic Model Loading:**

The Memory Ledger must account for **dynamic model swapping**, not just static concurrent allocation. The Supervisor model stays resident at all times. Everything else loads and unloads on demand.

- Workers are transient. When a task is dispatched, the appropriate Worker model loads. When the task completes, the model unloads and memory is reclaimed.
- ComfyUI pipelines share the same dynamic memory pool. When the Supervisor dispatches an image generation task, the Worker unloads (if loaded), the diffusion model loads, ComfyUI runs the workflow, the diffusion model unloads, and the memory is returned to the pool.
- The architect must specify: model load latency budgets (expected time from "load model" to "ready to serve"), memory reclamation guarantees (how quickly is memory freed after model unload, and is it fully reclaimed or fragmented), and the mechanism for model lifecycle management (vLLM API calls, container stop/start, or separate serving instances per model).
- The always-resident utility model (Qwen3.5-4B at ~2-3GB) is exempt from dynamic loading. It stays loaded alongside the Supervisor.
- The Memory Ledger must show three budget scenarios: (a) Supervisor + utility model only (bootstrap/idle), (b) Supervisor + utility + one active Worker (typical operation), (c) Supervisor + utility + ComfyUI pipeline (image generation). Each scenario must sum to no more than 115GB.

**Unified Model Registry:**

All models available to Babs, both local and remote, are registered in a single abstraction layer. The Supervisor and routing classifier select models from this registry without caring whether the model runs on the Spark, the G14, or a remote API endpoint. Same interface, different backend.

Each registry entry includes:
- **Model identifier.** Unique name (e.g., `nemotron3-super-120b-a12b-nvfp4-local`, `claude-opus-4.6-api`, `deepseek-v3-openrouter`).
- **Location type.** `local` (vLLM/SGLang on Spark), `lan` (G14 auxiliary), or `remote` (cloud API).
- **Endpoint.** OpenAI-compatible API URL for local models, provider API URL for remote models.
- **Capability profile.** Task types this model excels at (coding, reasoning, creative writing, structured output, tool use), with benchmark scores where available.
- **Cost profile.** Zero for local models. Per-input-token and per-output-token rates for remote models.
- **Latency profile.** Expected time-to-first-token and tokens-per-second. Remote models include network latency estimates.
- **Authorization.** API key reference (stored in secrets management, not in the registry itself) for remote models.
- **Budget group.** Which provider budget pool this model draws from (e.g., `anthropic-pro`, `google-ai-pro`, `openrouter`). Local models have no budget group.
- **Status.** `active`, `available` (downloaded but not loaded), `remote-only` (no local weights), `evaluating` (under scouting assessment), `retired`.

The registry is stored in the version-controlled configuration layer. Babs can propose additions (via the Model Scouting Pipeline, see Section 12) but cannot activate a new model without phloid's approval (Tier 2 for remote models that incur cost, Tier 1 for local model swaps between already-approved candidates).

The test-before-download flow uses the registry directly: a model starts as a `remote-only` entry with an OpenRouter endpoint. Babs evaluates it via API. If approved, she downloads the weights, creates a `local` entry pointing to vLLM, and the `remote-only` entry is retired. The rest of the system does not need to know the model moved.

**Intelligence Routing Layer:**
- Implement the interaction class system defined in Philosophy Document Section 3 (Class A: Reflex, Class B: Interactive, Class C: Deep Work, Class D: Background).
- **Cached Response Pool:** A pool of variable-enriched response templates serves pure Class A reflexes (greetings, acknowledgments) without model inference. Templates include variable slots for: time of day, day of week, pending task count, unresolved approvals, time since last session, and system state. The pool is served by the orchestration layer directly. The Reflection Loop maintains the pool (see Philosophy Document Section 5). Seed the pool at bootstrap with approximately 30-40 templates.
- **Reasoning effort as a routing input.** The Nemotron 3 Super model supports three reasoning modes: full reasoning (chain-of-thought enabled), low-effort reasoning (significantly fewer reasoning tokens), and budget-controlled reasoning (hard token ceiling on the reasoning trace, closes at the next newline before the budget is hit). The routing classifier should: disable reasoning entirely for Class A interactions (fast, no reasoning overhead), use low-effort mode for routine Class B interactions, and enable full reasoning for complex Class B/C interactions. Budget-controlled mode is available for latency-sensitive tasks where some reasoning is beneficial but full reasoning is too slow. This granular control replaces the binary thinking on/off approach.
- **Fast-path model is an open slot.** The classifier routes Class A interactions to the Cached Response Pool or the Supervisor with thinking disabled. This routing point is designed so a dedicated fast-path model can be slotted in later with no architectural changes. Document this as an open slot, not a missing component.
- Design a lightweight classifier (rule-based for v1, upgradeable to a small model later) that inspects incoming messages and routes them to the appropriate reasoning effort level and processing path. The always-resident Qwen3.5-4B utility model is a candidate for this classifier role if rule-based routing proves insufficient.
- **Thread type awareness.** The classifier must be aware of the current thread type (work or buddy) and factor this into routing decisions. Buddy-mode conversations are typically Class A or B (casual, conversational). Work-mode conversations span all classes.
- The Supervisor retains authority to reclassify any interaction mid-task.

**Requirements:**
- Define specific PagedAttention and memory allocation strategies to ensure 128GB of unified memory is not oversubscribed during parallel agent execution.
- Specify maximum concurrent worker count based on the Memory Ledger. Given dynamic model loading, this is likely 1 active Worker at a time on a single Spark.
- Define a **Model Swap Protocol**: how to hot-swap a Worker's underlying model (e.g., upgrading to a newer SLM) without bringing down the Supervisor or other Workers. The serving engine supports model reloading, but the orchestration layer must handle graceful drain and reconnection. This protocol also governs transitions between Worker and ComfyUI pipeline modes.

---

## Section 2: Orchestration & Communication

**Agent Orchestration:**
- Define the orchestration framework explicitly. Options include a custom lightweight Python state machine, LangGraph, or similar. Justify the choice with tradeoffs (dependency weight, flexibility, debuggability, community support).
- The orchestration layer must support: task decomposition, parallel fan-out to multiple Workers, result aggregation, retry logic, and priority-based preemption.

**Pub/Sub Bus:**
- Anchor the entire inter-agent communication layer on a Pub/Sub message broker (Redis Streams, MQTT, or NATS). Justify the choice.
- All agent-to-agent communication must flow through the bus. No direct inter-container calls.
- **The bus must span the LAN**, connecting both the Spark and the G14 auxiliary node. Both nodes subscribe to the same cluster. Worker task assignment and service routing must be node-aware: the Supervisor knows which node a service lives on and can route accordingly.
- This enables zero-refactor modularity: any agent can be replaced, upgraded, or scaled without touching others.

**Priority & Interrupt System:**
- Define at least 3 priority tiers (e.g., Critical/Interactive/Background).
- If Babs is mid-way through a long background task (e.g., code generation) and the user initiates a real-time voice query, the Supervisor must be able to preempt or park the background task and respond interactively within 2 seconds.
- Specify how task state is preserved during preemption and resumed afterward.

**Interruption Handling Protocol:**

The serving engine must support generation cancellation (vLLM does). The following four interruption scenarios define required behavior:

1. **Correction or refinement mid-stream.** Cancel generation immediately. Merge the interruption with the original request and regenerate. The partial response stays visible in the UI but is marked as interrupted.
2. **Unrelated new request mid-stream.** Finish or truncate the current response at a natural stopping point, then handle the new request immediately. No meta-commentary about the pivot.
3. **New message during async Class C work.** Handle the new message independently. The routing classifier must be aware of in-flight Class C tasks to determine if the interruption is an amendment to the running task or an independent request. If related, amend the worker dispatch. If unrelated, process as a new interaction while workers continue. If ambiguous, Babs asks (v1 behavior, learnable over time).
4. **Rapid multi-message input.** Debounce window of approximately 1.5 seconds (configurable). Cancel generation on the first interrupt, collect additional messages within the window, concatenate into a single input before processing.

**Task Persistence Across Restarts:**
- If the system reboots mid-workflow, in-flight tasks must not be silently lost.
- The orchestration layer must serialize durable task state to disk (via the pub/sub broker's persistence layer or a separate state store).
- On restart, the system must detect incomplete tasks and either resume them or surface them to phloid for re-initiation.
- Define what metadata is persisted per task (task ID, current step, assigned worker, intermediate results, priority, timestamp).

**Scheduled and Recurring Tasks:**
- Design a persistent task scheduler that survives reboots.
- phloid must be able to define recurring tasks ("every market open, check my positions", "every Sunday, summarize the week") via the dashboard or conversation.
- Babs must be able to propose recurring tasks after observing repeated patterns (governed by the Learning Mechanism in Philosophy Document Section 5).
- Scheduled tasks are stored in the version-controlled configuration layer, not in conversational memory.
- Define the scheduler implementation (cron-based, database-backed, or integrated with the pub/sub broker).

---

## Section 3: Tiered Memory & Context Management

Architect a four-tier memory hierarchy:

1. **Working Memory:** Active session context held in the Supervisor's inference window.
2. **Episodic Memory:** Vectorized conversation logs stored in a local vector database (e.g., Qdrant, ChromaDB). Specify the embedding model used for vectorization. Episodic Memory is partitioned into **work** and **personal** spaces via metadata tagging (see Philosophy Document Section 4, Memory Partitioning).
3. **Semantic Memory:** Hard facts, user preferences, learned heuristics. Structured storage (JSON/SQLite) with vector index overlay.
4. **Procedural Memory:** Versioned instruction sets that tell agents how to perform tasks well. These replace static skill files. See Philosophy Document Section 4 (Procedural Memory: The Skills Layer) for the full specification. Each entry must include: unique ID, version, task domain, instruction content (natural language prose, embedded and retrieved by semantic similarity), authorship (architect-defined or Babs-generated), performance metrics, and last validated date. Metadata is stored in a structured, queryable schema. Instruction content is free-form prose.

**Work/Personal Memory Partitioning (Philosophy Document Section 4):**
- Every Episodic Memory entry must carry a partition tag: `work` or `personal`.
- The tag is assigned based on the thread type (work-mode threads produce `work` entries, buddy-mode threads produce `personal` entries).
- Retrieval behavior respects partition boundaries by default: work-context queries exclude `personal` entries, and vice versa. The Supervisor can override this when cross-partition context is relevant.
- phloid can explicitly promote content across partitions via a "save to project" command (personal to work) or similar mechanism.
- The Reflection Loop has read access to both partitions. It uses `personal` entries for personality learning and `work` entries for task heuristic learning.
- Define the tagging schema and the retrieval bias mechanism (query-time filter, separate collections, or weighted scoring).

**Supervisor Context Window Management:**
- The Supervisor model (Nemotron 3 Super 120B-A12B) has a native 1M-token context window. Define explicitly how Babs manages her own Working Memory as conversations grow long.
- Specify when and how the Supervisor extracts, compresses, or offloads working context to Episodic Memory mid-conversation.
- **Extraction over summarization.** When context must be reduced, the default mechanism is extraction: selectively pulling decisions, open questions, stated preferences, action items, and key facts while preserving phloid's exact framing. The discarded content is conversational filler, back-and-forth, and thinking-out-loud that led to conclusions but is not the conclusion itself. Generative summarization (rewriting shorter) is the fallback for cases where extraction alone cannot meet the token budget, not the default approach.
- Define the trigger (token count threshold, turn count, or both) and the mechanism (rule-based extraction, model-assisted extraction with a lightweight classifier, or hybrid).
- This directly affects conversation quality over time and must be treated as a first-class design decision.

**Context Pruning Protocol:**
- The Supervisor must strip all conversational filler before dispatching sub-tasks to Workers.
- Workers receive only: a structured task directive, the exact required variables, relevant RAG chunks, and applicable Procedural Memory entries.
- Define maximum token budgets per Worker dispatch (e.g., Coding Worker receives no more than 4096 tokens of context).
- Specify the pruning mechanism (rule-based extraction, model-assisted extraction, or hybrid).

**The Code Before Memory Rule (Philosophy Document Section 3):**
- The retrieval pipeline must check whether a task can be answered by deterministic computation before searching memory.
- If yes, route to code execution. If the answer requires recalled context processed by code, retrieve the context, then route to code execution.
- This rule is enforced at the routing layer, not left to the Supervisor's discretion.

**RAG Retrieval Pipeline:**
- Specify chunking strategy for ingested documents (chunk size, overlap, boundary rules).
- Define the retrieval method: pure vector similarity, hybrid (vector + keyword/BM25), or multi-stage with a re-ranking model.
- Specify the re-ranking model if used and its memory footprint in the Memory Ledger.
- Retrieval must pull from multiple memory tiers (episodic, semantic, procedural) and merge results with a unified ranking.

**Knowledge Ingestion Pipeline:**
- Define how new information enters the system: PDFs, codebases, bookmarks, research papers, web pages, structured data files.
- Specify the chunking, embedding, deduplication, and source provenance tracking pipeline.
- Every ingested chunk must retain: source document ID, source type, ingestion timestamp, chunk position in original document.
- Deduplication must prevent the same content from being embedded multiple times when re-ingested.
- **Passive coding session capture** (see Section 11, Development Workflow): file change events and git commits from project directories on the Spark's filesystem are ingested as Episodic Memory entries, tagged with the relevant project.

**Memory Consolidation Pipeline (Philosophy Document Section 4, "The Dreaming Process"):**
- Implement as a Background (Class D) process that runs during idle compute.
- **Merge:** Collapse multiple episodic memories about the same topic by extracting key decisions, facts, preferences, and action items into consolidated entries. Preserve phloid's exact framing on important points. Source conversations are retained but deprioritized in retrieval.
- **Link:** Build an associative graph layer (lightweight, e.g., SQLite edge table) connecting related memories across topics and time.
- **Promote:** Graduate validated patterns and corrections from Episodic to Semantic Memory.
- **Deprecate:** Reduce retrieval priority for stale, superseded, or trivial memories without deleting them.
- Define the consolidation frequency, the maximum compute budget per consolidation cycle, and the safeguards preventing consolidation from corrupting or losing important memories.
- **Cross-partition consolidation:** The Reflection Loop may link entries across work and personal partitions in the associative graph (e.g., "phloid was frustrated" in personal memory links to "phloid rewrote the API" in work memory). The entries themselves remain in their original partitions.

---

## Section 4: Ephemeral Isolation for Sensitive Projects

Detail a protocol for secure, isolated namespaces for sensitive work (financial data, credentials, personal documents).

**Requirements:**
- Triggering a sensitive workspace must spin up dedicated, containerized Worker instances.
- These Workers interact with a **separate, encrypted vector database collection** (not the shared Episodic Memory).
- Upon task completion, the Supervisor's Working Memory must be cleaned of sensitive context via an **extraction pass**: the system extracts decisions made, action items, and non-sensitive results into a sanitized continuation context. A **stub memory** is written to general Episodic Memory recording that a sensitive session occurred on a given date regarding a topic category, without the sensitive content itself. This allows Babs to reference the session's existence without exposing sensitive details in general retrieval. Full session content goes to the encrypted collection only, retrievable by re-entering sensitive mode.
- Define the trigger mechanism (explicit user command, automatic classification, or both).
- Specify encryption at rest and in transit for the isolated namespace.

---
