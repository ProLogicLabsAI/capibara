"""capibara CLI — read-only capability card validation, discovery, and export.

No execution endpoint, no agent runtime, no hosted service. `capibara run`
does not exist and never will in V0 — describe and browse only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
import yaml

from capibara.catalog import (
    domain_for,
    get_card,
    get_card_with_source,
    load_catalog_with_sources,
    resolve_catalog_path,
)
from capibara.compare import compare_cards, comparison_to_dict
from capibara.projections import to_markdown, to_mcp, to_openapi
from capibara.validate import ValidationResult, load_schema, resolve_schema_path, validate_path

app = typer.Typer(
    help=(
        "Open CAPIBARA — a read-only capability registry: describe capabilities in YAML, "
        "validate, browse, compare, and export them. No execution endpoint, no agent runtime."
    ),
    no_args_is_help=True,
)

_EXPORT_FORMATS = ("mcp", "openapi", "md")

CatalogOption = Annotated[
    Path | None,
    typer.Option(
        "--catalog", help="Catalog file or directory. Defaults to the resolved catalogs/ root."
    ),
]
JsonOption = Annotated[bool, typer.Option("--json", help="Machine-readable JSON output.")]


@app.command()
def validate(
    paths: Annotated[
        list[Path] | None,
        typer.Argument(
            help="Card file(s), catalog file(s), or directory(ies). Defaults to catalogs/."
        ),
    ] = None,
    as_json: JsonOption = False,
) -> None:
    """Validate capability card(s) against schema/capability.v0.yaml plus the
    CONTRIBUTING.md gate invariants (id/filename, unique ids, no bare
    string/object types, no model names)."""
    try:
        targets = paths if paths else [resolve_catalog_path()]
        # Anchor schema resolution to the first target, not to CWD: an
        # explicit path may point somewhere far from the current directory.
        schema = load_schema(resolve_schema_path(targets[0]))
        results: list[ValidationResult] = []
        for target in targets:
            results.extend(validate_path(target, schema=schema))
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    failed = sum(1 for r in results if not r.ok)

    if as_json:
        payload = [
            {
                "source": str(r.source),
                "id": r.card_id,
                "ok": r.ok,
                "errors": r.errors,
                "warnings": r.warnings,
            }
            for r in results
        ]
        typer.echo(json.dumps(payload, indent=2))
        for r in results:
            for w in r.warnings:
                typer.echo(f"WARN  {r.source}  ({r.card_id or r.source.name}): {w}", err=True)
        if failed:
            raise typer.Exit(code=1)
        return

    total = 0
    for r in results:
        total += 1
        label = r.card_id or r.source.name
        if r.ok:
            typer.echo(f"PASS  {r.source}  ({label})")
        else:
            typer.echo(f"FAIL  {r.source}  ({label})")
            for error in r.errors:
                typer.echo(f"      - {error}")
        for warning in r.warnings:
            typer.echo(f"      ! {warning}")

    typer.echo("")
    typer.echo(f"{total - failed}/{total} card(s) passed.")
    if failed:
        raise typer.Exit(code=1)


def _resolve_and_load(catalog: Path | None) -> tuple[Path, list[tuple[Path, dict]]]:
    """Resolve the catalog path and load it, exiting cleanly on any known
    resolution/validation failure instead of raising a raw traceback."""
    try:
        catalog_path = resolve_catalog_path(catalog)
        pairs = load_catalog_with_sources(catalog_path)
        return catalog_path, pairs
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@app.command(name="list")
def list_capabilities(
    catalog: CatalogOption = None,
    domain: Annotated[str | None, typer.Option("--domain", help="Filter to this domain.")] = None,
    tag: Annotated[str | None, typer.Option("--tag", help="Filter to cards with this tag.")] = None,
    risk: Annotated[str | None, typer.Option("--risk", help="Filter by risk level.")] = None,
    owner: Annotated[str | None, typer.Option("--owner", help="Filter by owner.")] = None,
    search: Annotated[
        str | None,
        typer.Option("--search", help="Case-insensitive substring over id/intent/subject/tags."),
    ] = None,
    as_json: JsonOption = False,
) -> None:
    """List capability cards as a table: id, domain, subject, owner, risk, tags."""
    catalog_path, pairs = _resolve_and_load(catalog)

    rows = []
    for source, card in pairs:
        rows.append(
            {
                "id": card["id"],
                "domain": domain_for(source, catalog_path) or "-",
                "subject": card.get("subject", ""),
                "owner": card.get("owner", ""),
                "risk": (card.get("risk") or {}).get("level", ""),
                "tags": list(card.get("tags") or []),
                "intent": card.get("intent", ""),
            }
        )

    if domain:
        rows = [r for r in rows if r["domain"] == domain]
    if tag:
        rows = [r for r in rows if tag in r["tags"]]
    if risk:
        rows = [r for r in rows if r["risk"] == risk]
    if owner:
        rows = [r for r in rows if r["owner"] == owner]
    if search:
        needle = search.lower()
        rows = [
            r
            for r in rows
            if needle in r["id"].lower()
            or needle in r["intent"].lower()
            or needle in r["subject"].lower()
            or any(needle in t.lower() for t in r["tags"])
        ]

    if as_json:
        typer.echo(json.dumps(rows, indent=2))
        return

    if not rows:
        typer.echo("No capabilities matched.")
        return

    id_w = max(len("id"), *(len(r["id"]) for r in rows))
    domain_w = max(len("domain"), *(len(r["domain"]) for r in rows))
    subject_w = max(len("subject"), *(len(r["subject"]) for r in rows))
    owner_w = max(len("owner"), *(len(r["owner"]) for r in rows))
    risk_w = max(len("risk"), *(len(r["risk"]) for r in rows))

    header = (
        f"{'id':<{id_w}}  {'domain':<{domain_w}}  {'subject':<{subject_w}}  "
        f"{'owner':<{owner_w}}  {'risk':<{risk_w}}  tags"
    )
    typer.echo(header)
    typer.echo("-" * len(header))
    for r in rows:
        typer.echo(
            f"{r['id']:<{id_w}}  {r['domain']:<{domain_w}}  {r['subject']:<{subject_w}}  "
            f"{r['owner']:<{owner_w}}  {r['risk']:<{risk_w}}  {', '.join(r['tags'])}"
        )


@app.command()
def inspect(
    card_id: Annotated[str, typer.Argument(help="Capability card id to inspect.")],
    catalog: CatalogOption = None,
    as_json: JsonOption = False,
) -> None:
    """Print the full card for a single capability id."""
    _catalog_path, pairs = _resolve_and_load(catalog)
    cards = [card for _s, card in pairs]
    card = get_card(cards, card_id)
    if card is None:
        typer.echo(f"Capability '{card_id}' not found.", err=True)
        raise typer.Exit(code=1)

    if as_json:
        typer.echo(json.dumps(card, indent=2))
        return

    typer.echo(f"id:      {card['id']}")
    typer.echo(f"intent:  {card['intent']}")
    typer.echo(f"subject: {card['subject']}")
    typer.echo(f"owner:   {card['owner']}")
    risk = card.get("risk") or {}
    typer.echo(f"risk:    {risk.get('level', '-')}")
    if risk.get("notes"):
        typer.echo(f"         {risk['notes']}")
    if card.get("tags"):
        typer.echo(f"tags:    {', '.join(card['tags'])}")

    typer.echo("")
    typer.echo("inputs:")
    for i in card.get("inputs") or []:
        required = i.get("required", True)
        suffix = "" if required else " [optional]"
        typer.echo(f"  - {i['name']} ({i['type']}){suffix}")
        if i.get("description"):
            typer.echo(f"    {i['description']}")

    typer.echo("")
    typer.echo("outputs:")
    for o in card.get("outputs") or []:
        typer.echo(f"  - {o['name']} ({o['type']})")
        if o.get("description"):
            typer.echo(f"    {o['description']}")

    if card.get("semantic_refs"):
        typer.echo("")
        typer.echo("semantic_refs:")
        for ref in card["semantic_refs"]:
            typer.echo(f"  - {ref}")

    if card.get("behavior_profiles"):
        typer.echo("")
        typer.echo("behavior_profiles:")
        for profile in card["behavior_profiles"]:
            typer.echo(f"  - {profile['id']}: {profile['description']}")


@app.command()
def compare(
    a: Annotated[str, typer.Argument(help="First capability id.")],
    b: Annotated[str, typer.Argument(help="Second capability id.")],
    catalog: CatalogOption = None,
    as_json: JsonOption = False,
) -> None:
    """Structurally compare two capability cards (scalars, then shared /
    only-in-A / only-in-B for tags, semantic_refs, behavior_profiles, and
    name-matched inputs/outputs)."""
    catalog_path, pairs = _resolve_and_load(catalog)

    hit_a = get_card_with_source(pairs, a)
    hit_b = get_card_with_source(pairs, b)
    missing = [cid for cid, hit in ((a, hit_a), (b, hit_b)) if hit is None]
    if missing:
        typer.echo(f"Capability id(s) not found: {', '.join(missing)}.", err=True)
        raise typer.Exit(code=1)

    source_a, card_a = hit_a
    source_b, card_b = hit_b
    comparison = compare_cards(card_a, card_b)

    if as_json:
        payload = comparison_to_dict(comparison)
        payload["domain_a"] = domain_for(source_a, catalog_path)
        payload["domain_b"] = domain_for(source_b, catalog_path)
        typer.echo(json.dumps(payload, indent=2))
        return

    domain_a = domain_for(source_a, catalog_path) or "-"
    domain_b = domain_for(source_b, catalog_path) or "-"
    typer.echo(
        f"{comparison.id_a}  (domain: {domain_a})   vs   {comparison.id_b}  (domain: {domain_b})"
    )
    typer.echo("")

    if not comparison.scalar_diffs:
        typer.echo("scalars: identical (intent, subject, owner, risk.level)")
    else:
        typer.echo("scalars:")
        for d in comparison.scalar_diffs:
            typer.echo(f"  {d.field}:")
            typer.echo(f"    a: {d.a}")
            typer.echo(f"    b: {d.b}")

    for ld in comparison.list_diffs:
        typer.echo("")
        typer.echo(f"{ld.field}:")
        if not ld.shared and not ld.only_a and not ld.only_b:
            typer.echo("  (none)")
            continue
        for item in ld.shared:
            if isinstance(item, dict) and "changed" in item:
                key = item.get("name") or item.get("id")
                marker = "~" if item["changed"] else "="
                typer.echo(f"  {marker} {key}")
            else:
                typer.echo(f"  = {item}")
        for item in ld.only_a:
            label = item.get("name") or item.get("id") if isinstance(item, dict) else item
            typer.echo(f"  - {label} (only in {comparison.id_a})")
        for item in ld.only_b:
            label = item.get("name") or item.get("id") if isinstance(item, dict) else item
            typer.echo(f"  + {label} (only in {comparison.id_b})")


@app.command()
def export(
    format: Annotated[str, typer.Option("--format", help="mcp | openapi | md")],
    card_id: Annotated[
        str | None, typer.Argument(help="Capability id. Omit to export the whole catalog.")
    ] = None,
    catalog: CatalogOption = None,
    output: Annotated[
        Path | None, typer.Option("-o", "--output", help="Write to this path instead of stdout.")
    ] = None,
) -> None:
    """Project one card or the whole catalog into MCP tool JSON, an OpenAPI
    3.1 stub (YAML), or a Markdown document. One definition, many
    projections — no execution, no invocation runtime."""
    if format not in _EXPORT_FORMATS:
        typer.echo(
            f"Unknown export format '{format}'. Choose one of: {', '.join(_EXPORT_FORMATS)}.",
            err=True,
        )
        raise typer.Exit(code=1)

    catalog_path, pairs = _resolve_and_load(catalog)

    if card_id is not None:
        hit = get_card_with_source(pairs, card_id)
        if hit is None:
            typer.echo(f"Capability '{card_id}' not found.", err=True)
            raise typer.Exit(code=1)
        source, card = hit
        cards = [card]
        d = domain_for(source, catalog_path)
        domains = {card["id"]: d} if d is not None else {}
    else:
        cards = [card for _s, card in pairs]
        domains = {
            card["id"]: d
            for source, card in pairs
            if (d := domain_for(source, catalog_path)) is not None
        }

    if format == "mcp":
        text = json.dumps(to_mcp(cards), indent=2)
    elif format == "openapi":
        text = yaml.safe_dump(to_openapi(cards), sort_keys=False)
    else:
        text = to_markdown(cards, domains=domains)

    if output is not None:
        output.write_text(text, encoding="utf-8")
    else:
        typer.echo(text)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
