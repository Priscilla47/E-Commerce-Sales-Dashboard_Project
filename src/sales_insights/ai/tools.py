"""The analytics functions that a language model may ask for, and their safe execution.

A model never calculates and never runs code. It asks for a function of this registry by name,
with arguments, and ``run_tool`` checks both against the schema before calling the analytics
function and returns plain data. Nothing is evaluated: the functions are looked up in a fixed
table, never by a name built from the request.
"""

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import pandas as pd

from sales_insights.ai.llm import ToolCall
from sales_insights.analytics import breakdowns, products, revenue, timeseries

MAX_ROWS = 50  # the longest table given back to a model
MAX_PRODUCT_LENGTH = 100
MAX_N = 50


class ToolError(Exception):
    """A request was refused: unknown function, bad arguments, or an analytics error."""


@dataclass(frozen=True)
class Tool:
    """A function a model may ask for: its name, what it does, its arguments and how to run it."""

    name: str
    description: str
    parameters: Mapping[str, Any]
    run: Callable[[pd.DataFrame, Mapping[str, Any]], Any]


@dataclass(frozen=True)
class ToolResult:
    """What a function returned, as plain JSON-ready data, with the request that made it."""

    name: str
    arguments: Mapping[str, Any]
    data: Mapping[str, Any]


def _schema(properties: Mapping[str, Any] | None = None) -> dict[str, Any]:
    properties = dict(properties or {})
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


_PRODUCT = {
    "product": {
        "type": "string",
        "maxLength": MAX_PRODUCT_LENGTH,
        "description": "The exact name of the product, capital letters included.",
    }
}


def _tools() -> tuple[Tool, ...]:
    return (
        Tool(
            "total_revenue",
            "The total revenue: unit price times quantity, added up over every order.",
            _schema(),
            lambda df, a: revenue.total_revenue(df),
        ),
        Tool(
            "order_count",
            "The number of different orders.",
            _schema(),
            lambda df, a: revenue.order_count(df),
        ),
        Tool(
            "average_order_value",
            "The total revenue divided by the number of orders.",
            _schema(),
            lambda df, a: revenue.average_order_value(df),
        ),
        Tool(
            "unique_customers",
            "The number of different customers who ordered.",
            _schema(),
            lambda df, a: revenue.unique_customers(df),
        ),
        Tool(
            "units_sold",
            "The total number of units sold, all products together.",
            _schema(),
            lambda df, a: revenue.units_sold(df),
        ),
        Tool(
            "unique_products",
            "The names of the products sold, sorted, each once.",
            _schema(),
            lambda df, a: products.unique_products(df),
        ),
        Tool(
            "units_sold_for",
            "The number of units sold of one product (0 if nobody bought it).",
            _schema(_PRODUCT),
            lambda df, a: products.units_sold_for(df, a["product"]),
        ),
        Tool(
            "orders_for",
            "The number of orders of one product.",
            _schema(_PRODUCT),
            lambda df, a: products.orders_for(df, a["product"]),
        ),
        Tool(
            "customers_for",
            "The number of different customers who bought one product.",
            _schema(_PRODUCT),
            lambda df, a: products.customers_for(df, a["product"]),
        ),
        Tool(
            "top_products",
            "The n best-selling products by units sold, best first.",
            _schema(
                {
                    "n": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": MAX_N,
                        "description": "How many products to list.",
                    }
                }
            ),
            lambda df, a: products.top_products(df, a["n"]),
        ),
        Tool(
            "revenue_by",
            "Revenue, number of orders and share of the total revenue for each country or "
            "category, highest revenue first.",
            _schema({"column": {"type": "string", "enum": ["Country", "Category"]}}),
            lambda df, a: breakdowns.revenue_by(df, a["column"]),
        ),
        Tool(
            "revenue_over_time",
            "Revenue and number of orders for each day (D), month (M) or year (Y), in time order.",
            _schema({"freq": {"type": "string", "enum": ["D", "M", "Y"]}}),
            lambda df, a: timeseries.revenue_over_time(df, a["freq"]),
        ),
    )


_TOOLS = {tool.name: tool for tool in _tools()}


def registry() -> tuple[Tool, ...]:
    """Every function a model may ask for."""
    return tuple(_TOOLS.values())


def tool_definitions() -> list[dict[str, Any]]:
    """The registry as the dictionaries (name, description, parameters) a client is given."""
    return [
        {"name": tool.name, "description": tool.description, "parameters": dict(tool.parameters)}
        for tool in _TOOLS.values()
    ]


def _check_arguments(tool: Tool, arguments: object) -> dict[str, Any]:
    if not isinstance(arguments, Mapping):
        raise ToolError("The arguments must be an object of named values")
    properties = tool.parameters["properties"]
    for name in arguments:
        if name not in properties:
            raise ToolError(f"Unknown argument '{name}' for {tool.name}")
    for name in tool.parameters["required"]:
        if name not in arguments:
            raise ToolError(f"Missing argument '{name}' for {tool.name}")
    for name, rule in properties.items():
        value = arguments[name]
        if rule["type"] == "integer":
            if type(value) is not int:  # a boolean or a float is not a whole number here
                raise ToolError(f"Argument '{name}' must be a whole number, not {value!r}")
            if not rule["minimum"] <= value <= rule["maximum"]:
                raise ToolError(
                    f"Argument '{name}' must be from {rule['minimum']} to {rule['maximum']}"
                )
        else:
            if type(value) is not str:
                raise ToolError(f"Argument '{name}' must be text, not {value!r}")
            if "enum" in rule and value not in rule["enum"]:
                raise ToolError(f"Argument '{name}' must be one of {', '.join(rule['enum'])}")
            if len(value) > rule.get("maxLength", len(value)):
                raise ToolError(f"Argument '{name}' is longer than {rule['maxLength']} characters")
    return dict(arguments)


def _plain(value: Any) -> Any:
    """A value of a table as a plain JSON value: no numpy, no NaN, dates as ISO text."""
    if value is None or value is pd.NaT:
        return None
    if isinstance(value, pd.Timestamp):
        return f"{value:%Y-%m-%d}"
    if isinstance(value, bool):
        return bool(value)
    if hasattr(value, "item"):  # a numpy scalar
        value = value.item()
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, int | str):
        return value
    return str(value)


def _data(raw: Any) -> dict[str, Any]:
    if isinstance(raw, pd.DataFrame):
        total = len(raw)
        rows = [
            {str(column): _plain(value) for column, value in row.items()}
            for _, row in raw.head(MAX_ROWS).iterrows()
        ]
        return _cut({"rows": rows}, total)
    if isinstance(raw, list):
        return _cut({"values": [_plain(item) for item in raw[:MAX_ROWS]]}, len(raw))
    return {"value": _plain(raw)}


def _cut(data: dict[str, Any], total: int) -> dict[str, Any]:
    data["truncated"] = total > MAX_ROWS
    if data["truncated"]:
        data["total_rows"] = total
    return data


def run_tool(call: ToolCall, orders: pd.DataFrame) -> ToolResult:
    """Check a request of a model and run the function it asks for.

    Raises:
        ToolError: the function is not in the registry, an argument is missing, unknown or of the
            wrong type or range, or the analytics function refused the request.
    """
    tool = _TOOLS.get(call.name) if isinstance(call.name, str) else None
    if tool is None:
        raise ToolError(f"Unknown function {call.name!r}")
    arguments = _check_arguments(tool, call.arguments)
    try:
        raw = tool.run(orders, arguments)
    except ValueError as error:
        raise ToolError(str(error)) from error
    return ToolResult(tool.name, arguments, _data(raw))
