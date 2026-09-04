# Contributing to Open CAPIBARA

Open CAPIBARA is a read-only capability registry for **v0.0.1-alpha**: YAML grammar, sample catalogs,
and a CLI for validating, listing, inspecting, comparing, and exporting capability cards.
No execution endpoint. No agent runtime. No hosted service.

---

## What you can contribute in V0

- **New capability cards** — add a YAML file under `catalogs/<domain>/`
- **Schema clarifications** — improve comments or examples in `schema/capability.v0.yaml`
- **Bug fixes** — typos, broken field names, invariant violations

Runtime, workflow engines, and execution integrations are out of scope for V0.

---

## How to add a capability card

1. Choose or create a domain folder under `catalogs/`:
   - `software-engineering/`, `data-engineering/`, `enterprise-ai/`, or a new domain

2. Create a file named `<kebab-case-id>.yaml`.

3. Follow `schema/capability.v0.yaml` (JSON Schema draft-07). All required fields:

   ```yaml
   id: <kebab-case>        # stable; matches filename stem
   intent: "..."           # one sentence, plain language, no model names
   subject: <noun-phrase>  # primary entity the capability operates on
   inputs:
     - name: <snake_case>
       type: <semantic-token>  # see token vocabulary below
   outputs:
     - name: <snake_case>
       type: <semantic-token>
   owner: <team-or-domain>
   tags: [tag1, tag2]
   risk:
     level: low          # low | medium | high
     notes: "..."        # optional
   ```

4. **Semantic type tokens** for `inputs[].type` and `outputs[].type` — use these, not bare programming types:

   | Token | Use for |
   |-------|---------|
   | `text` | Unstructured prose |
   | `text/diff` | Code or text diff |
   | `text/code` | Source code block |
   | `text/markdown` | Markdown document |
   | `text/yaml` | YAML document |
   | `text/pdf` | PDF content |
   | `json-object` | Structured JSON/dict |
   | `identifier` | A name, slug, or key (not a bare string) |
   | `enum-label` | One value from a fixed set |
   | `boolean` | True/false flag |
   | `flag` | Boolean-shaped switch (synonym of `boolean` for flag-like fields) |
   | `image` | Image file or bytes |
   | `url` | A URL |

   Avoid bare `string` or `object` — these are JSON Schema primitives, not semantic types. `capibara
   validate` rejects bare `string`/`object` as an error; a token outside this table is a warning, not
   an error, so a deliberate new domain token is never blocked outright.

5. **Gate invariants** — your card must pass all of these before merging:
   - All required fields present
   - `id` matches the filename stem
   - `id` is unique across the catalog
   - No embedded prompt text in any field
   - No model names (`gpt-4`, `claude`, etc.) anywhere
   - `behavior_profiles` used only when the card genuinely has distinct behavioral modes
   - `type` values use the semantic token vocabulary, not bare `string`/`object`
   - `semantic_refs` does not point solely to one commercial vendor's product, docs, or API as
     the card's only reference — use vendor-neutral standards, specs, or policy docs instead.
     A capability describes a possibility, not a product; cards that read as promotion for a
     specific paid tool will be rejected regardless of schema validity.

6. Validate against the schema plus the gate invariants above:

   ```bash
   make dev   # once, to create .venv
   .venv/bin/capibara validate catalogs/<domain>/<your-file>.yaml
   ```

   `capibara validate` with no path defaults to every card under `catalogs/`. See `make test` /
   `make lint` in the [Makefile](Makefile) for the full dev loop.

---

## PR conventions

- One capability card per PR when possible
- Conventional commits: `feat(catalogs): add <id> capability`, `fix(schema): ...`
- Link to an issue if one exists; otherwise a short description in the PR body is fine
- All contributions are licensed under [Apache-2.0](LICENSE)
- PRs that are part of an automated bulk campaign (same card/wording pattern opened across many
  unrelated repos to promote one vendor) are closed without merge, regardless of schema validity

---

## Questions

Open a GitHub Issue. Keep it focused on the grammar, a specific card, or a schema question.
