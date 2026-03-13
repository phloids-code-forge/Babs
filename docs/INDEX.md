# Architecture Prompt: File Index

**Prompt Version:** 5.9
**Last Updated:** 2026-03-12
**Status:** Phase 1 in progress. vLLM 0.17.1rc1 serving Nemotron 3 Super NVFP4 at 14.8 tok/s but crashing on extended generation (SM121 illegal instruction). --enforce-eager untested, Nano fallback available. Directory structure and git repo initialized. Open WebUI pulled. G14 auxiliary node OS and networking complete, service deployment pending.

---

## Assembly Order

When delivering the final prompt (concatenated for execution), assemble in this order:

1. `00-preamble-and-meta.md` (title, preamble, execution protocol, output requirements, style constraints)
2. `01-hardware-and-infrastructure.md` (hardware environment, runtime resilience, observability, backup/CI/CD, pre-deployment prep [G14], bootstrap deployment plan [EdgeXpert])
3. `02-core-architecture.md` (supervisor-worker hierarchy, orchestration, tiered memory, ephemeral isolation)
4. `03-behavior-and-agency.md` (code quality pipeline, external agency, audit log, dynamic agent creation)
5. `04-interface-and-proactivity.md` (UI/interaction layer, three-tool development workflow, proactivity/reflection loop, embodiment)
6. `05-open-questions.md` (unresolved items, now Section 17)

**Note:** The original document interleaves these sections differently (hardware, then sections 1-16, then output/style). The grouping here is by concern for editing. Assembly restores the original section numbering order.

## Companion Document

`babs-design-philosophy-v1_5.md` (single file, not split)

The philosophy document is the higher authority. If any architecture file contradicts it, the philosophy document wins.

## Dependency Map

| File | References concepts from |
|------|-----------------------------|
| 00 (Preamble/Meta) | Philosophy doc (companion document reference) |
| 01 (Hardware/Infra) | 02 (memory ledger entries), 03 (audit log backup), 04 (dashboard metrics) |
| 02 (Core Architecture) | 01 (hardware constraints, 115GB ceiling), Philosophy doc (interaction classes, memory philosophy, Code Before Memory) |
| 03 (Behavior/Agency) | 02 (memory tiers, orchestration), 01 (memory ledger), Philosophy doc (trust tiers, learning mechanism, safety model) |
| 04 (Interface/Proactivity) | 01 (G14 services, cluster topology), 02 (memory partitioning, context management), 03 (approval gates, audit log), Philosophy doc (personality, buddy mode, immutable anchors) |
| 05 (Open Questions) | All files (questions reference components across the full architecture) |

## Memory Ledger

The Memory Ledger table lives in `01-hardware-and-infrastructure.md` alongside the hardware constraints it must satisfy. All other files that add components must note their Memory Ledger impact and cross-reference file 01. The ledger must include bootstrap, full deployment, and dynamic swap headroom columns (see Output Requirements in 00).

## Version Control

Each file carries its own changelog at the bottom. The version number in `00-preamble-and-meta.md` is the master version for the full prompt. Bump it when any file changes.

## Hard Constraint Reminder

115GB memory ceiling on the Spark. No em dashes. Philosophy doc wins conflicts.
