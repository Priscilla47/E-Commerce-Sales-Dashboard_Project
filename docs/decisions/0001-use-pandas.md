# 1. Use pandas for the analytics

## Status

Accepted. pandas has been used since the first version of the tool; this record explains why it stays.

## Context

The project reads a CSV file of e-commerce orders and answers questions about it: totals, rankings, breakdowns by country or category, revenue over time. The data is a table with typed columns (dates, whole numbers, prices, text), and the questions are grouping, summing, sorting and resampling.

The sample dataset has 500 orders. Real files of a small shop are expected to have from thousands to a few million lines, which fits in the memory of a laptop. The same analytics must serve a command line today and a dashboard and an AI layer later, so the choice shapes the whole `analytics` package (see [Architecture](../architecture.md)).

What matters most: correct results that can be checked by hand, short code that a student can read, and tools for dates and time series, which the forecasting feature will need.

## Options

### Pure Python (lists, dictionaries, the `csv` module)

No dependency. This is how the first version of the tool counted products, with loops over rows. It worked, but it also hid two bugs for months (the first product was never ranked and tied products were listed twice), because every grouping was written by hand. Dates, missing values and resampling by month would all have to be written and tested by us. **Ruled out**: too much code of our own to get wrong, for no gain at this size.

### pandas (chosen)

A table type (`DataFrame`) with typed columns, `groupby`, `resample`, missing-value handling and CSV reading. It is the tool most people who work with tabular data in Python already know, it is well documented, and Streamlit, the planned dashboard library, draws pandas tables and charts directly (see [decision 2](0002-use-streamlit.md)). **Chosen.**

### polars

A fast, newer table library, with a strict type system and lazy evaluation that can work on files larger than memory. Its speed advantage matters for data far larger than ours. It is less widely known, its Streamlit and forecasting-library support goes through conversion to pandas in places, and nothing in this project is slow today (a million-line table is summed or grouped in well under a second). **Ruled out for now**, not for ever: see the consequences.

### SQL with DuckDB (or SQLite)

Load the file into a database and write the questions as SQL queries. DuckDB reads CSV directly and handles data larger than memory. It would put the calculations in strings of SQL, which are harder to test with small hand-made tables and to compose in Python, and the time-series and forecasting steps would need the data back in Python anyway. **Ruled out**: it adds a second language for no problem we have.

## Decision

Use pandas, version 2.0 or newer, for loading, validation and every calculation of the `analytics` package. Functions take a pandas table and return a number or a table; nothing else of pandas leaks into the interfaces. The code is tested on pandas 2.0, 2.2 and 3.1, so the whole range works.

## Consequences

- Analytics functions are short and are tested on small tables whose results can be checked by hand.
- The whole table is in memory. That is fine for the expected files, and the loader reads everything as text first so that bad values give clear errors.
- Behavior that changes between pandas versions has already caused work (grouping on category columns, time zones, the default text type in pandas 3). The test suite runs on several versions to catch that, and any new use of a changing feature should be tested on all of them.
- Because the interfaces only receive plain numbers and tables, replacing pandas later would touch `data` and `analytics` and leave `cli` and `dashboard` almost unchanged.

**When we would revisit it.** If real files no longer fit in memory, or a measured calculation becomes too slow on files we need to support, we would first try polars or DuckDB behind the same functions, since the interfaces do not depend on the table type. We would also revisit it if pandas stops being maintained or its direction conflicts with the dashboard or forecasting libraries we choose.
