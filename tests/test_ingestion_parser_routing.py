from __future__ import annotations

from src.common.schemas import ParserRoute
from src.ingestion.parser_routing import (
    DocumentStructuralProfile,
    ParserAvailability,
    plan_route_batches,
    resolve_parser_route,
)


def test_resolve_parser_route_prefers_tagged_fast_path() -> None:
    route = resolve_parser_route(
        DocumentStructuralProfile(has_struct_tree=True, born_digital=True, layout_complex=True),
        ParserAvailability(opendataloader_available=True, hybrid_backend_healthy=True),
    )

    assert route is ParserRoute.TAGGED


def test_resolve_parser_route_selects_hybrid_for_born_digital_or_layout_complex_docs() -> None:
    route = resolve_parser_route(
        DocumentStructuralProfile(has_struct_tree=False, born_digital=True, layout_complex=False),
        ParserAvailability(opendataloader_available=True, hybrid_backend_healthy=True),
    )

    assert route is ParserRoute.HYBRID


def test_resolve_parser_route_downgrades_to_local_only_when_hybrid_backend_is_unhealthy() -> None:
    route = resolve_parser_route(
        DocumentStructuralProfile(has_struct_tree=False, born_digital=True, layout_complex=True),
        ParserAvailability(opendataloader_available=True, hybrid_backend_healthy=False),
    )

    assert route is ParserRoute.LOCAL_ONLY


def test_resolve_parser_route_uses_baseline_fallback_when_opendataloader_is_unavailable() -> None:
    route = resolve_parser_route(
        DocumentStructuralProfile(has_struct_tree=False, born_digital=True, layout_complex=True),
        ParserAvailability(opendataloader_available=False, hybrid_backend_healthy=False),
    )

    assert route is ParserRoute.BASELINE_FALLBACK


def test_plan_route_batches_groups_documents_without_mixing_routes() -> None:
    batches = plan_route_batches(
        {
            "alpha": ParserRoute.TAGGED,
            "beta": ParserRoute.HYBRID,
            "gamma": ParserRoute.HYBRID,
            "delta": ParserRoute.LOCAL_ONLY,
            "epsilon": ParserRoute.BASELINE_FALLBACK,
        }
    )

    assert [(batch.route, batch.doc_ids) for batch in batches] == [
        (ParserRoute.TAGGED, ["alpha"]),
        (ParserRoute.HYBRID, ["beta", "gamma"]),
        (ParserRoute.LOCAL_ONLY, ["delta"]),
        (ParserRoute.BASELINE_FALLBACK, ["epsilon"]),
    ]
