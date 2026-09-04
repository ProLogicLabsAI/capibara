"""Projections of CAPIBARA capability cards into MCP, OpenAPI, and Markdown.

These are projection stubs, not a shipped invocation runtime: one MCP tool
or one `POST /capabilities/{id}:invoke` OpenAPI path per card, derived only
from `inputs`/`outputs`. CAPIBARA does not know whether an implementation
mutates state, so no `readOnlyHint` or side-effect annotation is asserted.

The semantic-token -> JSON Schema map is the one place the "one definition,
many projections" invariant lives. An unknown token still exports as a
plain string (export never fails on a novel token) but the original token
is always preserved — as `x-capibara-type` on OpenAPI/MCP properties — so
no projection silently loses the semantic label.
"""

from __future__ import annotations

from capibara.validate import TOKEN_VOCABULARY

_JSON_TYPE_MAP = {
    "json-object": {"type": "object"},
    "boolean": {"type": "boolean"},
    "flag": {"type": "boolean"},
    "url": {"type": "string", "format": "uri"},
    "image": {"type": "string", "contentEncoding": "base64"},
}


def _json_schema_for_token(token: str) -> dict:
    """Map a CAPIBARA semantic type token to a JSON Schema fragment."""
    schema = dict(_JSON_TYPE_MAP.get(token, {"type": "string"}))
    if token not in TOKEN_VOCABULARY:
        schema["description"] = f"Unrecognized CAPIBARA type token '{token}' — exported as string."
    return schema


def _field_schema(fields: list[dict]) -> tuple[dict, list[str]]:
    """Build a JSON Schema `properties` map + `required` list from inputs/outputs."""
    properties = {}
    required = []
    for f in fields:
        prop = _json_schema_for_token(f["type"])
        if f.get("description"):
            prop.setdefault("description", f["description"])
        prop["x-capibara-type"] = f["type"]
        properties[f["name"]] = prop
        if f.get("required", True):
            required.append(f["name"])
    return properties, required


def to_mcp(cards: list[dict]) -> list[dict]:
    """Project cards into a flat list of MCP tool definitions."""
    tools = []
    for card in cards:
        input_properties, input_required = _field_schema(card["inputs"])
        output_properties, output_required = _field_schema(card["outputs"])
        tools.append(
            {
                "name": card["id"],
                "description": card["intent"],
                "inputSchema": {
                    "type": "object",
                    "properties": input_properties,
                    "required": input_required,
                },
                "outputSchema": {
                    "type": "object",
                    "properties": output_properties,
                    "required": output_required,
                },
            }
        )
    return tools


def to_openapi(cards: list[dict]) -> dict:
    """Project cards into an OpenAPI 3.1 stub: one invoke path per capability."""
    paths = {}
    for card in cards:
        input_properties, input_required = _field_schema(card["inputs"])
        output_properties, output_required = _field_schema(card["outputs"])
        risk = card.get("risk") or {}
        paths[f"/capabilities/{card['id']}:invoke"] = {
            "post": {
                "summary": card["intent"],
                "operationId": f"invoke_{card['id'].replace('-', '_')}",
                "tags": list(card.get("tags") or []),
                "x-capibara-owner": card.get("owner"),
                "x-capibara-risk": risk.get("level"),
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": input_properties,
                                "required": input_required,
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Capability output.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": output_properties,
                                    "required": output_required,
                                }
                            }
                        },
                    }
                },
            }
        }

    return {
        "openapi": "3.1.0",
        "info": {"title": "CAPIBARA Capabilities", "version": "0"},
        "paths": paths,
    }


def _markdown_for_card(card: dict) -> str:
    lines = [f"# {card['id']}", "", card["intent"], ""]
    lines.append(f"- **Subject:** {card['subject']}")
    lines.append(f"- **Owner:** {card['owner']}")
    risk = card.get("risk") or {}
    risk_line = f"- **Risk:** {risk.get('level', '-')}"
    if risk.get("notes"):
        risk_line += f" — {risk['notes']}"
    lines.append(risk_line)
    if card.get("tags"):
        lines.append(f"- **Tags:** {', '.join(card['tags'])}")
    lines.append("")

    lines.append("## Inputs")
    lines.append("")
    lines.append("| Name | Type | Required | Description |")
    lines.append("|------|------|----------|-------------|")
    for i in card.get("inputs") or []:
        lines.append(
            f"| `{i['name']}` | `{i['type']}` | {i.get('required', True)} | {i.get('description', '')} |"
        )
    lines.append("")

    lines.append("## Outputs")
    lines.append("")
    lines.append("| Name | Type | Description |")
    lines.append("|------|------|-------------|")
    for o in card.get("outputs") or []:
        lines.append(f"| `{o['name']}` | `{o['type']}` | {o.get('description', '')} |")
    lines.append("")

    if card.get("semantic_refs"):
        lines.append("## Semantic refs")
        lines.append("")
        for ref in card["semantic_refs"]:
            lines.append(f"- {ref}")
        lines.append("")

    if card.get("behavior_profiles"):
        lines.append("## Behavior profiles")
        lines.append("")
        for profile in card["behavior_profiles"]:
            lines.append(f"- **{profile['id']}** — {profile['description']}")
        lines.append("")

    return "\n".join(lines)


def to_markdown(cards: list[dict], *, domains: dict[str, str] | None = None) -> str:
    """Project cards into a Markdown document, one section per card.

    If `domains` (card id -> domain name) is given and more than one domain
    is present, cards are grouped under a heading per domain.
    """
    if not domains or len({domains[c["id"]] for c in cards if c["id"] in domains}) <= 1:
        return "\n---\n\n".join(_markdown_for_card(card) for card in cards)

    grouped: dict[str, list[dict]] = {}
    for card in cards:
        grouped.setdefault(domains.get(card["id"], "uncategorized"), []).append(card)

    sections = []
    for domain in sorted(grouped):
        body = "\n---\n\n".join(_markdown_for_card(card) for card in grouped[domain])
        sections.append(f"## Domain: {domain}\n\n{body}")
    return "\n\n---\n\n".join(sections)
