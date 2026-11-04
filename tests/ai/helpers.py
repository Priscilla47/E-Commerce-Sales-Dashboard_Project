"""Small tables shared by the tests of the ai package."""

import pandas as pd


def monthly_orders(values, start="2023-01", country="France", category="Books", product="Book"):
    """One order a month, on the last day of the month, with the given revenue."""
    months = pd.period_range(start, periods=len(values), freq="M")
    return pd.DataFrame(
        {
            "OrderID": range(1, len(values) + 1),
            "Date": [m.to_timestamp(how="end").normalize() for m in months],
            "Product": product,
            "Quantity": 1,
            "Country": country,
            "Category": category,
            "Revenue": [float(v) for v in values],
        }
    )


SPIKE = [100.0] * 7 + [1000.0]  # eight months, one spike
