"""The per-user ordering rule.

LayoutItem.position is the only per-user authority and wins whenever a row
exists. A service without a LayoutItem row for this user is ordered by
Service.sort_order then id, and appended after that user's positioned tiles -
so a freshly created service (or a freshly registered account) never drops a
tile and never shows a random order.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def order_services(services: Sequence[Mapping[str, Any]], positions: Mapping[int, int]) -> list[Mapping[str, Any]]:
    positioned = [service for service in services if service["id"] in positions]
    unpositioned = [service for service in services if service["id"] not in positions]
    positioned.sort(key=lambda service: (positions[service["id"]], service["id"]))
    unpositioned.sort(key=lambda service: (service["sort_order"], service["id"]))
    return positioned + unpositioned


def group_by_category(
    categories: Sequence[Mapping[str, Any]], ordered_services: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Bucket ordered services under their category, in Category.sort_order.

    Categories with no tiles are dropped entirely: an empty heading is noise, and
    a group that exists only because of a search miss would look broken.
    """
    buckets: dict[int, list[Mapping[str, Any]]] = {}
    for service in ordered_services:
        buckets.setdefault(service["category_id"], []).append(service)

    groups: list[dict[str, Any]] = []
    for category in categories:
        services = buckets.get(category["id"], [])
        if not services:
            continue
        groups.append(
            {
                "id": category["id"],
                "name": category["name"],
                "sort_order": category["sort_order"],
                "services": services,
            }
        )
    return groups
