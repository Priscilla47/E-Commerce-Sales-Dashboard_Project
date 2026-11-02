"""Revenue forecasting: a statistical model with its error, no language model needed.

The monthly revenue comes from ``analytics``. Two methods are offered: ``naive`` (the same month of
the previous year, or the last value when there is less than a year of history) and
``holt_winters`` (additive trend and yearly seasons, fitted by a small grid search). Every forecast
is returned with an interval and ``evaluate`` measures the error of the method on the last months,
against the naive baseline. Nothing here rounds a value, reads a file or prints.
"""

import math
import operator
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from sales_insights.analytics.timeseries import revenue_over_time

METHODS = ("naive", "holt_winters")
MIN_MONTHS = 3  # the least history a forecast needs
SEASON = 12  # months in a season
MIN_MONTHS_HOLT_WINTERS = 24  # two seasons
MAX_HORIZON = 12
Z = 1.96  # half-width of a 95% interval, in standard deviations of the errors

_ALPHAS = (0.05, 0.1, 0.2, 0.3, 0.5, 0.7)
_BETAS = (0.0, 0.01, 0.05, 0.1, 0.2)
_GAMMAS = (0.0, 0.1, 0.3, 0.5, 0.7)


@dataclass(frozen=True)
class Forecast:
    """The forecast of the next months.

    ``table`` has the columns ``period`` (first day of the month), ``forecast``, ``lower`` and
    ``upper`` (a 95% interval); ``method_used`` is the method that produced it, and ``fell_back``
    is True when it is not the one asked for. ``history_months`` counts the months it learned from.
    """

    table: pd.DataFrame
    method_used: str
    fell_back: bool
    history_months: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class Metrics:
    """The mean absolute error, and the mean absolute percentage error in percent (or None)."""

    mae: float
    mape: float | None


@dataclass(frozen=True)
class Evaluation:
    """How well a method forecast the last ``holdout`` months, and how well the baseline did."""

    method_used: str
    holdout: int
    history_months: int
    model: Metrics
    baseline: Metrics
    warnings: tuple[str, ...]


def mean_absolute_error(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """The mean of ``|actual - predicted|``.

    Raises:
        ValueError: the inputs are empty or have different lengths.
    """
    a, p = _pair(actual, predicted)
    return float(np.mean(np.abs(a - p)))


def mean_absolute_percentage_error(
    actual: Sequence[float], predicted: Sequence[float]
) -> float | None:
    """The mean of ``|actual - predicted| / |actual|``, in percent; None if an actual is 0.

    Raises:
        ValueError: the inputs are empty or have different lengths.
    """
    a, p = _pair(actual, predicted)
    if np.any(a == 0):
        return None
    return float(np.mean(np.abs(a - p) / np.abs(a)) * 100)


def _pair(actual: Sequence[float], predicted: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    a = np.asarray(actual, dtype="float64")
    p = np.asarray(predicted, dtype="float64")
    if a.size == 0 or a.shape != p.shape:
        raise ValueError("The actual and predicted values must be non-empty and of the same length")
    return a, p


def _whole(value: object, name: str) -> int:
    try:
        if isinstance(value, bool | np.bool_):
            raise TypeError
        return operator.index(value)  # type: ignore[arg-type]
    except TypeError:
        raise TypeError(f"{name} must be a whole number, not {value!r}") from None


def _check_range(value: int, name: str) -> int:
    if not 1 <= value <= MAX_HORIZON:
        raise ValueError(f"{name} must be from 1 to {MAX_HORIZON}, not {value}")
    return value


def _check_method(method: str) -> None:
    if method not in METHODS:
        raise ValueError(f"method must be one of {', '.join(METHODS)}, not {method!r}")


def _monthly(df: pd.DataFrame) -> tuple[pd.DatetimeIndex, np.ndarray, list[str]]:
    """The revenue of each complete month, and what was left out.

    A month counts when the data reaches its last day; a last month that stops earlier is left
    out, because its small revenue would be read as a fall.
    """
    series = revenue_over_time(df, "M")
    warnings: list[str] = []
    if not series.empty:
        last = df["Date"].dropna().max()
        if last.day < last.days_in_month:
            series = series.iloc[:-1]
            warnings.append(
                f"The last month ({last:%Y-%m}) was left out because the data stops on day "
                f"{last.day} of {last.days_in_month}."
            )
    return pd.DatetimeIndex(series["period"]), series["revenue"].to_numpy("float64"), warnings


def _need_history(count: int, what: str = "history") -> None:
    if count < MIN_MONTHS:
        raise ValueError(
            f"The forecast needs at least {MIN_MONTHS} months of {what}, found {count}"
        )


def _rms(values: np.ndarray) -> float:
    return float(math.sqrt(np.mean(values**2))) if values.size else 0.0


def _naive(values: np.ndarray, months: int) -> tuple[np.ndarray, np.ndarray]:
    """Forecast and half-width of the interval of the naive method."""
    count = len(values)
    steps = np.arange(months)
    if count >= SEASON:
        forecast = values[count - SEASON + steps % SEASON]
        sigma = _rms(values[SEASON:] - values[:-SEASON])
        reach = steps // SEASON + 1
    else:
        forecast = np.full(months, values[-1])
        sigma = _rms(np.diff(values))
        reach = steps + 1
    return forecast, Z * sigma * np.sqrt(reach)


def _holt_winters_run(y: np.ndarray, alpha: float, beta: float, gamma: float):
    mean = y[:SEASON].mean()
    trend = (y[SEASON : 2 * SEASON].mean() - mean) / SEASON
    offsets = np.arange(SEASON) - (SEASON - 1) / 2
    season = list(y[:SEASON] - (mean + trend * offsets))
    level = mean + trend * (-1 - (SEASON - 1) / 2)
    errors = np.empty(len(y))
    for t, actual in enumerate(y):
        phase = t % SEASON
        known = season[phase]
        errors[t] = actual - (level + trend + known)
        new_level = alpha * (actual - known) + (1 - alpha) * (level + trend)
        trend = beta * (new_level - level) + (1 - beta) * trend
        season[phase] = gamma * (actual - new_level) + (1 - gamma) * known
        level = new_level
    return errors[SEASON:], level, trend, season


def _holt_winters(values: np.ndarray, months: int) -> tuple[np.ndarray, np.ndarray]:
    best = None
    for alpha in _ALPHAS:
        for beta in _BETAS:
            for gamma in _GAMMAS:
                errors, level, trend, season = _holt_winters_run(values, alpha, beta, gamma)
                sse = float(np.sum(errors**2))
                if best is None or sse < best[0] - 1e-12:
                    best = (sse, errors, level, trend, season)
    _, errors, level, trend, season = best
    count = len(values)
    ahead = np.arange(1, months + 1)
    phases = (count + ahead - 1) % SEASON
    forecast = level + ahead * trend + np.array(season)[phases]
    return forecast, Z * _rms(errors) * np.sqrt(ahead)


def _predict(values: np.ndarray, months: int, method: str):
    """Forecast ``months`` ahead; returns the table columns, the method used and the warnings."""
    warnings: list[str] = []
    used = method
    if method == "holt_winters" and len(values) < MIN_MONTHS_HOLT_WINTERS:
        used = "naive"
        warnings.append(
            f"Only {len(values)} months of history: the naive method was used instead of "
            f"holt_winters, which needs {MIN_MONTHS_HOLT_WINTERS}."
        )
    if used == "naive":
        forecast, half = _naive(values, months)
    else:
        forecast, half = _holt_winters(values, months)
    if len(values) < SEASON:
        warnings.append(
            "With less than a year of history the forecast repeats the last month and cannot "
            "see the seasons of the year."
        )
    centre = np.maximum(forecast, 0.0)
    lower = np.maximum(forecast - half, 0.0)
    upper = np.maximum(forecast + half, 0.0)
    return centre, lower, upper, used, method != used, warnings


def forecast_revenue(df: pd.DataFrame, months: int, method: str = "holt_winters") -> Forecast:
    """Forecast the revenue of the next ``months`` months from a loaded orders table.

    ``holt_winters`` needs 24 months of history; with fewer, the naive method is used and the
    result says so (``fell_back`` and a warning). Values are never below 0 and never rounded.

    Raises:
        TypeError: ``months`` is not a whole number.
        ValueError: ``months`` is not from 1 to 12, ``method`` is unknown, or there are fewer than
            3 complete months of history.
    """
    months = _check_range(_whole(months, "months"), "months")
    _check_method(method)
    periods, values, warnings = _monthly(df)
    _need_history(len(values))
    centre, lower, upper, used, fell_back, more = _predict(values, months, method)
    table = pd.DataFrame(
        {
            "period": pd.date_range(
                periods[-1] + pd.DateOffset(months=1), periods=months, freq="MS"
            ),
            "forecast": centre,
            "lower": lower,
            "upper": upper,
        }
    )
    return Forecast(table, used, fell_back, len(values), tuple(warnings + more))


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> Metrics:
    return Metrics(
        mean_absolute_error(actual, predicted), mean_absolute_percentage_error(actual, predicted)
    )


def evaluate(df: pd.DataFrame, method: str = "holt_winters", holdout: int = 3) -> Evaluation:
    """Measure a method on the last ``holdout`` months, trained on the months before them.

    Returns the errors of the method and of the naive baseline on those months. MAPE is None when
    one of the actual values is 0.

    Raises:
        TypeError: ``holdout`` is not a whole number.
        ValueError: ``holdout`` is not from 1 to 12, ``method`` is unknown, or fewer than 3 months
            are left to train on.
    """
    holdout = _check_range(_whole(holdout, "holdout"), "holdout")
    _check_method(method)
    _, values, warnings = _monthly(df)
    train, actual = values[:-holdout], values[-holdout:]
    _need_history(len(train), "history to train on")
    centre, _, _, used, _, more = _predict(train, holdout, method)
    baseline, _, _, _, _, _ = _predict(train, holdout, "naive")
    return Evaluation(
        method_used=used,
        holdout=holdout,
        history_months=len(train),
        model=_metrics(actual, centre),
        baseline=_metrics(actual, baseline),
        warnings=tuple(warnings + more),
    )
