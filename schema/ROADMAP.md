# Schema Roadmap — Phase 0+ field extensions

`capability.v0.yaml` captures the minimum viable subset of the CAPIBARA vocabulary.
The table below maps additional terms from the foundational guide §6 to their planned
schema locations. All extensions are **additive** — V0-valid files remain valid.

## Vocabulary coverage

| Foundational guide term | V0 card coverage | Phase 0+ field |
|-------------------------|-----------------|----------------|
| Capability | `id` + bounded `intent` | — |
| Intent | `intent` | — |
| Input | `inputs[]` | — |
| Output | `outputs[]` | — |
| Context | partial: `subject` | `context` object (domain, environment, trust level) |
| Constraint | partial: `risk`, `semantic_refs` | `constraints[]` (who, what, law, ethics) |
| Evidence | partial: `semantic_refs` | `evidence` object (audit trail, validation method) |
| Effect | — | `effect` object (what changes in the world) |
| Relationship | catalog-level graph | `relationships[]` or separate edge files |

## Planned Phase 0 additions (non-breaking)

```yaml
# Phase 0 — add to required or optional fields without changing V0 required set

context:
  # The situation in which the capability exists
  domain: string          # e.g. "healthcare/dermatology"
  environment: string     # e.g. "clinic", "emergency", "remote"
  trust_level: string     # e.g. "low", "standard", "high"

constraints:
  # What limits or shapes the capability
  - type: string          # e.g. "legal", "ethical", "equipment", "data-access"
    description: string

effect:
  # What changes in the world after the capability runs (observable outcome)
  description: string
  affected_entities: [string]

relationships:
  # How this capability connects to others
  - type: string          # depends-on | triggers | supports | blocks | improves | replaces
    target_id: string     # id of the related capability
    description: string
```

## What does not belong in the card (Phase 0 or later)

- Numeric risk thresholds → `semantic_refs` to policy documents
- Inline prompt text → implementation detail; not part of the capability contract
- Model names → replaceable; governance belongs in policy
- Workflow orchestration → multi-step sequencing is an engine concern, not a card field
