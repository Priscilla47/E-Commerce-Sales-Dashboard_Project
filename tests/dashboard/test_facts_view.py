import pandas as pd
import pytest

from sales_insights.ai.facts import compute_facts
from sales_insights.dashboard.facts_view import facts_bullets
from sales_insights.dashboard.kpis import format_money
from tests.ai.helpers import SPIKE, monthly_orders


def test_format_money_is_the_text_of_the_cards():
    assert format_money(261333.44) == "261,333.44"
    assert format_money(2.675) == "2.68"
    assert format_money(-0.001) == "0.00"
    assert format_money(float("nan")) == "n/a"


def test_the_bullets_say_each_fact_with_the_numbers_of_the_facts():
    facts = compute_facts(monthly_orders(SPIKE, product="Pen"))
    text = "\n".join(facts_bullets(facts))
    assert "8 orders from 2023-01-31 to 2023-08-31" in text
    assert "trending up" in text and "about 75.00 more each month" in text
    assert "best month was 2023-08 with 1,000.00" in text.replace("**", "")
    assert "worst month was 2023-01 with 100.00" in text.replace("**", "")
    assert "2023-08" in text and "2.65" in text  # the anomaly and its z-score
    assert "Pen" in text and "8 units" in text


def test_a_flat_series_says_flat_and_no_anomaly_line_is_written():
    text = "\n".join(facts_bullets(compute_facts(monthly_orders([500.0] * 8))))
    assert "flat" in text.lower()
    assert "unusual" not in text.lower()


def test_share_changes_are_written_with_both_shares_and_the_points():
    rows = []
    for half, shares in enumerate(((50.0, 50.0), (80.0, 20.0))):
        for country, revenue in zip(("France", "UK"), shares, strict=True):
            rows.append(
                (
                    len(rows) + 1,
                    pd.Timestamp(2025, 1 + half * 6, 15),
                    "P",
                    1,
                    country,
                    "Books",
                    revenue,
                )
            )
    rows.append((90, pd.Timestamp(2025, 12, 31), "P", 1, "France", "Books", 0.0))
    frame = pd.DataFrame(
        rows, columns=["OrderID", "Date", "Product", "Quantity", "Country", "Category", "Revenue"]
    )
    text = "\n".join(facts_bullets(compute_facts(frame)))
    assert "France" in text and "50.0%" in text and "80.0%" in text and "+30.0 points" in text
    assert "UK" in text and "-30.0 points" in text


def test_the_notes_and_the_anomaly_note_are_kept():
    text = "\n".join(facts_bullets(compute_facts(monthly_orders([100.0, 200.0, 300.0]))))
    assert "at least 6 complete months, found 3" in text


def test_an_empty_table_has_one_bullet_that_says_there_are_no_orders():
    bullets = facts_bullets(compute_facts(monthly_orders([1.0]).iloc[0:0]))
    assert bullets == ["There are no orders to describe."]


@pytest.mark.parametrize("name", ["<b>x</b>", "*bold* _it_ [l](u)", "a|b"])
def test_text_from_the_data_is_escaped_for_markdown(name):
    text = "\n".join(facts_bullets(compute_facts(monthly_orders(SPIKE, product=name))))
    assert name not in text
