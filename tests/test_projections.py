import json
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

from capibara.catalog import load_catalog
from capibara.projections import to_markdown, to_mcp, to_openapi

REPO_ROOT = Path(__file__).parent.parent
CATALOGS_DIR = REPO_ROOT / "catalogs"


def _cards() -> list[dict]:
    return load_catalog(CATALOGS_DIR)


def test_to_mcp_round_trips_through_json_and_has_valid_input_schema():
    cards = _cards()
    text = json.dumps(to_mcp(cards))
    tools = json.loads(text)
    assert len(tools) == len(cards)
    for tool, card in zip(tools, cards):
        assert tool["name"] == card["id"]
        assert tool["description"] == card["intent"]
        Draft7Validator.check_schema(tool["inputSchema"])
        Draft7Validator.check_schema(tool["outputSchema"])
        input_names = {i["name"] for i in card["inputs"]}
        assert set(tool["inputSchema"]["properties"]) == input_names
        required_names = {i["name"] for i in card["inputs"] if i.get("required", True)}
        assert set(tool["inputSchema"]["required"]) == required_names
        output_names = {o["name"] for o in card["outputs"]}
        assert set(tool["outputSchema"]["properties"]) == output_names


def test_to_mcp_preserves_original_token_even_when_json_type_is_generic():
    cards = _cards()
    tools = to_mcp(cards)
    pr_tool = next(t for t in tools if t["name"] == "review-pull-request")
    assert pr_tool["inputSchema"]["properties"]["pr_diff"]["x-capibara-type"] == "text/diff"


def test_to_openapi_output_is_yaml_not_json():
    """The CLI must emit OpenAPI as YAML (paste-into-spec), not JSON."""
    cards = _cards()
    text = yaml.safe_dump(to_openapi(cards), sort_keys=False)
    spec = yaml.safe_load(text)
    assert spec["openapi"] == "3.1.0"
    assert len(spec["paths"]) == len(cards)


def test_to_openapi_has_one_invoke_path_per_card_with_owner_and_risk_extensions():
    cards = _cards()
    spec = to_openapi(cards)
    for card in cards:
        path = f"/capabilities/{card['id']}:invoke"
        assert path in spec["paths"]
        operation = spec["paths"][path]["post"]
        assert operation["x-capibara-owner"] == card["owner"]
        assert operation["x-capibara-risk"] == card["risk"]["level"]
        assert set(operation["tags"]) == set(card.get("tags") or [])

        request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
        assert request_schema["type"] == "object"
        response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
        output_names = {o["name"] for o in card["outputs"]}
        assert set(response_schema["properties"]) == output_names


def test_to_markdown_single_card_contains_id_intent_and_every_input_name():
    card = next(c for c in _cards() if c["id"] == "review-pull-request")
    text = to_markdown([card])
    assert "# review-pull-request" in text
    assert card["intent"] in text
    for i in card["inputs"]:
        assert f"`{i['name']}`" in text
    for o in card["outputs"]:
        assert f"`{o['name']}`" in text


def test_to_markdown_groups_multi_domain_catalog_by_domain():
    cards = _cards()
    domains = {
        "review-pull-request": "software-engineering",
        "classify-risk": "enterprise-ai",
    }
    subset = [c for c in cards if c["id"] in domains]
    text = to_markdown(subset, domains=domains)
    assert "## Domain: software-engineering" in text
    assert "## Domain: enterprise-ai" in text


def test_to_markdown_single_domain_does_not_add_domain_headings():
    cards = _cards()
    domains = {c["id"]: "software-engineering" for c in cards}
    subset = [c for c in cards if c["id"] == "review-pull-request"]
    text = to_markdown(subset, domains=domains)
    assert "## Domain:" not in text
