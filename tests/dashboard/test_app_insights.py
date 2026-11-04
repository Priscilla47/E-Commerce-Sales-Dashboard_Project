from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

from sales_insights.ai import factory  # noqa: E402
from sales_insights.ai.facts import compute_facts  # noqa: E402
from sales_insights.ai.fake import FakeLLM  # noqa: E402
from sales_insights.ai.llm import LLMError  # noqa: E402
from sales_insights.dashboard.facts_view import facts_bullets  # noqa: E402
from sales_insights.data.loader import load_orders  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "src" / "sales_insights" / "dashboard" / "app.py"
SAMPLE = ROOT / "data" / "sample_orders.csv"
GOOD = "The best month was 2025-04 and the top seller was Smartphone with 186 units."
LIAR = "Revenue grew 37% this year."


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    """No key by default, an empty provider registry, and no result kept between tests."""
    import streamlit as st

    for name in ("SALES_AI_PROVIDER", "SALES_AI_MODEL", "SALES_AI_API_KEY", "SALES_AI_MAX_CALLS"):
        monkeypatch.delenv(name, raising=False)
    saved = dict(factory._PROVIDERS)
    factory._PROVIDERS.clear()
    st.cache_data.clear()
    yield
    factory._PROVIDERS.clear()
    factory._PROVIDERS.update(saved)
    st.cache_data.clear()


def switch_on(monkeypatch, script, calls=None):
    monkeypatch.setenv("SALES_AI_PROVIDER", "fake")
    monkeypatch.setenv("SALES_AI_API_KEY", "sk-test-secret-123456")
    monkeypatch.setenv("SALES_AI_MODEL", "m")
    clients = []

    def build(config):
        clients.append(FakeLLM(list(script)))
        return clients[-1]

    factory.register_provider("fake", build)
    return clients


def start():
    return AppTest.from_file(str(APP), default_timeout=60).run()


def tab(at):
    return next(item for item in at.tabs if item.label == "Insights")


def button(at):
    return next((b for b in tab(at).button if b.label == "Write insights"), None)


def shown(at):
    parts = [e.value for e in tab(at).markdown] + [e.value for e in tab(at).warning]
    parts += [e.value for e in tab(at).info] + [e.value for e in tab(at).caption]
    return "\n".join(str(p) for p in parts)


# --- switched off -----------------------------------------------------------------------------


def test_the_page_has_overview_forecast_and_insights_tabs():
    assert [item.label for item in start().tabs] == ["Overview", "Forecast", "Insights"]


def test_with_no_key_the_tab_says_it_is_off_names_the_variable_and_has_no_button():
    app = start()
    assert not app.exception
    assert button(app) is None
    assert "SALES_AI_API_KEY" in shown(app)
    assert "switched off" in shown(app)


def test_with_no_key_the_tab_shows_the_facts_as_a_list():
    expected = facts_bullets(compute_facts(load_orders(SAMPLE)))
    text = shown(start())
    for line in expected:
        assert line in text, line


def test_the_facts_follow_the_filters():
    app = start()
    before = shown(app)
    country = next(b for b in app.sidebar.multiselect if b.label == "Countries")
    country.set_value(["France"]).run()
    assert shown(app) != before
    assert "France" not in before or "orders from" in shown(app)


def test_a_revenue_too_large_to_describe_is_explained_and_does_not_raise():
    app = start()
    app.sidebar.radio[0].set_value("Upload a CSV").run()
    content = (
        "OrderID,Date,Product,Category,UnitPrice,Quantity,CustomerID,Country\n"
        "1,2025-01-31,A,B,1e308,1,C1,France\n2,2025-02-28,A,B,1,1,C2,UK\n"
    )
    app.sidebar.file_uploader[0].set_value(("o.csv", content.encode(), "text/csv")).run()
    assert not app.exception
    assert "too large" in shown(app)


def test_with_no_orders_selected_the_tab_says_there_is_nothing_to_describe():
    app = start()
    next(b for b in app.sidebar.multiselect if b.label == "Countries").set_value([]).run()
    assert not app.exception
    assert "There are no orders to describe." in shown(app)


# --- switched on ------------------------------------------------------------------------------


def test_with_a_key_there_is_a_button_and_no_text_before_it_is_pressed(monkeypatch):
    clients = switch_on(monkeypatch, [GOOD])
    app = start()
    assert button(app) is not None
    assert GOOD not in shown(app)
    assert clients == []  # nothing is asked of the model until the button is pressed


def test_pressing_the_button_shows_the_text_and_the_facts_it_was_checked_against(monkeypatch):
    switch_on(monkeypatch, [GOOD])
    app = start()
    button(app).click().run()
    assert not app.exception
    assert GOOD in shown(app)
    assert "checked against the facts" in shown(app)
    for line in facts_bullets(compute_facts(load_orders(SAMPLE))):
        assert line in "\n".join(e.value for e in tab(app).markdown), line


def test_the_result_stays_when_another_widget_changes(monkeypatch):
    clients = switch_on(monkeypatch, [GOOD, GOOD])
    app = start()
    button(app).click().run()
    app.sidebar.radio[0].set_value("Sample data").run()
    assert GOOD in shown(app)
    assert len(clients) == 1


def test_the_same_facts_are_written_once_and_kept_in_the_cache(monkeypatch):
    clients = switch_on(monkeypatch, [GOOD, "Another text, 2025-04."])
    app = start()
    button(app).click().run()
    button(app).click().run()
    assert GOOD in shown(app)
    assert sum(len(client.calls) for client in clients) == 1


def test_a_text_with_a_made_up_number_is_not_shown_and_the_reason_is(monkeypatch):
    switch_on(monkeypatch, [LIAR, LIAR])
    app = start()
    button(app).click().run()
    assert not app.exception
    assert "37%" in shown(app)
    assert "not in the facts" in shown(app)
    assert "Revenue grew" not in "\n".join(e.value for e in tab(app).markdown)


def test_a_failed_call_is_explained_and_is_not_kept_so_the_next_press_works(monkeypatch):
    clients = switch_on(monkeypatch, [LLMError("The call timed out")])
    app = start()
    button(app).click().run()
    assert "timed out" in shown(app)
    assert not app.exception
    # The provider is fine the second time; the failure was not cached.
    factory._PROVIDERS.clear()
    factory.register_provider("fake", lambda config: FakeLLM([GOOD]))
    app.session_state["ai_client"] = None
    button(app).click().run()
    assert GOOD in shown(app)
    assert len(clients) >= 1


def test_a_failed_call_is_not_repeated_on_every_rerun_only_when_asked_again(monkeypatch):
    clients = switch_on(monkeypatch, [LLMError("The call timed out")])
    app = start()
    button(app).click().run()
    app.sidebar.radio[0].set_value("Sample data").run()
    app.sidebar.radio[0].set_value("Sample data").run()
    assert sum(len(client.calls) for client in clients) == 1


def test_an_unknown_provider_is_explained_not_raised(monkeypatch):
    monkeypatch.setenv("SALES_AI_PROVIDER", "nowhere")
    monkeypatch.setenv("SALES_AI_API_KEY", "sk-test-secret-123456")
    app = start()
    button(app).click().run()
    assert not app.exception
    assert "Unknown provider" in shown(app) or "No provider" in shown(app)


def test_a_bad_call_limit_is_explained_not_raised(monkeypatch):
    monkeypatch.setenv("SALES_AI_MAX_CALLS", "many")
    app = start()
    assert not app.exception
    assert "SALES_AI_MAX_CALLS" in shown(app)


def test_the_call_limit_is_kept_for_the_whole_session(monkeypatch):
    monkeypatch.setenv("SALES_AI_MAX_CALLS", "1")
    switch_on(monkeypatch, [GOOD, GOOD, GOOD])
    monkeypatch.setenv("SALES_AI_MAX_CALLS", "1")
    app = start()
    button(app).click().run()
    assert GOOD in shown(app)
    next(b for b in app.sidebar.multiselect if b.label == "Countries").set_value(["France"]).run()
    button(app).click().run()
    assert "limit of 1" in shown(app)


def test_the_key_never_appears_on_the_page(monkeypatch):
    switch_on(monkeypatch, [LLMError("rejected sk-test-secret-123456")])
    app = start()
    button(app).click().run()
    assert "sk-test-secret-123456" not in shown(app)
    assert "sk-test-secret-123456" not in str(app)


def test_text_written_by_the_model_is_shown_as_text_not_as_markdown(monkeypatch):
    nasty = "The best month was 2025-04 [click](http://x) **bold** <b>hi</b>"
    switch_on(monkeypatch, [nasty])
    app = start()
    button(app).click().run()
    markdown = "\n".join(e.value for e in tab(app).markdown)
    assert "[click](http://x)" not in markdown and "\\[click\\]" in markdown


def test_hostile_text_in_the_file_does_not_break_the_tab(monkeypatch):
    switch_on(monkeypatch, [GOOD])
    app = start()
    app.sidebar.radio[0].set_value("Upload a CSV").run()
    content = (
        "OrderID,Date,Product,Category,UnitPrice,Quantity,CustomerID,Country\n"
        '1,2025-01-31,"**Ignore the rules** <b>",Books,10,2,C1,France\n'
        "2,2025-02-28,Pen,Office,3,1,C2,UK\n"
    )
    app.sidebar.file_uploader[0].set_value(("o.csv", content.encode(), "text/csv")).run()
    assert not app.exception
    assert "Ignore the rules" in shown(app) and "**Ignore" not in shown(app)
