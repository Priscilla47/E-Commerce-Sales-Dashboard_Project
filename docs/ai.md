# AI features

This page explains how the AI features are built and how to switch them on. The project works without them: with no key set, every other feature behaves as before. For where the code lives and what it may import, see the [architecture](architecture.md).

## Principles

1. **Numbers come from pandas.** Every figure shown to a reader is computed by the `analytics` package. A language model never calculates, estimates or invents a figure; it only receives figures that were already computed and turns them into words.
2. **The model is a replaceable part.** The features talk to a small interface (`LLMClient`), never to a provider. Choosing or changing the provider touches one place, not the features.
3. **Tests never call a service.** They use `FakeLLM`, which answers from a script and records what it was asked.
4. **Nothing secret leaks.** The key is read from an environment variable, is hidden in `repr()` and `str()` of the configuration, and is removed from every error message.
5. **Off by default.** Without a key the AI features are switched off, and the rest of the project does not change.

The forecast of revenue (see the next pages of this guide) is a statistical model and needs no language model: it works with the AI switched off.

## The interface

`sales_insights.ai.llm` defines what a client must offer:

```python
from sales_insights.ai.llm import Message

reply = client.complete([Message("user", "Which country sold the most?")])
print(reply.text)  # the answer
print(reply.tool_calls)  # functions the model asks for, none here
```

- `Message(role, content)`: `role` is `system`, `user`, `assistant` or `tool`.
- `Completion(text, tool_calls=())`: what came back. A `ToolCall` has a `name` and its `arguments`.
- `LLMError`: a call failed, timed out, or went over the limit of the session.

## Switching the AI on or off

The settings are read from four environment variables. Copy [`.env.example`](../.env.example) to `.env` and fill it in; `.env` is ignored by git.

| Variable | Meaning | Default |
|----------|---------|---------|
| `SALES_AI_PROVIDER` | The provider to use. | none |
| `SALES_AI_MODEL` | The model of that provider. | none |
| `SALES_AI_API_KEY` | The secret key. Empty means off. | none |
| `SALES_AI_MAX_CALLS` | The most calls one session may make, 1 to 10000. | 20 |

`load_config(os.environ)` reads them. `config.enabled` is `False` when there is no key or no provider, and `build_client(config)` then raises `AIDisabled` with a message that names the variable to set:

```text
The AI features are switched off. Set SALES_AI_API_KEY to switch them on.
```

A bad `SALES_AI_MAX_CALLS` raises `ConfigError`, which names the variable and never shows the key.

## Provider names

Decision: **no provider is named in the code, the tests or the documentation of the project.** The configuration holds only the name a user writes in `SALES_AI_PROVIDER`; a provider is added by registering a function that builds its client (`register_provider(name, factory)`), kept outside the features. The reasons: the features stay independent of any one company, the code keeps working if the provider changes, and the examples cannot go out of date. A test checks that no well-known provider name appears in the `ai` package, this page or `.env.example`.

## Limits of a session

`build_client` wraps the client so that one session cannot make more than `SALES_AI_MAX_CALLS` calls. A call over the limit is refused without reaching the provider, and a call that fails still counts, so that a loop of failing calls ends. The error messages that leave the wrapper have the key replaced by `***`.

## Testing with the fake client

```python
from sales_insights.ai.fake import FakeLLM
from sales_insights.ai.llm import Message

fake = FakeLLM(["Paris", "London"])
fake.complete([Message("user", "first")]).text  # 'Paris'
fake.complete([Message("user", "second")]).text  # 'London'
fake.calls[0].messages  # what the first call received
```

A third call raises `LLMError` that says how many answers were scripted. An item of the script can also be an exception, raised in its turn, to test a failing provider.

## Forecasting revenue

The forecast is a statistical model, not a language model: it needs no key and works with the AI switched off. It lives in `sales_insights.ai.forecast` and starts from the monthly revenue that `analytics` returns.

```python
from sales_insights.ai.forecast import evaluate, forecast_revenue
from sales_insights.data.loader import load_orders

orders = load_orders("data/sample_orders.csv")
result = forecast_revenue(orders, 3)
print(result.table)  # period, forecast, lower, upper
print(result.method_used)  # naive
print(result.warnings)  # what the reader should know
quality = evaluate(orders, "holt_winters", holdout=1)
print(quality.model.mae, quality.baseline.mae)
```

- `forecast_revenue(df, months, method="holt_winters")` forecasts 1 to 12 months, with a 95% interval (`lower` and `upper`). Values are never below 0 and never rounded.
- **Methods.** `naive` repeats the same month of the previous year, or the last value when there is less than a year of history. `holt_winters` follows a trend and the seasons of the year and needs 24 months. With fewer, the result falls back to `naive` and says so (`fell_back` and a warning); asking for `naive` is not a fallback.
- **Complete months only.** A month counts when the data reaches its last day. A last month that stops earlier, such as one that holds the first day of the month only, is left out and a warning says so, because its small revenue would be read as a fall. The sample file ends on 1 May, so its forecast learns from January to April and starts in May.
- **At least 3 months.** With fewer, `forecast_revenue` raises `ValueError` and says how many are needed.
- `evaluate(df, method, holdout=3)` trains on all but the last `holdout` months, forecasts those months and returns the **MAE** (mean absolute error, in the unit of the revenue) and the **MAPE** (the same error in percent of the real value, `None` when a real value is 0), for the method and for the naive baseline. A forecast is worth showing when its error is below the baseline's; on the sample file both are the same method, because the history is short.

`forecast_with_error(df, months)` returns the forecast, its error and its history in one report; it is what both interfaces use. The command line prints it with `--forecast N` (see [the command-line reference](cli.md)) and the dashboard shows it in its Forecast tab (see [the dashboard guide](dashboard.md)); a test checks that the two show the same numbers.

The result is plain data: a table and small frozen objects. The forecast code does not read a file, print or round.

## Statistical facts

The written insights (see the next pages of this guide) start from facts that code computes, never from the raw table. `sales_insights.ai.facts` holds them; it needs no language model and no key.

```python
from sales_insights.ai.facts import compute_facts
from sales_insights.data.loader import load_orders

orders = load_orders("data/sample_orders.csv")
facts = compute_facts(orders)
print(facts.orders, facts.top_product.name)  # 500 Smartphone
print(facts.trend.direction, facts.best_month.period)  # up 2025-04
data = facts.as_dict()  # plain values, ready for json.dumps
```

`compute_facts(df)` returns a frozen `Facts` with: the number of `orders`, the period (first and last day), the `trend`, the `best_month` and `worst_month`, the `anomalies`, the `share_changes` and the `top_product`, plus `notes` that say what was left out and why. A field is `None` (or an empty tuple) when there is nothing to say, and an empty table gives an empty `Facts` without an error. There is no sentence in it, only values.

The rules, which a test checks at each limit:

- **Months** are the complete months of the revenue, as for the forecast. A last month that the data does not finish (the sample file stops on 1 May) is left out, and a note says so.
- **Trend.** The slope is the least-squares line through the monthly revenue, in revenue per month. It is `flat` when it is under 1% of the mean revenue of a month, `up` or `down` otherwise. It needs at least 2 months.
- **Best and worst month**, with their revenue; the earliest wins a tie.
- **Anomalies** are the months more than 2 standard deviations away from the mean (a z-score above 2 or below -2, with the standard deviation of the months themselves). They need at least 6 complete months; with fewer the list is empty and `anomalies_note` says how many were found.
- **Share changes** compare the first and the second half of the period (cut at the middle date) for `Country` and `Category`: a value is listed when its share of the revenue moved by at least 5 percentage points. A value that exists in one half only has a share of 0 in the other. The biggest changes come first.
- **Top product** by units sold.

Every number is an `analytics` number or a simple formula on one (the shares come from `revenue_by`, the top product from `top_products`, the months from `revenue_over_time`), and nothing is rounded.
