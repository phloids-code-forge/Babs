## Section 5: The Autonomous Code Quality Pipeline & Standards Enforcement

Treat the Coding Worker as a first-class agent pipeline with its own Evaluator-Optimizer loop. Code quality is not optional and not aspirational. It is enforced by deterministic tooling at every iteration. No code leaves the Coding Worker without passing both standards enforcement and functional verification.

**Code Standards Toolchain:**

The following tools are pre-installed in the Coding Worker's container. They are deterministic (produce ground-truth pass/fail results) and therefore fall under the Code Before Memory rule. The Coding Worker does not "remember" that code should be well-formatted. It runs the tools and gets a concrete verdict.

- **Ruff** (formatter + linter). Handles code formatting (consistent style, import ordering, line length) and linting (unused imports, dead code, shadowed variables, bare excepts, magic numbers, common bugs). Replaces the need for black, flake8, isort, and pyflakes. Single tool, single config file. The Ruff rule set must include the `D` family (pydocstyle) configured for Google-style docstring enforcement on all public functions and classes.
- **mypy** (static type checker). Validates type hint consistency. If a function declares it returns `WorkerStatus`, mypy verifies every code path returns a `WorkerStatus`. Catches subtle bugs that linting misses, particularly the kind of inconsistent return types that LLMs produce.
- **Playwright + headless Chromium** (rendered output validation). Only invoked when the task produces rendered output. See Rendered Output Validation below.

**The Execution Loop:**

The Coding Worker's self-validation loop has two stages. Both must pass before results are returned to the Supervisor.

*Stage 1: Standards Enforcement*
1. Write the code.
2. Run `ruff format` (auto-fix style). This is non-interactive and always succeeds.
3. Run `ruff check` (lint). Auto-fix what is auto-fixable. If unfixable violations remain, revise the code and return to step 2.
4. Run `mypy` (type check). If type errors are found, revise the code and return to step 2.
5. Standards pass. Proceed to Stage 2.

*Stage 2: Functional Verification*
6. Send the code to the headless Jupyter Kernel for execution.
7. If execution fails, parse the error traceback, revise the code, and return to step 1 (full loop, because revisions may introduce new standards violations).
8. If the task produced rendered output (HTML, dashboard component, formatted document), run the Rendered Output Validation step. If it fails, revise and return to step 1.
9. All checks pass. Return results to the Supervisor.

- **Loop Limit:** Define a maximum iteration count (e.g., 5 outer loops, where one outer loop is a complete pass through both stages). If the Coding Worker cannot produce fully passing code within the limit, it must escalate to the Supervisor with the raw error context, partial code, and a summary of what it tried. It must not loop forever.
- Specify how the Jupyter Kernel container is sandboxed (filesystem access, network access, execution timeout per cell).
- The Code Before Memory Rule applies to the entire pipeline: every validation step uses deterministic tooling to produce ground-truth results, not heuristic judgment.

**Rendered Output Validation:**

If the task produces any rendered output (HTML page, dashboard component, formatted report, email template), the Coding Worker must validate the visual output before returning it. The principle: if a rendering defect is machine-detectable, it must not reach the user.

- Playwright renders the output in headless Chromium at three viewport sizes: desktop (1920x1080), tablet (768x1024), and mobile (375x812).
- A validation script checks each render for: elements positioned outside the viewport, content overflowing its container, clipped or truncated text, broken image references, z-index stacking issues causing hidden content.
- Validation failures re-enter the fix loop at step 1 (same as any other code error).
- This costs no VRAM. Playwright and headless Chromium are CPU-only. The Coding Worker container must include Playwright and a headless Chromium binary. The architect should account for the container size increase (~400MB for the Chromium binary) in the Storage Allocation Strategy but not in the Memory Ledger (the browser process is ephemeral, launching only during validation and exiting immediately after).

**Coding Worker Procedural Memory Dependency:**

Before writing any code, the Coding Worker must pull the relevant Procedural Memory entries for the task domain. At minimum, every Python task pulls the **"Python Code Standards"** entry (see Section 12, Cold Start Bootstrap). This entry defines naming conventions, structural rules, documentation requirements, and quality principles. The Coding Worker does not rely on base model training alone for code style decisions.

This separation means code standards can be updated by modifying the Procedural Memory entry without changing the Coding Worker's model, container, or configuration.

---

## Section 6: Secure External Agency & Approval Gates

Design the system to safely execute external actions using the Principle of Least Privilege.

**External Agency Examples:**
- Fractional trading via Alpaca API
- Drafting/sending emails via Gmail API
- Calendar management, web research, file operations

**Trust Tier Implementation (Philosophy Document Section 2):**
- The orchestration layer must enforce the four Trust Tiers (Tier 0: Full Autonomy, Tier 1: Notify and Execute, Tier 2: Propose and Wait, Tier 3: Confirm Twice) for every external action.
- Every external tool integration must be tagged with its Trust Tier in the configuration layer.
- The Supervisor must route actions through the approval gate before execution. For Tier 2 and 3, the action is queued and surfaced to phloid via the dashboard and the Discord notification channel.
- Implement timeout behavior: Tier 2 actions park after 30 minutes (configurable) with no approval. Tier 3 actions have no timeout and never auto-execute.
- phloid can configure Tier overrides (e.g., promote specific Tier 2 actions to Tier 1) via version-controlled config files.
- **Trust Tiers apply regardless of thread type.** Buddy mode does not relax approval requirements.

**Discord Notification Service:**
- Hosted on the G14 auxiliary node. A lightweight service on the pub/sub bus that listens for notification events (Tier 2/3 approval requests, system alerts, proactive notifications from the Event Listener) and dispatches them to a private Discord server via bot API or webhook.
- Tier 2/3 approval requests are posted as rich embeds with inline reaction buttons (approve/reject). phloid taps the reaction, the bot relays the response back to the orchestration layer via the pub/sub bus.
- Channel structure: separate channels for approvals, system alerts, and general notifications.
- If the Discord bot on the G14 is unavailable (G14 offline), the Spark activates a dormant local Discord bot container (see Section 9). If the Discord webhook itself fails, notifications queue locally and the dashboard shows a "notification delivery failed" banner. The Graceful Degradation Matrix must cover both scenarios.
- Discord bot token and webhook URL are stored in the version-controlled config layer.

**Action Rate Limiting:**
- Define per-action-type rate limits to prevent runaway execution loops (e.g., max 5 trades per hour, max 10 outbound emails per day).
- Rate limits are configurable and stored in the config layer.
- If a rate limit is hit, the action is blocked and the Supervisor is notified. It does not silently retry.

**Network Isolation:**
- Define whether Babs has unrestricted internet access or routes through a local firewall/proxy.
- For a system that can execute trades and send emails, specify the network security boundary explicitly.

**Cloud Escalation Protocol (Philosophy Document Section 3, Cloud Escalation Principle):**

Babs may escalate tasks to cloud models when local models are insufficient. Cloud models are accessed through the Unified Model Registry (Section 1) and treated as remote Workers, dispatched through the same orchestration layer as local Workers but with additional gates.

- **Escalation triggers (v1, rule-based).** The routing classifier maintains a list of task types that always escalate: full architecture planning, complex multi-file refactors, long-form writing above a configurable quality bar, tasks where phloid explicitly requests a cloud model. The Reflection Loop can propose new auto-escalation rules based on observed correction patterns (e.g., if Babs is consistently corrected on a task type, propose escalating it). These learned rules follow the standard tentative-to-durable lifecycle (Philosophy Document Section 5).
- **Context minimization.** The same context pruning protocol used for local Worker dispatch (Section 3) applies to cloud API calls. Babs constructs a minimal context package: task description, relevant Procedural Memory entries, required data, and nothing else. No episodic memory dumps. No personal partition content unless explicitly relevant and phloid-approved. This is both a privacy measure and a cost measure.
- **Response reprocessing.** Cloud model responses are raw output. The Supervisor reprocesses every cloud response through Babs' personality before presenting it to phloid. She may add her own assessment, agree or disagree with the cloud model's recommendation, or synthesize multiple cloud responses. She never attributes the response to the cloud model ("Claude says X"). She consulted an expert and came back with the answer.
- **Cost gating (Philosophy Document Section 3, Cost-Aware Routing).** Cloud escalations are governed by per-provider token budgets stored in the configuration layer. Routine escalations (within budget) are Tier 1: notify and execute. Escalations that would push a budget past a configurable warning threshold (default 80%) are Tier 2: propose and wait. The routing logic selects the cheapest model that meets the capability requirement, following the hierarchy: local first, cheap cloud second, premium cloud last.
- **Provider diversity.** Three cloud provider pools are available at launch: Anthropic (Claude, via Pro subscription), Google (Gemini 3.1 Pro, via AI Pro subscription and Antigravity), and OpenRouter (DeepSeek, and any other model on the OpenRouter marketplace). Each pool has independent budget tracking. When one pool is rate-limited or over budget, Babs routes to alternatives automatically.
- **Latency-aware fallback.** If a cloud API response exceeds a configurable threshold (default 15 seconds), the Supervisor proceeds with local-only reasoning and flags the task for async cloud follow-up when the API becomes responsive.
- **Token circuit breaker.** Per-request token cap and rolling daily/monthly spend ceiling per provider. Prevents infinite billing loops from malformed requests or runaway retry logic.
- **API translation adapter.** Cloud model responses are normalized into the same schema used by local Workers so downstream consumers (the Supervisor, the audit log, the dashboard) do not need provider-specific handling.

---

## Section 7: The Immutable Audit Log

**This is a dedicated section, not a subsection of observability. It is a safety-critical system for a platform that moves money and sends communications.**

**Requirements:**
- Every external action Babs takes must be recorded in an append-only, immutable audit log.
- Each entry must include: timestamp, requesting task ID, requesting agent, action type, Trust Tier, approval method (auto/user), exact parameters sent, response received, success/failure status.
- Babs cannot delete or modify audit entries under any circumstance.
- The audit log must be stored separately from Episodic Memory (it is not conversational context, it is an accountability record).
- Define the storage format (SQLite WAL, dedicated append-only table, or structured log file).
- The audit log must be browsable and searchable via the dashboard.
- The audit log is included in all three backup tiers (local, LAN, off-site). See Section 14.

**Anomaly Detection (Philosophy Document Section 7):**
- Monitor the audit log for patterns indicating malfunction: unusual action frequency, repeated failures, orphaned actions not traced to a task decomposition chain, actions auto-approved via Tier 1 overrides that would have been Tier 2+ under defaults.
- Anomalies trigger a dashboard alert. Severe anomalies pause the relevant agent until phloid reviews.

---

## Section 8: Dynamic Agent Creation (The Self-Expansion Protocol)

**Babs must be able to create, evaluate, and retire her own specialized agents.**

This section implements the protocol defined in Philosophy Document Section 6.

**Capability Registry:**
- Maintain a runtime catalog of all active agents: name, purpose, base model, tool access, Trust Tier, resource footprint, performance metrics.
- The Supervisor consults this registry when decomposing tasks to determine if an existing agent matches the need.

**Agent Blueprint System:**
- When no existing agent matches a task, Babs may propose a new one.
- The blueprint includes: purpose description, base model selection (from locally available models), system prompt, tool access list, input/output schema, Trust Tier request, estimated memory footprint.
- Agents requiring external API access or elevated permissions require phloid's approval (Tier 2). Internal-only agents are Tier 1 (notify and execute).

**Runtime Container Orchestration:**
- The Docker orchestration layer must expose an API that the Supervisor can call to spin up new agent containers at runtime. Static docker-compose alone is insufficient.
- Define the orchestration mechanism (Docker API, Podman, or a lightweight container manager) and the security constraints on what the Supervisor can and cannot spin up.

**Evaluation and Lifecycle:**
- New agents run in a probationary period (configurable, default 10 tasks).
- Babs cannot create agents that exceed the Memory Ledger allocation. She must account for resource cost and may need to retire a low-priority agent to make room.
- Define the maximum number of concurrent self-created agents (configurable).

**Agent Probation Evaluation Layering:**

Three evaluation layers run simultaneously during probation:

- **Layer 1 (Deterministic checks).** Mandatory for all agent outputs that have verifiable validation. Code passes Ruff, mypy, and execution. Research citations resolve. Data outputs match schema. This is the Code Before Memory rule applied to evaluation.
- **Layer 2 (Split evaluator).** A Worker model runs an adversarial evaluation pass on every probation task. The evaluator receives the task, the output, and the quality criteria. It does not know it is evaluating a Babs-created agent. It produces a pass/fail verdict with reasoning.
- **Layer 3 (phloid spot-check).** 3 of 10 probation tasks (configurable) are flagged for phloid's review. Discord ping when ready. The dashboard shows task input, agent output, and three buttons: "Looks good," "Needs work" (optional comment), "Kill it" (immediate retirement).

**Agent Promotion:**

Agent promotion requires explicit phloid approval but is lightweight. When probation ends, the dashboard surfaces a promotion card showing: tasks completed, deterministic pass rate, evaluator pass rate, links to the 3 spot-checked results, and Babs' explanation of why she created the agent and how it performed. phloid taps promote or retire.

Babs provides explanatory context on promotion cards for early agents. As phloid gets comfortable (measured by time-on-card decreasing), explanations taper. This is a learnable Reflection Loop behavior.

**MCP Compatibility:**
- All agent tool schemas (both architect-defined and Babs-created) should follow the Model Context Protocol (MCP) format for tool definitions.
- This ensures future compatibility with MCP clients and servers without refactoring tool integrations.
- Define the MCP schema structure used for tool registration.

---
