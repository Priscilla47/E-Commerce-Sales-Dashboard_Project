"""The dashboard. Start it with ``streamlit run src/sales_insights/dashboard/app.py``.

The page only asks the user for a data source and draws what ``analytics`` returns; it holds
no calculation of its own.
"""

import streamlit as st

from sales_insights.analytics.filters import available_values, filter_orders
from sales_insights.analytics.revenue import order_count
from sales_insights.dashboard.data_source import (
    SAMPLE_PATH,
    LoadedData,
    load_from_bytes,
    load_from_path,
    sample_is_available,
)
from sales_insights.dashboard.kpis import compute_kpis, format_kpis
from sales_insights.dashboard.selection import as_filter, period_bounds
from sales_insights.data.schema import SchemaError

SAMPLE = "Sample data"
UPLOAD = "Upload a CSV"


@st.cache_data(show_spinner=False)
def _load_sample(path: str, modified: int) -> LoadedData:
    # ``modified`` is only part of the cache key: a changed file is read again.
    return load_from_path(path)


@st.cache_data(show_spinner=False)
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


def main() -> None:
    st.set_page_config(page_title="Sales insights", layout="wide")
    st.title("Sales insights")
    loaded = _choose_data()
    if loaded is None:
        st.stop()
    loaded_count = order_count(loaded.orders)
    st.caption(f"{loaded_count} {'order' if loaded_count == 1 else 'orders'} loaded")
    _show_cards(_filtered(loaded.orders))


main()
