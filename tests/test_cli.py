import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from capibara.cli import app

REPO_ROOT = Path(__file__).parent.parent
CATALOGS_DIR = REPO_ROOT / "catalogs"

runner = CliRunner()


def _invoke(*args: str):
    """Invoke a subcommand pinned to this repo's catalogs/ via --catalog,
    which must come after the subcommand name (it is a per-command Typer
    Option, not a top-level app option)."""
    return runner.invoke(app, [*args, "--catalog", str(CATALOGS_DIR)])


# --- validate ---------------------------------------------------------------


def test_validate_all_catalogs_passes():
    result = runner.invoke(app, ["validate", str(CATALOGS_DIR)])
    assert result.exit_code == 0
    assert "15/15 card(s) passed." in result.stdout


def test_validate_failure_is_nonzero_and_json_stays_parseable_with_warnings_on_stderr(tmp_path):
    bad = tmp_path / "unknown-token.yaml"
    bad.write_text(
        "id: unknown-token\n"
        "intent: A test card that uses a novel semantic type token for CLI testing.\n"
        "subject: thing\n"
        "inputs:\n  - name: x\n    type: string\n"
        "outputs:\n  - name: y\n    type: audio-waveform\n"
        "owner: test-team\ntags: [test]\nrisk:\n  level: low\n"
    )
    result = runner.invoke(app, ["validate", str(bad), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)  # must not raise: warnings go to stderr, not stdout
    assert len(payload) == 1
    assert payload[0]["ok"] is False
    assert any("bare 'string'" in e for e in payload[0]["errors"])


# --- list ---------------------------------------------------------------


def test_list_prints_all_capability_ids():
    result = _invoke("list")
    assert result.exit_code == 0
    for card_id in ("classify-risk", "detect-schema-drift", "review-pull-request"):
        assert card_id in result.stdout


def test_list_search_finds_review_pull_request():
    result = _invoke("list", "--search", "review")
    assert result.exit_code == 0
    assert "review-pull-request" in result.stdout
    assert "detect-schema-drift" not in result.stdout


def test_list_json_rows_include_domain_and_respect_domain_filter():
    result = _invoke("list", "--domain", "enterprise-ai", "--json")
    assert result.exit_code == 0
    rows = json.loads(result.stdout)
    assert rows
    assert all(r["domain"] == "enterprise-ai" for r in rows)


# --- inspect ---------------------------------------------------------------


def test_inspect_hit_prints_card_fields():
    result = _invoke("inspect", "classify-risk")
    assert result.exit_code == 0
    assert "id:      classify-risk" in result.stdout
    assert "behavior_profiles:" in result.stdout


def test_inspect_omits_empty_optional_sections():
    result = _invoke("inspect", "review-pull-request")
    assert result.exit_code == 0
    assert "behavior_profiles:" not in result.stdout


def test_inspect_json_is_the_raw_card_without_injected_domain():
    result = _invoke("inspect", "classify-risk", "--json")
    assert result.exit_code == 0
    card = json.loads(result.stdout)
    assert card["id"] == "classify-risk"
    assert "domain" not in card


def test_inspect_miss_exits_nonzero():
    result = _invoke("inspect", "does-not-exist")
    assert result.exit_code != 0


# --- compare ---------------------------------------------------------------


def test_compare_prints_scalar_and_list_diffs():
    result = _invoke("compare", "review-pull-request", "draft-pr-description")
    assert result.exit_code == 0
    assert "intent:" in result.stdout
    assert "~ linked_issue" in result.stdout


def test_compare_missing_id_exits_nonzero_and_names_it():
    result = _invoke("compare", "review-pull-request", "does-not-exist")
    assert result.exit_code != 0
    assert "does-not-exist" in result.stderr


# --- export ---------------------------------------------------------------


def test_export_mcp_prints_valid_json_for_whole_catalog():
    result = _invoke("export", "--format", "mcp")
    assert result.exit_code == 0
    tools = json.loads(result.stdout)
    assert len(tools) == 15


def test_export_mcp_single_card():
    result = _invoke("export", "review-pull-request", "--format", "mcp")
    assert result.exit_code == 0
    tools = json.loads(result.stdout)
    assert len(tools) == 1
    assert tools[0]["name"] == "review-pull-request"


def test_export_openapi_prints_valid_yaml():
    result = _invoke("export", "--format", "openapi")
    assert result.exit_code == 0
    spec = yaml.safe_load(result.stdout)
    assert spec["openapi"] == "3.1.0"


def test_export_md_contains_card_content():
    result = _invoke("export", "review-pull-request", "--format", "md")
    assert result.exit_code == 0
    assert "# review-pull-request" in result.stdout


def test_export_unknown_format_exits_nonzero():
    result = _invoke("export", "--format", "yaml")
    assert result.exit_code != 0


def test_export_unknown_card_id_exits_nonzero():
    result = _invoke("export", "does-not-exist", "--format", "mcp")
    assert result.exit_code != 0


def test_export_writes_to_output_path(tmp_path):
    out = tmp_path / "out.json"
    result = _invoke("export", "review-pull-request", "--format", "mcp", "-o", str(out))
    assert result.exit_code == 0
    assert result.stdout == ""
    tools = json.loads(out.read_text())
    assert tools[0]["name"] == "review-pull-request"


# --- catalog resolution failure surfaces cleanly, not as a raw traceback ---


def test_missing_catalog_exits_cleanly_not_with_a_traceback(tmp_path):
    result = runner.invoke(app, ["list", "--catalog", str(tmp_path / "nope")])
    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
