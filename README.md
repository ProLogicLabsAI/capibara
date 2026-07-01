# Open CAPIBARA

> **CAPIBARA is an open semantic language and registry for describing capabilities: what can happen, why it happens, under what conditions, with what effects, and how systems evolve from those capabilities.**

*CAPIBARA models potential before structure.*

---

## What it is

**Open CAPIBARA** is a capability registry — a read-only grammar, catalog, and explorer for V0.

With it you can:

- **Describe** capabilities in YAML (one card per bounded action)
- **Browse** them (discover / inspect / compare)
- **Export** to MCP tool definitions, OpenAPI snippets, or Markdown

**Not** an agent framework. **Not** a workflow engine. **Not** a gateway.

The unit is the capability: **a named possibility that something can happen** — before identity, before systems, before anything runs. The capability persists when models change, frameworks churn, and teams reorganize.

---

## The problem it solves

Teams scatter prompts, MCP configs, and agent definitions across wikis, repos, and ad hoc JSON. Nothing answers: *what can this organization actually do with its AI systems, who owns each capability, and how do we project it to MCP or OpenAPI without maintaining three separate copies?*

CAPIBARA answers that question through description, not execution.

```
REST   → exposes functions
MCP    → exposes tools
CAPIBARA → describes capabilities (the governed layer above both)
```

One YAML definition. Multiple projections (MCP, OpenAPI, documentation). V0 implements the description half; projection and runtime follow.

---

## Lineage

CAPIBARA is Generation 3 of a real discipline, not invented vocabulary:

| Generation | Question |
|------------|----------|
| Data Catalog (Gen 1) | What data exists? |
| Meta Grid / metadata coordination (Gen 2) | What metadata exists? |
| **Capability Grid / CAPIBARA (Gen 3)** | **What can the organization do?** |

The pattern is borrowed from analytics: metric definitions belong in a governed semantic layer that BI tools project from, not re-defined per dashboard. CAPIBARA applies the same principle one level up — capability definitions belong in a governed layer that agents and applications project from.

---

## Quick start

```
capibara/
  schema/capability.v0.yaml    # JSON Schema — the grammar
  catalogs/
    software-engineering/      # 5 example cards
    data-engineering/          # 5 example cards
    enterprise-ai/             # 5 example cards
```

Browse `catalogs/` to see the grammar in use. Read `schema/capability.v0.yaml` to understand the card shape.

CLI (`capibara list`, `capibara inspect <id>`, `capibara export --format mcp`) is the next slice — not yet shipped in V0.

---

## V0 scope

- YAML schema + sample catalogs — Apache-2.0
- Read-only: describe, browse, export (export = next gene)
- No execution endpoint, no agent runtime, no hosted service

*Runtime, orchestration, and genes are out of scope for v0.*

---

## Design notes

The grammar is grounded in a longer design rationale (capability as potential, the
semantic loop, the vocabulary of type tokens, and a phased roadmap). Those notes will
be published alongside this repo as the project matures.
