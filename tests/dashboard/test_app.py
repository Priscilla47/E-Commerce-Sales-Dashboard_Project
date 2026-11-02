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
