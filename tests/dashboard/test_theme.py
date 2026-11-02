import re

import pytest

from sales_insights.dashboard.theme import (
    DARK_BACKGROUND,
    LIGHT_BACKGROUND,
    PALETTE,
    contrast_ratio,
)

# --- contrast_ratio ---------------------------------------------------------------------------


def test_black_on_white_is_the_largest_possible_contrast():
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0)


def test_a_colour_against_itself_has_no_contrast():
    assert contrast_ratio("#2E7BC4", "#2E7BC4") == pytest.approx(1.0)


def test_the_order_of_the_two_colours_does_not_matter():
    assert contrast_ratio("#2E7BC4", "#FFFFFF") == contrast_ratio("#FFFFFF", "#2E7BC4")


def test_grey_777_on_white_is_the_known_value():
    # #777777 on white is the classic borderline case: 4.48 to two decimals.
    assert round(contrast_ratio("#777777", "#FFFFFF"), 2) == 4.48


@pytest.mark.parametrize("bad", ["", "red", "#FFF", "#GGGGGG", "FFFFFF", "#FFFFFFF", None, 5])
def test_a_colour_that_is_not_a_six_digit_hex_is_refused(bad):
    with pytest.raises(ValueError, match="colour"):
        contrast_ratio(bad, "#FFFFFF")
    with pytest.raises(ValueError, match="colour"):
        contrast_ratio("#FFFFFF", bad)


def test_lowercase_hex_is_accepted():
    assert contrast_ratio("#ffffff", "#000000") == pytest.approx(21.0)


# --- the palette ------------------------------------------------------------------------------


def test_the_palette_has_a_few_distinct_colours():
    assert 3 <= len(PALETTE) <= 6
    assert len({colour.upper() for colour in PALETTE}) == len(PALETTE)


def test_every_colour_is_a_six_digit_hex_code():
    for colour in (*PALETTE, LIGHT_BACKGROUND, DARK_BACKGROUND):
        assert re.fullmatch(r"#[0-9A-Fa-f]{6}", colour), colour


@pytest.mark.parametrize("background", [LIGHT_BACKGROUND, DARK_BACKGROUND])
def test_every_series_colour_has_a_contrast_of_at_least_3_to_1_with_both_backgrounds(background):
    for colour in PALETTE:
        assert contrast_ratio(colour, background) >= 3.0, (colour, background)


def test_the_two_backgrounds_are_the_light_and_the_dark_one():
    assert LIGHT_BACKGROUND.upper() == "#FFFFFF"
    assert contrast_ratio(LIGHT_BACKGROUND, DARK_BACKGROUND) > 10
