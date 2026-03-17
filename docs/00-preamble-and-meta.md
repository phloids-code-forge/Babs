# Master Architecture Request: Project Babs -- v5

**Prompt Version:** 5.9
**Last Updated:** 2026-03-12
**Status:** Phase 8 complete (2026-03-15). Phase 9 (NemoClaw/OpenClaw integration) in progress as of 2026-03-17. Full Babs stack operational: Dashboard -> NATS -> Supervisor -> Procedural Memory + Tools -> vLLM (Nano, 65+ tok/s). OpenShell gateway running, vllm-local provider verified against our Docker vLLM container. Babs supervisor/memory integration with OpenClaw agent loop is the next step. Nemotron 3 Super NVFP4 parked at 14-16 tok/s single-node (community Marlin patches); not yet interactive-fast. Awaiting avarok v24 or further community patches.

---

## Preamble

Role: You are an elite AI Systems Architect. Your task is to design a comprehensive, production-ready infrastructure plan for a localized, highly autonomous multi-agent AI named "Babs."

You must treat every section of this document as a hard constraint. Where numerical limits, memory budgets, or timeout thresholds are specified, your plan must prove compliance with math, not prose. Handwaving is not acceptable.

**Companion Document:** This prompt is governed by the **Project Babs Design Philosophy Document v1.5**, which defines identity, autonomy boundaries, intelligence routing (including cloud escalation principle and cost-aware routing), memory philosophy (including work/personal memory partitioning and buddy mode), learning constraints, dynamic agent creation rules, audit requirements, and design principles. That document is attached alongside this prompt. Where the philosophy document defines a constraint (e.g., Trust Tiers, Immutable Anchors, Code Before Memory, Cloud Escalation Principle), the architecture must implement it. Conflicts between this prompt and the philosophy document should be flagged explicitly rather than silently resolved.

**Implementation Model:** This architecture will be built iteratively by phloid and Babs together, not delivered as a monolithic plan and executed by a separate team. The architecture documents serve as the engineering specification and shared reference during incremental build-out. Babs will be bootstrapped to a minimal viable state first (see Section 16, Bootstrap Deployment Plan), then used to build out her own remaining infrastructure with phloid reviewing every change. The phased delivery protocol below defines how the architect should structure the initial plan; actual implementation will proceed incrementally as phloid and Babs work through it.

---

## Execution Protocol

**This plan must not be delivered as a single monolithic output.**

The architecture is too large and too detailed to maintain quality across a single response. Deliver the plan across sequential phases. Follow these rules:

1. **Phase Definition First.** Your first response must define the phase boundaries, what each phase covers, estimated scope, and dependencies between phases. phloid will review and approve the phase plan before work begins.
2. **One Phase Per Response.** Each subsequent response delivers one complete phase. Do not begin the next phase until phloid greenlights the current one.
3. **Each Phase Stands Alone.** No phase may reference "see above" or "as described earlier" without restating the relevant constraint. If Phase 4 depends on a memory budget defined in Phase 1, Phase 4 restates the number. This protects against context degradation across a long conversation.
4. **Dedicated Artifact Phases.** The Memory Ledger and Graceful Degradation Matrix each get their own dedicated phase or are the primary deliverable of a phase. They must not be crammed into the tail end of another section.
5. **Validation Gates.** Each phase ends with a checklist of assumptions, open questions, and explicit dependencies on prior phases. phloid reviews these before proceeding.

---


## Output Requirements

Your response must include all of the following across the phased delivery:

1. **Master Architecture Diagram:** A visual or structured representation of every component, their relationships, and communication flows. Must include both nodes (Spark and G14) and the network interconnect.
2. **Cluster Topology Diagram:** A dedicated diagram showing the two-node architecture, service assignments per node, pub/sub bus spanning the LAN, Tailscale overlay, and client device access paths.
3. **Memory Ledger:** A table showing every running component's estimated memory footprint at peak load, summing to no more than 115GB on the Spark. This must be a dedicated deliverable phase. Include KV cache math at 32K, 64K, 128K, and 262K context lengths for the Supervisor. Include a separate resource budget table for the G14 auxiliary node. The ledger must include two columns: **bootstrap** (Supervisor + essential services only) and **full deployment** (all components at steady state). The ledger must also show **dynamic swap headroom**: the memory available when Workers are unloaded, which is the pool available for ComfyUI diffusion pipelines or other transient workloads.
4. **Storage Allocation Strategy:** A table showing estimated disk usage per component (model weights, vector databases, audit logs, Episodic Memory, backups) with 12-month growth projections against the 4TB internal + 2TB external (Spark) and 1TB (G14) budgets.
5. **Graceful Degradation Matrix:** A table mapping each component failure (including external dependencies: Discord, Alpaca, Gmail, Anthropic API, G14 node offline, G14 GPU contention, Tailscale unavailable, all backup targets lost) to the system's behavior. This must be a dedicated deliverable phase.
6. **Trust Tier Action Map:** A table mapping every external action to its assigned Trust Tier, rate limits, and approval flow.
7. **Step-by-Step Deployment Phases:** Ordered phases to bring the system online incrementally, with validation gates between each phase. The EdgeXpert bootstrap sequence (Section 16) is the primary deployment plan. G14 prework (Section 15) runs in parallel.
8. **Exact Directory Structure:** The filesystem layout on the DGX OS (Spark) and Ubuntu (G14).
9. **Docker Compose Layout:** The base `docker-compose.yml` for initial static services on the Spark, the docker-compose configuration for G14 services, plus the runtime container orchestration layer for dynamic agent creation on the Spark.
10. **Configuration File Templates:** Templates for all version-controlled config files referenced in the plan (model assignments, memory budgets, timeouts, Trust Tiers, rate limits, scheduled tasks, drift thresholds, Discord config, bootstrap seed data, cluster topology, G14 service assignments, backup schedules, Tailscale config).
11. **Capability Registry Schema:** The data structure for the agent capability registry.
12. **Procedural Memory Schema:** The data structure for Procedural Memory entries, compatible with the specification in Philosophy Document Section 4. Structured metadata fields with free-form semantic prose for instruction content.
13. **Audit Log Schema:** The data structure for the immutable audit log.
14. **Thread Metadata Schema:** The data structure for conversation threads, including thread type (work/buddy), partition assignment, and project tags.
15. **Seed Procedural Memory Entries:** The bootstrap data set must include complete, ready-to-deploy Procedural Memory entries for core task types. At minimum, the **Python Code Standards** entry specified in Section 12 must be delivered as a full Procedural Memory document, not a placeholder. Additional seed entries for document generation, research methodology, and communication drafting should be scoped and delivered as part of the bootstrap phase.

---

## Style & Communication Constraints

- No em dashes. Ever.
- No corporate speak, buzzword padding, or filler prose.
- If you are uncertain about a specification, state the assumption explicitly and flag it for review rather than guessing silently.
- Precision over verbosity. Say it once, say it right.
