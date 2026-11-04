"""The dashboard. Start it with ``streamlit run src/sales_insights/dashboard/app.py``.

The page only asks the user for a data source and draws what ``analytics`` returns; it holds
no calculation of its own.
"""

import json
import os
import re

import pandas as pd
import streamlit as st

from sales_insights.ai.config import ConfigError, load_config
from sales_insights.ai.factory import AIDisabled, build_client
from sales_insights.ai.facts import Facts, compute_facts
from sales_insights.ai.forecast import forecast_with_error
from sales_insights.ai.insights import Insights, write_insights
from sales_insights.ai.llm import LLMError
from sales_insights.analytics.filters import available_values, filter_orders
from sales_insights.analytics.products import unique_products
from sales_insights.analytics.revenue import order_count
from sales_insights.dashboard.charts import (
    NOTHING_TO_DRAW,
    forecast_chart,
    revenue_by_chart,
    revenue_over_time_chart,
    top_products_chart,
)
from sales_insights.dashboard.data_source import (
    SAMPLE_PATH,
    LoadedData,
    count_problems,
    describe_problems,
    load_from_bytes,
    load_from_path,
    sample_is_available,
)
from sales_insights.dashboard.facts_view import facts_bullets
from sales_insights.dashboard.forecast_view import format_forecast
from sales_insights.dashboard.kpis import compute_kpis, format_kpis
from sales_insights.dashboard.selection import as_filter, period_bounds
from sales_insights.data.schema import SchemaError
from sales_insights.data.validation import WARNING, ValidationReport

SAMPLE = "Sample data"
UPLOAD = "Upload a CSV"


@st.cache_data(show_spinner=False, max_entries=2)
def _load_sample(path: str, modified: int) -> LoadedData:
    # ``modified`` is only part of the cache key: a changed file is read again.
    return load_from_path(path)


@st.cache_data(show_spinner=False, max_entries=2)
def _load_upload(content: bytes) -> LoadedData:
    return load_from_bytes(content)


def _choose_data() -> LoadedData | None:
    """Ask for the data source in the sidebar and load it; None when there is nothing yet."""
    source = st.sidebar.radio("Data source", [SAMPLE, UPLOAD])
    try:
        if source == SAMPLE:
            if not sample_is_available():
                st.error(f"The sample file was not found at {SAMPLE_PATH}")
                return None
            return _load_sample(str(SAMPLE_PATH), SAMPLE_PATH.stat().st_mtime_ns)
        upload = st.sidebar.file_uploader("Orders file", type="csv")
        if upload is None:
            st.info("Upload a CSV file of orders in the sidebar to start.")
            return None
        return _load_upload(upload.getvalue())
    except SchemaError as error:
        st.error(str(error))
        return None


def _plain(text: str) -> str:
    """Escape the characters of ``text`` that Markdown would interpret (it comes from a file)."""
    return re.sub(r"([\\`*_\[\]()<>#|~$])", r"\\\1", text)


def _bullets(lines: list[str]) -> str:
    return "\n".join(f"- {_plain(line)}" for line in lines)


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _show_findings(report: ValidationReport) -> None:
    """Say what the validation found: errors in a warning box, warnings in a collapsed note."""
    if report.errors:
        count = _plural(count_problems(report), "error")
        st.warning(
            f"{count} found in the data, so some figures may be unreliable "
            f"(the lines below are line numbers of the file):\n\n"
            f"{_bullets(describe_problems(report))}"
        )
    if report.warnings:
        count = _plural(count_problems(report, severity=WARNING), "warning")
        with st.expander(f"{count} about the data"):
            st.markdown(_bullets(describe_problems(report, severity=WARNING)))


def _filtered(orders):
    """Show the filters in the sidebar and return the orders that match them."""
    st.sidebar.header("Filters")
    start = end = None
    bounds = period_bounds(orders)
    if bounds is not None:
        picked = st.sidebar.date_input(
            "Period", value=bounds, min_value=bounds[0], max_value=bounds[1]
        )
        # While the user is choosing, only the first day is known.
        start = picked[0] if len(picked) > 0 else None
        end = picked[1] if len(picked) > 1 else None
    countries = available_values(orders, "Country")
    categories = available_values(orders, "Category")
    chosen_countries = st.sidebar.multiselect("Countries", countries, default=countries)
    chosen_categories = st.sidebar.multiselect("Categories", categories, default=categories)
    return filter_orders(
        orders,
        start=start,
        end=end,
        countries=as_filter(chosen_countries, countries),
        categories=as_filter(chosen_categories, categories),
    )


def _show_cards(orders) -> None:
    labels = format_kpis(compute_kpis(orders))
    columns = st.columns(4)
    columns[0].metric("Revenue", labels.revenue)
    columns[1].metric("Orders", labels.orders)
    columns[2].metric("Average order value", labels.average_order_value)
    columns[3].metric("Customers", labels.customers)


TIME_SCALES = {"Day": "D", "Month": "M"}
DEFAULT_PRODUCTS = 5


def _draw(figure) -> None:
    """Draw a figure, or say there is nothing to draw (the cards stay on screen)."""
    if figure is None:
        st.info(NOTHING_TO_DRAW)
    else:
        st.plotly_chart(figure, width="stretch")


def _show_charts(orders) -> None:
    """Draw the three charts, each with the one control that changes it."""
    scale = st.radio("Revenue over time, by", list(TIME_SCALES), index=1, horizontal=True)
    _draw(revenue_over_time_chart(orders, TIME_SCALES[scale]))

    left, right = st.columns(2)
    with left:
        column = st.selectbox("Break the revenue down by", ["Country", "Category"])
        _draw(revenue_by_chart(orders, column))
    with right:
        products = len(unique_products(orders))
        shown = products
        if products > 1:
            shown = st.slider("Number of products", 1, products, min(DEFAULT_PRODUCTS, products))
        _draw(top_products_chart(orders, shown))


MONTHS = list(range(1, 13))


def _show_forecast(orders) -> None:
    """The forecast tab: a number of months, the chart, the error and what to keep in mind."""
    months = st.selectbox("Months to forecast", MONTHS, index=2)
    try:
        report = forecast_with_error(orders, months)
    except ValueError as error:  # not enough months of history
        st.info(str(error))
        return
    labels = format_forecast(report)
    st.caption(
        f"This is an estimate, not a promise. It was made with the {labels.method} method "
        f"from {report.forecast.history_months} complete months of history."
    )
    if labels.warnings:
        st.warning(_bullets(labels.warnings))
    _draw(forecast_chart(report.history, report.forecast.table))
    if labels.mae is None:
        st.info(labels.note)
    else:
        st.caption(
            f"Error of the {labels.method} method on {labels.holdout}, "
            "trained on the months before them. MAE is in the unit of the revenue; "
            "MAPE is the same error in percent."
        )
        columns = st.columns(4)
        columns[0].metric("MAE", labels.mae)
        columns[1].metric("MAPE", labels.mape)
        columns[2].metric("Baseline MAE", labels.baseline_mae)
        columns[3].metric("Baseline MAPE", labels.baseline_mape)
    table = pd.DataFrame(labels.rows, columns=["Month", "Forecast", "Lower", "Upper"])
    st.dataframe(table, hide_index=True)


class _ModelUnavailable(Exception):
    """The model could not be reached: raised so that the failure is not kept in the cache."""


@st.cache_data(show_spinner="Writing the insights...", max_entries=4)
def _write(facts: Facts, settings: str, _client) -> Insights:
    # ``settings`` is only part of the cache key: other settings write the text again.
    result = write_insights(facts, _client)
    if result.error:
        raise _ModelUnavailable(result.reason)
    return result


def _session_client(config):
    """One client for the whole session, so that the limit of calls holds across reruns."""
    settings = (config.provider, config.model, config.max_calls)
    if st.session_state.get("ai_client") is None or st.session_state.get("ai_settings") != settings:
        st.session_state["ai_client"] = None
        st.session_state["ai_client"] = build_client(config)
        st.session_state["ai_settings"] = settings
    return st.session_state["ai_client"]


def _facts_list(facts: Facts) -> str:
    return "\n".join(f"- {line}" for line in facts_bullets(facts))


def _show_insights(orders) -> None:
    """The Insights tab: the facts, and a button to have them written and checked."""
    try:
        facts = compute_facts(orders)
    except ValueError as error:  # a revenue too large to compute with
        st.info(str(error))
        return
    if facts.orders == 0:
        st.markdown(_facts_list(facts))
        return
    try:
        config = load_config(os.environ)
        if not config.enabled:
            build_client(config)  # raises AIDisabled with the variable to set
    except ConfigError as error:
        st.warning(str(error))
        st.markdown(_facts_list(facts))
        return
    except AIDisabled as error:
        st.info(f"{error} These are the facts the text would be written from.")
        st.markdown(_facts_list(facts))
        return

    facts_json = json.dumps(facts.as_dict(), sort_keys=True)
    if st.button("Write insights"):
        st.session_state["insights_for"] = facts_json
    if st.session_state.get("insights_for") != facts_json:
        st.caption(
            "The text is written by a language model from the facts below only, and every number "
            "in it is checked against them."
        )
        st.markdown(_facts_list(facts))
        return
    settings = f"{config.provider}|{config.model}|{config.max_calls}"
    try:
        result = _write(facts, settings, _session_client(config))
    except (LLMError, _ModelUnavailable) as error:
        st.session_state.pop("insights_for", None)  # a failure is tried again only when asked
        st.warning(str(error))
        st.markdown(_facts_list(facts))
        return
    if result.grounded:
        st.markdown(_plain(result.text))
        st.caption("Every number in this text was checked against the facts below.")
    else:
        st.warning(f"No text was written: {result.reason}")
    with st.expander("The facts behind the text", expanded=not result.grounded):
        st.markdown(_facts_list(facts))


def main() -> None:
    st.set_page_config(page_title="Sales insights", layout="wide")
    st.title("Sales insights")
    loaded = _choose_data()
    if loaded is None:
        st.stop()
    loaded_count = order_count(loaded.orders)
    st.caption(f"{loaded_count} {'order' if loaded_count == 1 else 'orders'} loaded")
    _show_findings(loaded.report)
    orders = _filtered(loaded.orders)
    _show_cards(orders)
    overview, forecast, insights = st.tabs(["Overview", "Forecast", "Insights"])
    with overview:
        _show_charts(orders)
    with forecast:
        _show_forecast(orders)
    with insights:
        _show_insights(orders)


main()
