import pytest

from sales_insights.dashboard.kpis import KpiLabels, Kpis, compute_kpis, format_kpis

# --- compute_kpis -----------------------------------------------------------------------------


def test_the_four_figures_of_the_shared_fixture(loaded_orders):
    kpis = compute_kpis(loaded_orders)
    assert kpis == Kpis(
        revenue=1660.0, orders=6, average_order_value=pytest.approx(1660 / 6), customers=3
    )


def test_an_empty_table_gives_zeros(loaded_orders):
    assert compute_kpis(loaded_orders.iloc[0:0]) == Kpis(0.0, 0, 0.0, 0)


def test_one_order_is_its_own_average(loaded_orders):
    kpis = compute_kpis(loaded_orders.iloc[[1]])
    assert (kpis.revenue, kpis.orders, kpis.average_order_value, kpis.customers) == (
        500.0,
        1,
        500.0,
        1,
    )


def test_the_figures_have_plain_python_types(loaded_orders):
    kpis = compute_kpis(loaded_orders)
    assert type(kpis.revenue) is float
    assert type(kpis.average_order_value) is float
    assert type(kpis.orders) is int
    assert type(kpis.customers) is int


def test_the_kpis_are_frozen(loaded_orders):
    kpis = compute_kpis(loaded_orders)
    with pytest.raises(AttributeError):
        kpis.revenue = 0.0  # type: ignore[misc]


def test_the_figures_are_not_rounded_by_compute_kpis(loaded_orders):
    assert compute_kpis(loaded_orders).average_order_value == 1660 / 6


# --- format_kpis ------------------------------------------------------------------------------


def test_format_uses_thousands_separators_and_two_decimals():
    labels = format_kpis(Kpis(261333.44, 1234, 211.7, 4500))
    assert labels == KpiLabels(
        revenue="261,333.44", orders="1,234", average_order_value="211.70", customers="4,500"
    )


def test_format_of_zeros():
    assert format_kpis(Kpis(0.0, 0, 0.0, 0)) == KpiLabels("0.00", "0", "0.00", "0")


def test_format_of_millions():
    assert format_kpis(Kpis(12345678.9, 1, 12345678.9, 1)).revenue == "12,345,678.90"


@pytest.mark.parametrize(
    ("value", "text"),
    [(0.125, "0.13"), (2.675, "2.68"), (1.005, "1.01"), (0.124, "0.12"), (0.126, "0.13")],
)
def test_halves_round_up_as_a_person_would_expect(value, text):
    assert format_kpis(Kpis(value, 0, value, 0)).revenue == text
    assert format_kpis(Kpis(value, 0, value, 0)).average_order_value == text


def test_a_tiny_negative_value_does_not_show_minus_zero():
    assert format_kpis(Kpis(-0.001, 0, -0.001, 0)).revenue == "0.00"


def test_negative_revenue_keeps_its_sign():
    assert format_kpis(Kpis(-1234.5, 0, 0.0, 0)).revenue == "-1,234.50"


def test_formatting_never_changes_the_computed_value(loaded_orders):
    kpis = compute_kpis(loaded_orders)
    format_kpis(kpis)
    assert kpis.average_order_value == 1660 / 6


# --- very large amounts -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1e15, "1,000,000,000,000,000.00"),
        (1e27, "1,000,000,000,000,000,000,000,000,000.00"),
        (1.2345678901234568e29, "123,456,789,012,345,680,000,000,000,000.00"),
        (-1e30, "-1,000,000,000,000,000,000,000,000,000,000.00"),
    ],
)
def test_an_amount_with_more_than_28_digits_is_written_in_full_not_refused(value, expected):
    assert format_kpis(Kpis(value, 1, value, 1)).revenue == expected


def test_the_largest_float_does_not_raise_and_has_two_decimals():
    text = format_kpis(Kpis(1.7976931348623157e308, 1, 1.0, 1)).revenue
    assert text.endswith(".00") and text.startswith("179,769,313,486,231,570")
    assert len(text.replace(",", "")) == 312  # 309 digits, a point and two decimals


def test_rounding_half_up_still_holds_for_ordinary_amounts():
    assert format_kpis(Kpis(2.675, 1, 0.005, 1)).revenue == "2.68"
    assert format_kpis(Kpis(2.675, 1, 0.005, 1)).average_order_value == "0.01"
