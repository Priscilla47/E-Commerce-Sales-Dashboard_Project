import json

import pytest

from sales_insights.ai.nlq import Answer
from sales_insights.ai.tools import ToolResult
from sales_insights.dashboard.chat_view import Turn, call_data, call_title, status_of


def result(name="top_products", arguments=None, data=None):
    return ToolResult(name, arguments if arguments is not None else {"n": 1}, data or {"rows": []})


def test_a_call_title_is_the_function_with_its_arguments():
    assert call_title(result()) == "top_products(n=1)"
    assert call_title(result("total_revenue", {})) == "total_revenue()"
    assert call_title(result("revenue_by", {"column": "Country"})) == "revenue_by(column='Country')"


def test_a_text_argument_is_shown_with_python_quoting_and_stays_one_line():
    title = call_title(result("units_sold_for", {"product": "O'Neil\nline"}))
    assert "\n" not in title and "O" in title


def test_the_data_of_a_call_is_pretty_json_that_parses_back():
    data = {"rows": [{"Product": "Book", "units": 6}], "truncated": False}
    text = call_data(result(data=data))
    assert json.loads(text) == data
    assert "\n" in text


def test_an_answered_turn_has_the_status_answered():
    turn = Turn("What sells best?", Answer("Book.", True, (result(),)), orders=500)
    assert status_of(turn) == "answered"


def test_a_refusal_is_a_refusal_and_a_failed_call_is_a_failure():
    refused = Turn("q", Answer(None, False, (), "I can't answer that."), orders=5)
    failed = Turn("q", Answer(None, False, (), "timed out", True), orders=5)
    assert (status_of(refused), status_of(failed)) == ("refused", "failed")


def test_a_turn_is_frozen_and_remembers_how_many_orders_it_was_made_from():
    turn = Turn("q", Answer("a", True), orders=52)
    assert turn.orders == 52
    with pytest.raises(AttributeError):
        turn.orders = 1  # type: ignore[misc]
