"""Figures about the products of a loaded orders table.

Pure functions on a table as returned by ``load_orders``. A product is matched by its exact
name (the match is case-sensitive). Missing cells are skipped: a line without a quantity adds
no units, and a line without a customer is not counted as a customer.
"""

import pandas as pd


def unique_products(df: pd.DataFrame) -> list[str]:
    """The names of the products that occur in the table, each once, sorted."""
    return sorted(str(name) for name in df["Product"].dropna().unique())


def units_sold_for(df: pd.DataFrame, product: str) -> int:
    """The total quantity ordered of ``product``; 0 for a product nobody bought."""
    return int(df.loc[df["Product"] == product, "Quantity"].sum())


def orders_for(df: pd.DataFrame, product: str) -> int:
    """The number of order lines of ``product``. A repeat customer is counted every time."""
    return int((df["Product"] == product).sum())


def customers_for(df: pd.DataFrame, product: str) -> int:
    """The number of different customers who bought ``product``."""
    return int(df.loc[df["Product"] == product, "CustomerID"].nunique())


def top_products(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """The ``n`` best-selling products, by total quantity.

    The result has the columns ``[Product, units]``, with the highest total first and products
    that sold the same quantity ordered by name.

    Raises:
        TypeError: ``n`` is not a whole number.
        ValueError: ``n`` is negative or larger than the number of products.
    """
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError(f"n must be a whole number, not {n!r}")

    # observed=True: with a category column, keep only the products that really occur.
    units = df.groupby("Product", observed=True)["Quantity"].sum()
    if n < 0 or n > len(units):
        raise ValueError("Wrong number of products")

    top = units.sort_values(ascending=False, kind="stable").head(n)
    return pd.DataFrame({"Product": list(top.index), "units": top.to_numpy("int64")})
