from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[2] / "src" / "sales_insights" / "dashboard" / "app.py"


@pytest.fixture
def app() -> AppTest:
    return AppTest.from_file(str(APP), default_timeout=60)


def texts(at: AppTest) -> str:
    """Everything the page says, as one text."""
    parts = [element.value for element in at.markdown]
    parts += [element.value for element in at.caption]
    parts += [element.value for element in at.info]
    parts += [element.value for element in at.error]
    parts += [element.value for element in at.warning]
    parts += [element.value for element in at.success]
    return "\n".join(str(part) for part in parts)


def test_the_app_runs_on_the_sample_data_without_exception(app):
    app.run()
    assert not app.exception


def test_the_sample_data_is_the_default_source(app):
    app.run()
    assert app.sidebar.radio[0].value == "Sample data"
    assert "500 orders loaded" in texts(app)


def test_choosing_upload_without_a_file_asks_for_one_and_shows_no_figure(app):
    app.run()
    app.sidebar.radio[0].set_value("Upload a CSV").run()
    assert not app.exception
    assert "Upload a CSV file" in texts(app)
    assert "orders loaded" not in texts(app)


def test_going_back_to_the_sample_shows_the_orders_again(app):
    app.run()
    app.sidebar.radio[0].set_value("Upload a CSV").run()
    app.sidebar.radio[0].set_value("Sample data").run()
    assert "500 orders loaded" in texts(app)


def test_the_page_has_a_title(app):
    app.run()
    assert [title.value for title in app.title] == ["Sales insights"]


# --- uploading a file ----------------------------------------------------------------------

HEADER = "OrderID,Date,Product,Category,UnitPrice,Quantity,CustomerID,Country\n"


def upload(at: AppTest, content: bytes, name: str = "orders.csv") -> AppTest:
    """Choose the upload source and give it a file."""
    at.run()
    at.sidebar.radio[0].set_value("Upload a CSV").run()
    return at.sidebar.file_uploader[0].set_value((name, content, "text/csv")).run()


def test_a_valid_upload_is_loaded(app):
    content = (
        HEADER + "1,2025-01-05,Book,Books,10,2,C1,France\n2,2025-01-06,Book,Books,10,1,C2,UK\n"
    ).encode()
    app = upload(app, content)
    assert not app.exception
    assert "2 orders loaded" in texts(app)
    assert not app.error


def test_an_upload_with_missing_columns_shows_the_message_and_no_figure(app):
    app = upload(app, b"OrderID,Date\n1,2025-01-01\n")
    assert not app.exception
    assert "Missing required column(s)" in texts(app)
    assert "UnitPrice" in texts(app)
    assert "orders loaded" not in texts(app)


def test_an_empty_upload_shows_a_message_and_no_exception(app):
    app = upload(app, b"")
    assert not app.exception
    assert "empty" in texts(app)
    assert "orders loaded" not in texts(app)


def test_a_non_utf8_upload_shows_a_message_and_no_exception(app):
    app = upload(app, (HEADER + "1,2025-01-05,Café,Food,10,2,C1,France\n").encode("latin-1"))
    assert not app.exception
    assert "UTF-8" in texts(app)


def test_an_upload_with_data_errors_does_not_crash_the_page(app):
    app = upload(app, (HEADER + "1,2025-01-05,Book,Books,10,-2,C1,France\n").encode())
    assert not app.exception
    assert "1 order loaded" in texts(app)


# --- key figures and filters ---------------------------------------------------------------
# Expected values are computed here with plain pandas on the raw file, not with the code under
# test.

import datetime  # noqa: E402

import pandas as pd  # noqa: E402

SAMPLE = pd.read_csv(
    APP.parents[3] / "data" / "sample_orders.csv", keep_default_na=False, na_values=[""]
)
SAMPLE["Revenue"] = SAMPLE["UnitPrice"] * SAMPLE["Quantity"]


def cards(at: AppTest) -> dict[str, str]:
    return {metric.label: metric.value for metric in at.metric}


def expected_cards(rows: pd.DataFrame) -> dict[str, str]:
    orders = rows["OrderID"].nunique()
    average = rows["Revenue"].sum() / orders if orders else 0.0
    return {
        "Revenue": f"{rows['Revenue'].sum():,.2f}",
        "Orders": f"{orders:,}",
        "Average order value": f"{average:,.2f}",
        "Customers": f"{rows['CustomerID'].nunique():,}",
    }


def test_four_cards_show_the_key_figures_of_the_sample(app):
    app.run()
    assert list(cards(app)) == ["Revenue", "Orders", "Average order value", "Customers"]
    assert cards(app) == expected_cards(SAMPLE)
    assert cards(app)["Revenue"] == "261,333.44"


def test_the_sidebar_has_a_period_and_two_selectors_filled_from_the_data(app):
    app.run()
    assert app.sidebar.date_input[0].label == "Period"
    assert app.sidebar.date_input[0].value == (
        datetime.date.fromisoformat(SAMPLE["Date"].min()),
        datetime.date.fromisoformat(SAMPLE["Date"].max()),
    )
    labels = {box.label: box for box in app.sidebar.multiselect}
    assert set(labels) == {"Countries", "Categories"}
    assert labels["Countries"].options == sorted(SAMPLE["Country"].dropna().unique())
    assert labels["Categories"].options == sorted(SAMPLE["Category"].dropna().unique())
    assert labels["Countries"].value == labels["Countries"].options


def test_choosing_a_country_changes_the_cards(app):
    app.run()
    country = sorted(SAMPLE["Country"].dropna().unique())[0]
    countries = next(box for box in app.sidebar.multiselect if box.label == "Countries")
    countries.set_value([country]).run()
    assert not app.exception
    assert cards(app) == expected_cards(SAMPLE[SAMPLE["Country"] == country])
    assert cards(app)["Revenue"] != "261,333.44"


def test_choosing_a_category_changes_the_cards(app):
    app.run()
    category = sorted(SAMPLE["Category"].dropna().unique())[0]
    categories = next(box for box in app.sidebar.multiselect if box.label == "Categories")
    categories.set_value([category]).run()
    assert cards(app) == expected_cards(SAMPLE[SAMPLE["Category"] == category])


def test_choosing_a_period_changes_the_cards(app):
    app.run()
    start, end = datetime.date(2025, 2, 1), datetime.date(2025, 3, 31)
    app.sidebar.date_input[0].set_value((start, end)).run()
    dates = pd.to_datetime(SAMPLE["Date"])
    rows = SAMPLE[(dates >= "2025-02-01") & (dates < "2025-04-01")]
    assert 0 < len(rows) < len(SAMPLE)
    assert cards(app) == expected_cards(rows)


def test_a_filter_that_matches_nothing_shows_zeros_and_no_error(app):
    app.run()
    countries = next(box for box in app.sidebar.multiselect if box.label == "Countries")
    countries.set_value([]).run()
    assert not app.exception
    assert not app.error
    assert cards(app) == {
        "Revenue": "0.00",
        "Orders": "0",
        "Average order value": "0.00",
        "Customers": "0",
    }


def test_an_upload_gets_its_own_filters_and_cards(app):
    content = (
        HEADER + "1,2025-01-05,Book,Books,10,2,C1,France\n2,2025-01-06,Book,Books,10,1,C2,UK\n"
    ).encode()
    app = upload(app, content)
    assert not app.exception
    assert cards(app)["Revenue"] == "30.00"
    assert cards(app)["Customers"] == "2"
    countries = next(box for box in app.sidebar.multiselect if box.label == "Countries")
    assert countries.options == ["France", "UK"]
    countries.set_value(["UK"]).run()
    assert cards(app)["Revenue"] == "10.00"


def test_selecting_everything_keeps_an_order_whose_country_is_missing(app):
    content = (
        HEADER + "1,2025-01-05,Book,Books,10,2,C1,France\n2,2025-01-06,Book,Books,10,1,C2,\n"
    ).encode()
    app = upload(app, content)
    assert cards(app)["Orders"] == "2"
    assert cards(app)["Revenue"] == "30.00"


def test_an_upload_without_any_date_still_shows_the_cards(app):
    content = (HEADER + "1,,Book,Books,10,2,C1,France\n").encode()
    app = upload(app, content)
    assert not app.exception
    assert cards(app)["Revenue"] == "20.00"
    assert not app.sidebar.date_input


# --- the three states of the data ----------------------------------------------------------
# blocked (an error box, no figure), loaded with errors (a warning box and the figures), loaded.

GOOD = "{n},2025-01-05,Book,Books,10,2,C{n},France\n"
NEGATIVE = "{n},2025-01-05,Book,Books,10,-2,C{n},France\n"


def csv_with(good: int, bad: int) -> bytes:
    """A file whose first ``bad`` orders have a negative quantity (lines 2, 3, ...)."""
    rows = [NEGATIVE.format(n=n) for n in range(1, bad + 1)]
    rows += [GOOD.format(n=n) for n in range(bad + 1, bad + good + 1)]
    return (HEADER + "".join(rows)).encode()


def test_a_clean_file_shows_no_warning_box_and_no_note(app):
    app = upload(app, csv_with(good=3, bad=0))
    assert not app.warning
    assert not app.error
    assert not app.expander
    assert cards(app)["Orders"] == "3"


def test_a_missing_column_blocks_the_page_with_the_message_of_the_command_line(app):
    content = HEADER.replace("UnitPrice,", "").encode() + b"1,2025-01-05,Book,Books,2,C1,France\n"
    app = upload(app, content)
    assert not app.exception
    assert len(app.error) == 1
    assert app.error[0].value == "Missing required column(s): UnitPrice"
    assert not app.metric
    assert not app.sidebar.multiselect


def test_three_bad_rows_are_listed_and_the_figures_are_still_shown(app):
    app = upload(app, csv_with(good=2, bad=3))
    assert not app.exception
    assert len(app.warning) == 1
    box = app.warning[0].value
    for line in (2, 3, 4):
        assert f"line {line}: Negative value in column 'Quantity'" in box
    assert "line 5" not in box
    assert "more" not in box
    assert cards(app)["Orders"] == "5"


def test_fifty_bad_rows_list_twenty_lines_and_say_thirty_more(app):
    app = upload(app, csv_with(good=1, bad=50))
    box = app.warning[0].value
    assert box.count("Negative value in column 'Quantity'") == 20
    assert "and 30 more" in box
    assert "line 21:" in box
    assert "line 22:" not in box
    assert cards(app)["Orders"] == "51"


def test_the_warning_box_says_how_many_errors_there_are(app):
    app = upload(app, csv_with(good=1, bad=3))
    assert "3 errors" in app.warning[0].value
    app = upload(AppTest.from_file(str(APP), default_timeout=60), csv_with(good=1, bad=1))
    assert "1 error " in app.warning[0].value + " "


def test_warnings_only_are_in_a_collapsed_note_and_not_in_the_warning_box(app):
    # A zero quantity is a warning, not an error.
    content = HEADER.encode() + b"1,2025-01-05,Book,Books,10,0,C1,France\n"
    app = upload(app, content)
    assert not app.exception
    assert not app.warning
    assert len(app.expander) == 1
    assert app.expander[0].label == "1 warning about the data"
    assert "line 2: Quantity is zero" in "\n".join(m.value for m in app.expander[0].markdown)
    assert cards(app)["Orders"] == "1"


def test_errors_and_warnings_show_both_boxes(app):
    content = (
        HEADER.encode()
        + b"1,2025-01-05,Book,Books,10,-2,C1,France\n2,2025-01-05,Book,Books,10,0,C2,France\n"
    )
    app = upload(app, content)
    assert len(app.warning) == 1
    assert len(app.expander) == 1


def test_the_sample_data_has_no_box_at_all(app):
    app.run()
    assert not app.warning
    assert not app.error
    assert not app.expander


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"\x00\x01\x02",
        b"\x89PNG\r\n\x1a\n\x00\x00",
        b"OrderID\n1\n",
        (HEADER + "x,y,z\n").encode(),
        HEADER.encode(),
        (HEADER + "1,2025-13-45,Book,Books,10,2,C1,France\n").encode(),
        (HEADER + "1,2025-01-05,Book,Books,abc,2,C1,France\n").encode(),
        (b"OrderID;Date;Product\n1;2025-01-05;Book\n"),
        (HEADER + "1,2025-01-05,Café,Food,10,2,C1,France\n").encode("latin-1"),
    ],
)
def test_no_uploaded_content_makes_the_page_raise(app, content):
    app = upload(app, content)
    assert not app.exception


def test_text_from_the_file_is_shown_as_text_not_as_markdown(app):
    # The casing warning quotes the product names of the file.
    hostile = "[click](http://evil.example)"
    content = (
        HEADER
        + f"1,2025-01-05,{hostile},Books,10,2,C1,France\n"
        + f"2,2025-01-05,{hostile.upper()},Books,10,2,C2,France\n"
    ).encode()
    app = upload(app, content)
    note = "\n".join(m.value for m in app.expander[0].markdown)
    assert "Inconsistent casing" in note
    assert "[click](" not in note
    assert "\\[click\\]\\(" in note
