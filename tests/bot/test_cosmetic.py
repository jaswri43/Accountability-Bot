from datetime import datetime, timezone
from types import SimpleNamespace

from cosmetic import number_items, resolve_cosmetic_number, sort_by_tier_then_date


def item(name, tier, created_at):
    return SimpleNamespace(name=name, tier=tier, created_at=created_at)


def test_number_items_is_one_indexed_in_given_order():
    assert number_items(["a", "b", "c"]) == [(1, "a"), (2, "b"), (3, "c")]
    assert number_items([]) == []


def test_resolve_cosmetic_number_round_trips():
    items = ["a", "b", "c"]
    for number, value in number_items(items):
        assert resolve_cosmetic_number(items, number) == value


def test_resolve_cosmetic_number_out_of_range():
    items = ["a", "b"]
    assert resolve_cosmetic_number(items, 0) is None
    assert resolve_cosmetic_number(items, 3) is None
    assert resolve_cosmetic_number(items, -1) is None


def test_sort_is_tier_first_then_oldest_first():
    items = [
        item("high-old", "high", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        item("low-new", "low", datetime(2026, 3, 1, tzinfo=timezone.utc)),
        item("medium", "medium", datetime(2026, 2, 1, tzinfo=timezone.utc)),
        item("low-old", "low", datetime(2026, 1, 1, tzinfo=timezone.utc)),
    ]
    assert [i.name for i in sort_by_tier_then_date(items)] == ["low-old", "low-new", "medium", "high-old"]


def test_missing_tier_sorts_as_low():
    items = [
        item("medium", "medium", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        item("untiered", None, datetime(2026, 2, 1, tzinfo=timezone.utc)),
    ]
    assert [i.name for i in sort_by_tier_then_date(items)] == ["untiered", "medium"]


def test_sort_handles_naive_and_aware_datetimes_together():
    # Rows read back from SQLite are naive; a freshly created row is aware.
    # Comparing the two raised TypeError in production (/addtask).
    items = [
        item("fresh", "low", datetime(2026, 2, 1, tzinfo=timezone.utc)),
        item("from-db", "low", datetime(2026, 1, 1)),
    ]
    assert [i.name for i in sort_by_tier_then_date(items)] == ["from-db", "fresh"]
