## Section 11: User Interface & Interaction Layer

**This system needs a daily-driver interface, not just a terminal.**

**Requirements:**
- Design a local web-based dashboard hosted on the Spark (accessible via Tailscale IP from any device, e.g., `http://100.64.x.x:PORT` or a local DNS alias like `http://babs.local`). The Spark is the authoritative host for both the dashboard backend and frontend. The G14 does not serve any dashboard components.
- The dashboard must integrate: chat interface (text I/O with real-time streaming), voice I/O controls (disabled with banner when Whisper is unavailable), active task status and queue visibility, approval queue for Tier 2/3 actions (with approve/reject controls), memory inspection (ability to browse/search Episodic and Semantic memory with partition filtering for work/personal), Procedural Memory browser (view, search, and manage skill entries), learned heuristics inspector (view, override, delete learned behaviors), audit log browser (searchable, filterable), scheduled tasks manager, system health metrics (from the observability stack, including cluster-level node status), manual override controls (cancel tasks, flush memory, trigger sensitive mode), agent registry viewer (active agents, self-created agents, performance metrics), **thread type selector** (work or buddy mode, visually distinct so phloid always knows which mode he is in), and **cloud spend tracker** (per-provider token usage against budget ceilings, current billing period totals, cost-per-task breakdowns for recent cloud escalations).
- The UI must adhere to the "Always Pretty" principle (Philosophy Document Section 8): dark-mode-first, no raw terminal dumps, no unstyled HTML, error states are designed. Professional and polished.
- **Real-time communication:** The dashboard backend must use WebSocket (or SSE) for real-time updates to the frontend. This covers chat streaming, task status changes, approval queue notifications, and system health metrics. HTTP polling is not acceptable for interactive use.

**Buddy Mode UI:**
- Buddy-mode threads must be visually distinct from work-mode threads. Different accent color, different header, or similar visual signal. phloid must never accidentally be in the wrong mode.
- Thread creation offers a mode choice (work or buddy). Default is work.
- A toggle or command allows switching modes mid-thread. The switch is logged and all subsequent messages in the thread are tagged with the new partition.
- The "save to project" command is accessible via a button or slash command within buddy-mode threads. It promotes the selected exchange to work Episodic Memory with a project tag.

**Multimodal I/O:**
- **STT:** Whisper model hosted on the G14 auxiliary node (see Cluster Topology). The dashboard sends audio to the G14's Whisper API endpoint. If the G14 is unavailable, voice input is disabled with a clear UI indicator.
- **TTS:** Sub-millisecond local TTS (Kokoro, XTTS, or similar) hosted on the Spark. Specify model and voice cloning capability if applicable.
- Voice interaction must feel conversational, not command-response. Define the wake-word or push-to-talk mechanism.
- **File/Image Input:** The dashboard must accept file uploads (PDFs, images, code files, data files) and route them through the Knowledge Ingestion Pipeline (Section 3). Image input should be supported for basic visual queries even before Phase 3 VLM integration.

**Private Web Search:**
- Babs uses **SearXNG** hosted on the G14 auxiliary node as a self-hosted, privacy-respecting meta-search engine. SearXNG aggregates results from multiple public search engines without sending user queries directly to Google, Bing, or other providers. Search history stays local.
- SearXNG has a resource entry in the G14's resource budget (see Cluster Topology).
- The Supervisor accesses SearXNG via its local network API for all Tier 0 web research tasks.
- If SearXNG on the G14 is unavailable, the Spark activates a dormant local SearXNG container (see Section 9).

**Remote Access:**
- **Tailscale mesh VPN** is installed on the Spark at deployment. All client devices (PX13, Tab S9 Ultra, phone) also have Tailscale installed.
- The dashboard is accessible from anywhere via the Spark's Tailscale IP. Full functionality: chat, approvals, task monitoring, memory inspection, voice (if Whisper is available and latency permits).
- Discord remains the lightweight notification and approval channel for quick mobile interactions. The Tailscale dashboard is for full interactive sessions.
- The dashboard API must be stateless and token-authenticated. No session-based auth that only works on localhost. No hardcoded LAN assumptions in the API layer.
- For advanced remote access (VNC to the Spark desktop, SSH terminal), Tailscale provides the secure tunnel. No additional configuration needed.

**Multi-Session Support:**
- The data model must support multiple concurrent conversation threads.
- Each thread has a type (work or buddy) that determines memory partition routing.
- Each thread maintains its own Working Memory context while sharing Episodic (within its partition), Semantic, and Procedural memory.
- The dashboard must allow switching between threads without losing state.

**Development Workflow Integration (Three-Tool Workflow):**

The Spark's filesystem is the canonical repository for all project files, skills, MCP configurations, and codebases. Babs has direct access to these files because they are local to her. phloid uses three AI-powered coding tools, all operating on the same canonical files on the Spark's filesystem. Each tool draws from a different token pool, providing redundancy when any one pool is rate-limited.

- **Claude Code (architecture and planning).** CLI tool running in a terminal on the PX13 (or on the Spark via SSH). Authenticated with phloid's Anthropic Pro account ($20/month). Reads and edits files directly in the Project Babs repo. Used for architecture planning, document editing, strategic decisions, and any work where direct filesystem access and inline file editing are the primary workflow. Draws from the Anthropic Pro token pool (~44K tokens per 5-hour rolling window). This tool replaces browser-based Claude conversations for project work.
- **Antigravity (heavy implementation with cloud models).** Google's agent-first IDE (VS Code fork). Provides access to Gemini 3.1 Pro (via phloid's Google AI Pro subscription, $20/month), Claude Sonnet 4.6, Claude Opus 4.6, and GPT-OSS 120B. All Claude and Gemini tokens in Antigravity draw from Google's token pool, completely separate from the Anthropic Pro pool. Used for heavy coding sessions, multi-file scaffolding, agent-first workflows, and browser-based testing. Connects to the Spark's filesystem via Remote SSH over Tailscale.
- **VS Code + local model (daily driver implementation).** VS Code with Remote SSH to the Spark, plus a local-model coding extension (Continue or similar) pointed at the vLLM endpoint on the Spark. This is Babs-powered coding: zero token costs, no rate limits, no external dependency. Used for routine implementation, code review, and any work where cloud models are unnecessary. This becomes the primary coding tool once Babs is capable enough to handle the work.
- **Seamless location switching:** All three tools connect to the Spark via Tailscale IP. The connection works identically whether phloid is at home (traffic routes over LAN) or remote (traffic routes through Tailscale tunnel). No reconfiguration needed.
- **Token budget strategy:** Three separate token pools across two paid subscriptions plus local compute. When one cloud pool is rate-limited, switch to the other. Default to the local model for routine implementation. Use cloud models for complex architectural scaffolding, difficult debugging, or when a stronger model's judgment is needed.
- **Conventions document:** When Claude Code or Antigravity produces an architecture plan or task breakdown, the output should include a short conventions document covering: import patterns, error handling approach, logging format, docstring style, and type annotation expectations. This conventions doc is pasted into the system context of whichever tool handles implementation (local model, Antigravity, or Claude Code) so that all tools build to the same spec. Without this, a codebase built by three different models reads like it was written by three different people. The conventions doc supplements (does not replace) the Python Code Standards Procedural Memory entry; it covers project-specific patterns that the general standards do not.
- **Cross-tool adversarial review:** Because multiple AI tools operate on the same codebase, phloid can use them to review each other's work. Have Claude Code review what Antigravity wrote, or vice versa. Different models catch different things. This is a cheap way to get higher confidence without paying for it twice from the same provider.
- **Passive coding session capture:** A file watcher daemon on the Spark monitors designated project directories for changes. On file save events, it creates lightweight Episodic Memory entries (timestamp, file path, diff summary, project tag). This provides a passive record of coding activity without requiring phloid to interact with Babs. All three tools trigger this capture because they all write to the same filesystem.
- **Git integration:** For projects using git, Babs watches for new commits and ingests commit messages and diffs as structured Episodic Memory entries. Commits are a cleaner unit of "coding session" than individual file saves.
- **Explicit session capture:** phloid can open a Babs dashboard thread alongside his coding session. Discussions, decisions, and code reviews in this thread are captured as standard work Episodic Memory, linked to the relevant project.
- The file watcher and git hook integration are Tier 0 operations (reading local data, no approval needed).

---

## Section 12: Proactivity & Autonomous Behavior

**Event Listener Sub-Agent:**
- Design a lightweight daemon that monitors system and network states (disk usage, service health, calendar events, market hours, etc.).
- Pushes ambient notifications to the Supervisor via the Pub/Sub bus.
- Allows Babs to initiate conversations autonomously (e.g., "Hey, your disk is at 90%" or "Market opens in 10 minutes, want me to check your positions?").
- **UPS monitoring:** The Event Listener monitors UPS status via USB connection to the Spark. On power loss detection, it triggers a graceful shutdown sequence: flush pending writes, serialize in-flight task state, park scheduled jobs. On power restore, the Spark boots and runs the task recovery protocol (Section 2).
- **Cluster health monitoring:** The Event Listener monitors the G14 auxiliary node via the NATS heartbeat. It reports node online/offline events and triggers dormant fallback container activation/deactivation (Section 9).

**Asynchronous Reflection Loop:**

The Reflection Loop is a step scheduler, not a monolithic inference call. Each step has individual trigger conditions, compute costs, and output schemas. Each step writes output to durable storage before the next begins. Preemption between steps is clean: Supervisor steps yield immediately to any Class A/B/C request and resume at the next idle window.

**Hybrid model split:** The mechanical pass runs on a Worker (consolidation, linking, deprecation, dead-letter pattern analysis). The evaluative pass runs on the Supervisor at low reasoning effort (drift detection, heuristic identification, personality learning, agent quality grading, cached response pool maintenance).

**Dual trigger:** Time-based idle threshold AND content accumulation threshold must both be met. Tuned aggressive for fast learning. Suggested defaults: 2 minutes idle + 5 new episodic entries for the mechanical pass, 2 minutes idle + any pending evaluative work for the Supervisor pass.

**Step inventory:**

1. **Memory consolidation.** Merge, link, promote, and deprecate entries (Section 3, Memory Consolidation Pipeline).
2. **Dead-letter queue clustering and pattern analysis.** Cluster failures by error category (Section 9, Error Taxonomy) and identify recurring patterns.
3. **Heuristic extraction from correction patterns.** Identify candidate heuristics from phloid's corrections (Philosophy Document Section 5, Learning Mechanism).
4. **Heuristic validation against recent outcomes.** Check whether existing heuristics still hold against recent task results.
5. **Buddy-mode personality learning.** Process personal-partition Episodic Memory for personality-relevant signals (communication preferences, humor calibration, emotional patterns, interests). Weight toward relationship and communication learning, not task heuristics.
6. **Drift detection against immutable anchors.** Compare current response patterns against personality anchors (Philosophy Document Section 5, Drift Detection). Flag if mutable traits have drifted beyond configured thresholds. Drift detection parameters are stored in configuration and cannot be relaxed by the Reflection Loop itself.
7. **Agent probation quality assessment.** Only runs when agents are in probation. Evaluates probation task results against quality criteria (Section 8, Agent Probation Evaluation Layering).
8. **Cached response pool maintenance.** Generate new greeting and acknowledgment variants matching current personality calibration, retire stale ones, track engagement (Philosophy Document Section 3, Cached Response Pool).
9. **Morning Brief generation.** See Morning Brief specification below.
10. **Model scouting pipeline.** Babs monitors the OpenRouter model rankings and other model release channels for new models that could improve Worker performance or reduce cloud escalation costs. On a configurable schedule (default: weekly during idle), she pulls the current rankings, identifies candidates that match Worker capability profiles (coding, reasoning, structured output), and runs them against a local evaluation suite via API. The eval suite tests: Procedural Memory compliance (does the model follow instructions from the Python Code Standards entry?), structured output reliability (does it produce valid JSON/schemas on demand?), and task-specific quality on a curated set of representative tasks. Results are logged and, if a candidate outperforms the current Worker on the relevant metrics, Babs surfaces a recommendation on the dashboard with: model name, benchmark comparison, estimated memory footprint, and a "Download and Swap" action (Tier 2, requires phloid's approval). The test-before-download flow uses the Unified Model Registry (Section 1): a model starts as a `remote-only` entry, gets evaluated via API, and if approved, the weights are downloaded and a `local` entry replaces the remote one. Scouting can also be triggered conversationally (phloid mentions a model) or by event detection (a new model release notification).

**Immutable Core Anchors (Philosophy Document Section 5):** The Reflection Loop cannot modify core personality, autonomy boundaries, ethical constraints, safety interlocks, or the relationship model. These are enforced at the architecture level, not by self-restraint.

**Morning Brief:**

Pre-generated during idle time when phloid has been inactive for a configurable window (default 2+ hours).

Content rotates across: breaking news relevant to active projects or interests (sourced via SearXNG), coding concepts relevant to recent work, project status updates (pending tasks, completed background work, unresolved approvals), market snapshots (if financial tools configured), personal interest items (from buddy-mode context), cloud spend summary (tokens used per provider since last session, budget utilization percentages, any rate-limit events or budget warnings).

Length calibrated to cover the cold-start window, approximately 50-100 words, roughly 3-6 seconds of reading time. The Reflection Loop adjusts length based on observed reading speed.

Includes optional link to source material (news article URL, Procedural Memory entry, dashboard view).

Optionally interactive: soft prompt inviting discussion ("Worth discussing when you have a minute," "I noticed a pattern in your last three coding sessions"). If phloid ignores it, no follow-up. If phloid engages, the Supervisor pivots to the brief topic.

Engagement tracking: the Reflection Loop measures time-on-content, follow-up rate, and adjusts content mix toward what phloid engages with.

Ephemeral storage: the brief is a single key-value entry, not stored in the memory system. Shelf life of one session. Regenerated if older than a configurable freshness threshold.

Fallback: if no brief is prepared or the brief is stale, plain cached greeting with a "getting up to speed" signal.

**Startup Sequence:**

- **Step 1.** Message arrives. Classifier detects greeting component and request component. Original request registered in session state as pending.
- **Step 2.** Cached greeting fires instantly (sub-100ms). Pre-generated Morning Brief fires immediately after. No inference required for either.
- **Step 3.** In parallel, cold-start context retrieval runs (recent episodic context, pending tasks, system state from Event Listener). Supervisor processes the actual request with full context.
- **Step 4a (normal path).** phloid reads brief, does not engage. Supervisor streams the answer. Pending flag cleared.
- **Step 4b (pivot path).** phloid engages with the brief topic. Supervisor parks the original request (flagged as deferred in session state, preserved by extraction pass if context management runs). Engages with brief topic. When pivot resolves or a natural break occurs, Babs resurfaces the original question.
- **Step 4c (ignore path).** phloid sends a different follow-up, ignoring both brief and original question. Babs follows phloid's lead. Original request stays flagged. Raised at a natural pause if it appears phloid forgot.

**Pending request tracking:** The orchestration layer maintains a "pending original request" flag on the session object. If N turns pass without the original request being addressed, Babs raises it conversationally, not mechanically.

**Cold Start Bootstrap:**
- Define a bootstrap procedure for first boot when all memory tiers are empty.
- **Seed Procedural Memory:** Pre-load a set of architect-defined Procedural Memory entries covering core task types (coding best practices, document generation, research methodology, communication drafting). These give Workers functional instructions from day one. The following seed entries are required deliverables (see Output Requirements):
  - **"Python Code Standards"** is the baseline entry pulled by the Coding Worker before every Python task. It defines:
    - **Naming:** `snake_case` for functions and variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants. No abbreviations unless universally understood (`url`, `id`, `db`). Names must be descriptive enough to eliminate the need for a comment explaining what the function does. `get_active_worker_count()` needs no comment. `process_data()` is a naming failure.
    - **Function length:** No function longer than approximately 30 lines. If it is longer, it is doing too many things. Extract sub-functions with descriptive names so the parent reads like a table of contents.
    - **No magic numbers or strings.** Every literal value that controls behavior must be a named constant (e.g., `MAX_RETRY_ATTEMPTS = 5`) or pulled from configuration. No hardcoded `if retries > 5`.
    - **Error handling:** Never bare `except Exception`. Always catch specific expected exceptions and handle each one explicitly. A bare except is a bug hiding machine.
    - **No dead code.** No commented-out blocks, no unused imports, no uncalled functions. Version control exists for recovery. The codebase contains only what is actively used.
    - **Single return type.** If a function signature says it returns `WorkerStatus`, every code path returns a `WorkerStatus`. No functions that sometimes return `None`, sometimes a string, sometimes a dict.
    - **Type hints on all function signatures.** Every function declares its parameter types and return type. This makes the code self-documenting and enables mypy enforcement.
    - **Google-style docstrings on all public functions and classes.** Each docstring explains what the function does, why it exists, what its parameters are, what it returns, and what exceptions it raises. This is the primary documentation layer.
    - **Inline comments explain non-obvious "why", not obvious "what".** A comment that restates what the code does is noise. A comment that explains why a non-obvious approach was chosen is valuable.
    - **Separation of concerns.** Every function does one thing. Every class represents one idea. Every file owns one responsibility. Duplication is eliminated by extraction into shared functions, not by copy-paste-modify.
  - This entry is architect-defined at bootstrap but follows the standard Procedural Memory lifecycle. Babs can propose revisions through the Learning Mechanism as she observes phloid's corrections and preferences over time.
  - **"Babs Personality Rubric"** defines how Babs performs in conversation. It contains numbered rules (P-VOICE-01 through P-ANTI-06) with specific pass/fail examples, severity levels (Character Break, Personality Drift, Style Miss), and context mode definitions (Casual, Coding, Brainstorming, Crisis, Demo). The full rubric is indexed in the vector database for retrieval during drift detection (Section 12, Asynchronous Reflection Loop) and personality calibration. It is the primary reference the Supervisor uses to evaluate whether its own conversational output is in-character.
  - **"Babs Personality Cheatsheet"** is the compressed version of the rubric. It is injected directly into the Supervisor's system prompt at every conversation. It must be concise enough to fit within the system prompt budget without competing with task context, while capturing all critical behavioral rules. The cheatsheet is the enforcement layer. The full rubric is the calibration layer.
  - Both personality entries are governed by the Immutable Core Anchors constraint (Philosophy Document Section 5). The Reflection Loop can tune mutable traits (humor calibration, teaching depth, verbosity preferences) but cannot modify core personality rules (honesty, anti-sycophancy, opinion directness, energy matching). The personality rubric marks which rules are immutable and which are tunable.
- **Seed Semantic Memory:** Pre-load baseline user context (phloid's name, initial project descriptions, known tool integrations, stated preferences gathered during a brief onboarding interaction).
- **First-boot interaction mode:** On first launch, Babs should run a brief, structured onboarding conversation to gather baseline preferences (communication style, priority projects, notification preferences, working hours) rather than waiting weeks to learn them passively through the Learning Mechanism.
- The bootstrap data is stored in version-controlled config and can be re-applied after a full system reset.

---

## Section 13: Embodiment & Physical World Bridge (Phase 3 -- Future Expansion)

**Note:** This section is forward-looking. It should be architecturally accounted for (clean integration points) but is not required for initial deployment. Design for it, don't build it yet.

**ROS2 Bridge:**
- Explain how a local Vision Language Model (VLM) can be used for spatial reasoning.
- VLM output is passed to a ROS2 node for future physical drone piloting.
- **Critical Safety Constraint:** The LLM must never have direct, unfiltered hardware control. All physical actions must pass through a deterministic safety interlock layer that validates commands before execution.
- Specify the candidate VLM model and the ROS2 message interface.

---