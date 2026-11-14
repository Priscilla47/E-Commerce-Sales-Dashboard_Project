from decimal import Decimal

import pytest

from sales_insights.ai.numbers import Allowed, dates_in, digits_in, number, unknown_numbers


def allowed(numbers=(), percents=(), dates=(), names=()):
    return Allowed(
        tuple(Decimal(str(n)) for n in numbers),
        tuple(Decimal(str(p)) for p in percents),
        tuple(dates),
        tuple(names),
    )


FACTS = allowed(numbers=[1000.0, 8, 2.65, 0.3, 2023], percents=[30], dates=["2023-08"])


@pytest.mark.parametrize(
    "text",
    ["1000.0", "1,000", "1000", "8", "-8", "2.65", "2.7", "30%", "30 percent", "30 per cent"],
)
def test_allowed_numbers_are_accepted_as_written(text):
    assert unknown_numbers(f"It was {text}.", FACTS) == []


def test_a_percent_must_be_an_allowed_percent_not_any_number():
    # 8 orders and 1000.0 are numbers of the facts, but "800%" or "8%" are not shares.
    assert unknown_numbers("Orders rose 8% and 800%.", FACTS) == ["8%", "800%"]


@pytest.mark.parametrize(
    "text, refused",
    [
        ("Revenue grew 1e5.", "1e5"),
        ("Revenue grew 8E3.", "8E3"),
        ("It was 2,0,2,3.", "2,0,2,3"),
        ("It was 8/8 of the sales.", "8/8"),
        ("It was 2023.8.8.", "2023.8.8"),
        ("It was 8 millions.", "8 millions"),
        ("It was 8 trillion.", "8 trillion"),
        ("It was 8 thousands.", "8 thousands"),
        ("It was 8k.", "8k"),
    ],
)
def test_what_cannot_be_checked_is_refused_whatever_its_digits(text, refused):
    assert unknown_numbers(text, FACTS) == [refused]


def test_invisible_characters_cannot_split_a_number():
    assert unknown_numbers("Revenue grew 4​5%.", FACTS) == ["45%"]
    assert unknown_numbers("Revenue grew 3​0%.", FACTS) == []  # 30% is a share


def test_other_digits_are_read_as_the_digits_they_show():
    assert unknown_numbers("It was \u0663\u0667.", FACTS) == ["37"]  # arabic-indic digits
    assert unknown_numbers("It was \uff18 orders.", FACTS) == []  # a full-width 8
    assert unknown_numbers("It was \u00b3\u2077%.", FACTS) == ["37%"]  # superscripts


def test_a_number_that_is_no_digit_is_refused():
    assert unknown_numbers("Half of it: ½.", FACTS) != []
    assert unknown_numbers("Chapter Ⅻ.", FACTS) == []  # a roman numeral is letters


def test_a_date_must_be_a_date_of_the_facts_or_the_month_of_one():
    with_day = allowed(dates=["2023-08", "2023-01-31"])
    assert unknown_numbers("The peak was 2023-08 and it began 2023-01-31.", with_day) == []
    assert unknown_numbers("It began in 2023-01.", with_day) == []
    assert unknown_numbers("The peak was 2023-07.", with_day) == ["2023-07"]
    assert unknown_numbers("On 2023-08-15 it peaked.", with_day) == ["2023-08-15"]


def test_a_range_of_years_is_two_numbers_not_a_date():
    assert unknown_numbers("From 2023-2023.", FACTS) == []


def test_a_name_is_skipped_only_where_it_stands_as_a_word():
    names = allowed(numbers=[8], names=["Model 3000", "M"])
    assert unknown_numbers("Model 3000 sold 8.", names) == []
    assert unknown_numbers("Revenue was 500M.", names) == ["500M"]
    assert unknown_numbers("Revenue was 500 M.", names) == ["500"]  # refused all the same
    assert unknown_numbers("It sold Model 30000.", names) == ["30000"]


def test_a_name_without_a_letter_never_removes_digits():
    names = allowed(numbers=[8], names=["1", "37"])
    assert unknown_numbers("Revenue grew 17%, then 1,000,111.", names) == ["17%", "1,000,111"]
    assert unknown_numbers("Product 37 sold 8.", names) == ["37"]


def test_a_name_followed_by_a_percent_is_not_a_name():
    names = allowed(names=["Pen 37"])
    assert unknown_numbers("Pen 37% of it.", names) == ["37%"]


def test_a_huge_allowed_number_is_compared_without_overflow():
    huge = Allowed((number(1.7976931348623157e308), number(1e27)))
    assert unknown_numbers("It grew 37.5.", huge) == ["37.5"]
    assert unknown_numbers("It was 1,000,000,000,000,000,000,000,000,000.", huge) == []


def test_the_helpers_read_dates_digits_and_numbers():
    assert dates_in("left out (2025-05), from 2025-01-01") == ["2025-05", "2025-01-01"]
    assert digits_in("day 1 of 31") == [Decimal(1), Decimal(31)]
    assert number(-2.5) == Decimal("2.5") and number(3) == Decimal(3)


def test_unknown_numbers_are_listed_once_in_order():
    assert unknown_numbers("37, 12, 37 and 8.", FACTS) == ["37", "12"]


# --- the rules shared by the insights and the answers -------------------------------------------


def only(*values, percents=(), names=()):
    return Allowed(
        tuple(number(v) for v in values), tuple(Decimal(str(p)) for p in percents), (), names
    )


def test_a_text_without_numbers_has_no_unknown_number():
    assert unknown_numbers("Sales rose.", only(1)) == []


def test_an_exact_or_rounded_number_is_accepted():
    for text in ("261333.44", "261333.4", "261333", "261,333.44", "261,333"):
        assert unknown_numbers(f"It was {text}.", only(261333.44)) == [], text


def test_a_number_with_more_than_two_decimals_must_match_exactly():
    assert unknown_numbers("It was 2.645.", only(2.6457513)) == ["2.645"]
    assert unknown_numbers("It was 2.6457513.", only(2.6457513)) == []


def test_a_percent_must_be_given_as_a_percent_and_a_plain_number_may_not_be_a_share():
    assert unknown_numbers("30% of sales", only(0.3, percents=[30])) == []
    assert unknown_numbers("30 of sales", only(0.3, percents=[30])) == ["30"]


def test_the_sign_is_not_compared():
    assert unknown_numbers("down 12.5", only(-12.5)) == []


@pytest.mark.parametrize("text", ["1k", "1.2M", "3 million", "2bn", "5 thousand"])
def test_an_abbreviation_is_never_accepted_even_when_the_value_is_allowed(text):
    assert len(unknown_numbers(f"about {text}", only(1, 1.2, 3, 2, 5, 1000, 3e6))) == 1


def test_a_word_that_starts_like_an_abbreviation_is_not_one():
    assert unknown_numbers("8 months and 3 books and 2 bars", only(8, 3, 2)) == []


def test_the_longest_name_is_skipped_first():
    names = ("Model 3", "Model 3000")
    assert unknown_numbers("Model 3000 and Model 3", only(names=names)) == []


def test_half_up_rounding_not_banker_rounding():
    assert unknown_numbers("0.5 and 1.5 and 2.5", only(0.5, 1.5, 2.5)) == []
    assert unknown_numbers("It was 3.", only(2.5)) == []
    assert unknown_numbers("It was 2.", only(2.5)) == ["2"]
