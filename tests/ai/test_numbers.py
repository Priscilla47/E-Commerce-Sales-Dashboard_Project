from decimal import Decimal

import pytest

from sales_insights.ai.numbers import unknown_numbers


def allowed(*values):
    return [Decimal(repr(v)) for v in values]


def test_a_text_without_numbers_has_no_unknown_number():
    assert unknown_numbers("Sales rose.", allowed(1)) == []


def test_an_exact_or_rounded_number_is_accepted():
    for text in ("261333.44", "261333.4", "261333", "261,333.44", "261,333"):
        assert unknown_numbers(f"It was {text}.", allowed(261333.44)) == [], text


def test_a_number_with_more_than_two_decimals_must_match_exactly():
    assert unknown_numbers("It was 2.645.", allowed(2.6457513)) == ["2.645"]
    assert unknown_numbers("It was 2.6457513.", allowed(2.6457513)) == []


def test_a_percent_may_be_a_share_and_a_plain_number_may_not():
    assert unknown_numbers("30% of sales", allowed(0.3)) == []
    assert unknown_numbers("30 of sales", allowed(0.3)) == ["30"]


def test_the_sign_is_not_compared():
    assert unknown_numbers("down 12.5", allowed(-12.5)) == []


@pytest.mark.parametrize("text", ["1k", "1.2M", "3 million", "2bn", "5 thousand"])
def test_an_abbreviation_is_never_accepted_even_when_the_value_is_allowed(text):
    assert len(unknown_numbers(f"about {text}", allowed(1, 1.2, 3, 2, 5, 1000, 3e6))) == 1


def test_a_word_that_starts_like_an_abbreviation_is_not_one():
    assert unknown_numbers("8 months and 3 books and 2 bars", allowed(8, 3, 2)) == []


def test_names_are_removed_before_reading_numbers():
    assert unknown_numbers("Model 3000 sold 8.", allowed(8), names=["Model 3000"]) == []
    assert unknown_numbers("Model 3000 sold 3000.", allowed(8), names=["Model 3000"]) == ["3000"]


def test_the_longest_name_is_removed_first():
    names = ["Model 3", "Model 3000"]
    assert unknown_numbers("Model 3000 and Model 3", allowed(), names=names) == []


def test_unknown_numbers_come_in_order_without_repeats():
    assert unknown_numbers("5, 7, 5, 9", allowed(7)) == ["5", "9"]


def test_half_up_rounding_not_banker_rounding():
    assert unknown_numbers("0.5 and 1.5 and 2.5", allowed(0.5, 1.5, 2.5)) == []
    assert unknown_numbers("It was 3.", allowed(2.5)) == []
    assert unknown_numbers("It was 2.", allowed(2.5)) == ["2"]
