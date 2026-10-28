# 2. Use Streamlit for the dashboard

## Status

Accepted. The dashboard is not built yet: the `dashboard` package exists and is empty, and Streamlit is not a dependency of the project until it is.

## Context

The project should offer an interactive dashboard next to the command line: revenue and best sellers at a glance, breakdowns by country and category, a revenue curve over time, and later questions in plain language, written insights and a forecast. It is built by one person who works mostly in Python, with a few weeks for the first version, and it must be easy to run and to put in a Docker image (the choice of a cloud provider is open).

The dashboard is a thin interface over the `analytics` package: it loads a file, calls analytics functions and draws the result, with no calculation of its own (see [Architecture](../architecture.md)). The framework therefore only has to draw tables, charts and a few controls, and to run the Python code that already exists.

## Options

### Streamlit (chosen)

Pages are plain Python scripts that call `st.dataframe`, `st.line_chart`, `st.selectbox` and so on; the script re-runs on each interaction. It draws pandas tables and charts directly, includes a file uploader and a chat interface (useful for the question-and-answer feature), starts with one command and needs no JavaScript. **Chosen.**

### Dash (Plotly)

Callback-based, with fine control over the layout and the charts. More powerful for complex interactions, but each interaction is a hand-written callback between components, which is more code and more concepts than this dashboard needs. **Ruled out**: the extra control is not needed and costs time we do not have.

### A FastAPI back end with a JavaScript front end

The most flexible and the most separable: an API that other clients could use, and a front end with any look. It also means two code bases, two languages, a build step for the front end, and an API contract to design and test, to display a handful of charts. **Ruled out**: far more work than the first version needs. If an API is wanted later, the analytics functions can be put behind one without changing them.

### A notebook (Jupyter)

Quickest to write and good for exploring the data. It is not an application: it is awkward to give to a non-programmer, to deploy and to test, and its state depends on the order in which cells were run. **Ruled out** for the dashboard. A notebook remains a good way to explore the analytics functions on the side.

## Decision

Build the dashboard with Streamlit, in the `dashboard` package, as a thin layer over the `analytics` package. Add Streamlit as a dependency, probably as an optional one such as `pip install -e ".[dashboard]"`, when the dashboard is started, so that the command line stays light to install.

## Consequences

- A first version can be written quickly, and a user can open it with one command or one container.
- The script is re-run on every interaction, so expensive steps (reading the file, a forecast) must be cached with Streamlit's caching, and the code must not keep state in module variables.
- Layout control is limited compared with Dash or a custom front end. That is accepted for a first version.
- The `dashboard` package must not import `cli`, and `analytics` must not import `dashboard`; the architecture tests enforce the second rule.
- Streamlit is a runtime dependency of the dashboard only; the tests of the analytics do not need it.

**When we would revisit it.** If the dashboard needs layouts or interactions that Streamlit cannot do, if several users need to be served with their own sessions and the re-run model becomes too slow, or if another program needs the figures through an API, we would put a FastAPI layer over the analytics functions and keep or replace the Streamlit front end. Because the dashboard has no calculation of its own, that change would not touch the analytics.
