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
