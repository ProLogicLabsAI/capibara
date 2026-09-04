from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

from capibara.validate import (
    load_cards,
    load_schema,
    validate_card,
    validate_card_gates,
    validate_path,
)

REPO_ROOT = Path(__file__).parent.parent
CATALOGS_DIR = REPO_ROOT / "catalogs"
FIXTURES_DIR = Path(__file__).parent / "fixtures"

EXPECTED_CARD_COUNT = 15


def test_schema_loads_and_is_valid_draft7():
    schema = load_schema()
    assert schema["title"] == "CAPIBARA Capability Card v0"
    Draft7Validator.check_schema(schema)


@pytest.mark.parametrize(
    "example_file",
    sorted(CATALOGS_DIR.rglob("*.yaml")),
    ids=lambda p: str(p.relative_to(CATALOGS_DIR)),
)
def test_every_catalog_card_passes_validation(example_file):
    schema = load_schema()
    [(_source, card, _is_single)] = load_cards(example_file)
    errors = validate_card(card, schema)
    assert errors == [], f"{example_file.name} should be valid, got: {errors}"


def test_catalogs_directory_all_pass_and_count_is_fifteen():
    """Guards the exact card count so a new card added without a test update
    still gets validated by this suite (and the count assertion nudges the
    fixture list here to stay in sync)."""
    results = validate_path(CATALOGS_DIR)
    assert len(results) == EXPECTED_CARD_COUNT
    assert all(r.ok for r in results), [(r.source, r.errors) for r in results if not r.ok]


def test_recursive_discovery_from_catalogs_root(tmp_path):
    """The lab's loader used a non-recursive glob, which finds nothing under
    the public repo's catalogs/<domain>/*.yaml layout. Directory loading must
    be recursive."""
    (tmp_path / "catalogs" / "a-domain").mkdir(parents=True)
    card_path = tmp_path / "catalogs" / "a-domain" / "do-a-thing.yaml"
    card_path.write_text(
        "id: do-a-thing\n"
        "intent: Do a thing for the purposes of this recursive-discovery test.\n"
        "subject: thing\n"
        "inputs:\n  - name: x\n    type: text\n"
        "outputs:\n  - name: y\n    type: text\n"
        "owner: test-team\ntags: [test]\nrisk:\n  level: low\n"
    )
    triples = load_cards(tmp_path / "catalogs")
    assert len(triples) == 1
    assert triples[0][0] == card_path
    assert triples[0][1]["id"] == "do-a-thing"


def test_validate_directory_does_not_treat_schema_file_as_a_card(tmp_path):
    """A directory that contains both catalogs/ and schema/ (the repo's own
    shape) must never validate schema/capability.v0.yaml as if it were a card."""
    (tmp_path / "catalogs" / "a-domain").mkdir(parents=True)
    (tmp_path / "catalogs" / "a-domain" / "do-a-thing.yaml").write_text(
        "id: do-a-thing\n"
        "intent: Do a thing for the purposes of this schema-skip test.\n"
        "subject: thing\n"
        "inputs:\n  - name: x\n    type: text\n"
        "outputs:\n  - name: y\n    type: text\n"
        "owner: test-team\ntags: [test]\nrisk:\n  level: low\n"
    )
    (tmp_path / "schema").mkdir()
    (tmp_path / "schema" / "capability.v0.yaml").write_text(
        yaml.safe_dump(load_schema()), encoding="utf-8"
    )
    triples = load_cards(tmp_path)
    sources = {source for source, _card, _is_single in triples}
    assert (tmp_path / "schema" / "capability.v0.yaml") not in sources
    assert len(triples) == 1
    assert triples[0][1]["id"] == "do-a-thing"


def test_embedded_risk_threshold_fails_with_clear_error():
    fixture = FIXTURES_DIR / "invalid-embedded-threshold.yaml"
    results = validate_path(fixture)
    assert len(results) == 1
    result = results[0]
    assert not result.ok
    assert any("threshold" in err and "risk" in err for err in result.errors)


def test_load_cards_rejects_non_card_non_catalog(tmp_path):
    bad_file = tmp_path / "not-a-card.yaml"
    bad_file.write_text("just a string\n")
    with pytest.raises(ValueError):
        load_cards(bad_file)


def _minimal_card(**overrides) -> dict:
    card = {
        "id": "do-a-thing",
        "intent": "Do a thing for the purposes of a gate-check unit test.",
        "subject": "thing",
        "inputs": [{"name": "x", "type": "text"}],
        "outputs": [{"name": "y", "type": "json-object"}],
        "owner": "test-team",
        "tags": ["test"],
        "risk": {"level": "low"},
    }
    card.update(overrides)
    return card


def test_gate_id_filename_mismatch(tmp_path):
    source = tmp_path / "mismatched-name.yaml"
    errors, _warnings = validate_card_gates(
        _minimal_card(id="totally-different-id"), source, is_single_card_file=True
    )
    assert any("does not match filename stem" in e for e in errors)


def test_gate_id_filename_mismatch_skipped_for_catalog_list_files(tmp_path):
    """A YAML list catalog file has no single filename-stem to match against."""
    source = tmp_path / "many-cards.yaml"
    errors, _warnings = validate_card_gates(
        _minimal_card(id="totally-different-id"), source, is_single_card_file=False
    )
    assert not any("does not match filename stem" in e for e in errors)


def test_gate_duplicate_id_across_two_files(tmp_path):
    (tmp_path / "domain-a").mkdir()
    (tmp_path / "domain-b").mkdir()
    a = tmp_path / "domain-a" / "dup-card.yaml"
    b = tmp_path / "domain-b" / "dup-card.yaml"
    a.write_text(yaml.safe_dump(_minimal_card(id="dup-card")))
    b.write_text(yaml.safe_dump(_minimal_card(id="dup-card")))
    results = validate_path(tmp_path)
    by_source = {r.source: r for r in results}
    assert by_source[a].ok
    assert not by_source[b].ok
    assert any("duplicate id" in e and str(a) in e for e in by_source[b].errors)


@pytest.mark.parametrize("bare_type", ["string", "object"])
def test_gate_bare_type_is_rejected(bare_type):
    errors, _warnings = validate_card_gates(
        _minimal_card(inputs=[{"name": "x", "type": bare_type}]),
        Path("do-a-thing.yaml"),
        is_single_card_file=True,
    )
    assert any(f"bare '{bare_type}'" in e for e in errors)


def test_gate_model_name_is_rejected():
    errors, _warnings = validate_card_gates(
        _minimal_card(intent="Uses GPT-4 to do a thing."),
        Path("do-a-thing.yaml"),
        is_single_card_file=True,
    )
    assert any("model-name marker" in e for e in errors)


def test_gate_unknown_token_is_a_warning_not_an_error():
    errors, warnings = validate_card_gates(
        _minimal_card(inputs=[{"name": "x", "type": "audio-waveform"}]),
        Path("do-a-thing.yaml"),
        is_single_card_file=True,
    )
    assert errors == []
    assert any("not in the documented token vocabulary" in w for w in warnings)
