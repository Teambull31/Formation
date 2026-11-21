from app.main import total


def test_total_sums_price_times_quantity():
    assert total([{"price": 2.5, "qty": 2}, {"price": 1, "qty": 3}]) == 8.0


def test_total_of_empty_order_is_zero():
    assert total([]) == 0


def test_total_rounds_to_cents():
    assert total([{"price": 0.1, "qty": 3}]) == 0.3
