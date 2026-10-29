"""The dashboard. Start it with ``streamlit run src/sales_insights/dashboard/app.py``.

The page only asks the user for a data source and draws what ``analytics`` returns; it holds
no calculation of its own.
"""

import streamlit as st

from sales_insights.analytics.revenue import order_count
from sales_insights.dashboard.data_source import (
    SAMPLE_PATH,
    LoadedData,
    load_from_bytes,
    load_from_path,
    sample_is_available,
)
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


def main() -> None:
    st.set_page_config(page_title="Sales insights", layout="wide")
    st.title("Sales insights")
    loaded = _choose_data()
    if loaded is None:
        st.stop()
    orders = order_count(loaded.orders)
    st.caption(f"{orders} {'order' if orders == 1 else 'orders'} loaded")


main()
