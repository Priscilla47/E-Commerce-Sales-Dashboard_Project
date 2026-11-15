# Command-line reference

`sales-insights` reads a CSV file of orders and prints answers about it: revenue, best sellers, customers, breakdowns, a revenue forecast and data checks. This page lists every option, with real output from the sample dataset (`data/sample_orders.csv`). The file format is described in [Data format](data-schema.md).

## Install and run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

sales-insights -h
```

It needs Python 3.11 or newer. If you only want to try it from a clone of the repository, without `pip install -e .`, install the dependencies (`pip install pandas numpy`) and run `PYTHONPATH=src python3 -m sales_insights.cli.main -T data/sample_orders.csv`.

## Usage

```
sales-insights [options] FILE
```

`FILE` is the orders CSV file and goes last. At least one option is needed. Options are answered in the order they are given, one after the other, and an option given twice is answered twice.

## Options

| Option | Argument | What it prints | Exit code |
|--------|----------|----------------|-----------|
| `-h`, `--help` | none | The help, then stops. | 0 |
| `-T` | none | The total revenue: unit price times quantity, added up over every line. | 0 |
| `-u` | none | The products sold, each once, sorted by name. | 0 |
| `-p` | `PRODUCT` | The units sold of one product, 0 if nobody bought it. The name must match exactly, capital letters included. | 0 |
| `-c` | `PRODUCT` | The number of different customers who bought the product. A customer who bought it several times counts once. | 0 |
| `-t` | `N` | The N best-selling products by units sold (products that sold the same quantity are ordered by name), then the list of their names. | 0, or 84 if N is negative, not a whole number or larger than the number of products |
| `--by` | `country`, `category` or `month` | A table of revenue, number of orders and share of the total revenue for each value, highest revenue first. For `month` the table runs in time order, without the share, and a month without orders shows 0. | 0 |
| `--forecast` | `N` | A forecast of the revenue of the next N months (1 to 12): a table with the month, the forecast and the lower and upper limits of a 95% interval, then the error of the method on the last months, next to the error of the naive baseline. The method and the warnings are explained in [the AI guide](ai.md#forecasting-revenue). | 0, or 84 if N is not from 1 to 12 or the data has fewer than 3 complete months |
| `--ask` | `QUESTION` | The answer to a question in plain language, then the functions that were run to get it. It needs the AI settings of [the AI guide](ai.md); without them it exits with 84 and names the variable to set. | 0, or 84 if the AI is switched off or misconfigured, the question is empty or over 500 characters, or no answer could be given |
| `--validate` | none | The result of the data checks described in [Data format](data-schema.md). | 0, or 84 if the data has errors (warnings alone exit with 0) |

## Examples

Every output below is copied from a real run on the sample dataset.

**Total revenue** (`-T`)

```console
$ sales-insights -T data/sample_orders.csv
Total Revenue:  261333.44
```

**Products sold** (`-u`)

```console
$ sales-insights -u data/sample_orders.csv
Items sold: ['Blender', 'Book', 'Coffee Maker', 'Desk Lamp', 'Headphones', 'Jeans', 'Laptop', 'Phone Case', 'Smartphone', 'T-shirt']
```

**Units sold of one product** (`-p`)

```console
$ sales-insights -p Laptop data/sample_orders.csv
Number of Laptop sold:  147
```

**Customers who bought a product** (`-c`). There are 46 laptop orders, but one customer bought a laptop twice.

```console
$ sales-insights -c Laptop data/sample_orders.csv
Number of clients that bought:  Laptop = 45
```

**Best sellers** (`-t`)

```console
$ sales-insights -t 3 data/sample_orders.csv
1 - Smartphone  sold  186  times
2 - Book  sold  176  times
3 - Desk Lamp  sold  175  times
Top  3 :  ['Smartphone', 'Book', 'Desk Lamp']
```

**Revenue by country** (`--by country`)

```console
$ sales-insights --by country data/sample_orders.csv
Revenue by country
Country     Revenue  Orders  Share
USA        35336.02      54  13.5%
India      32558.63      56  12.5%
Cameroon   27386.92      48  10.5%
Brazil     26196.71      41  10.0%
Nigeria    25654.21      55   9.8%
Australia  25541.30      49   9.8%
UK         24514.11      46   9.4%
France     22314.19      52   8.5%
Canada     21250.55      47   8.1%
Germany    20580.80      52   7.9%
```

**Revenue by category** (`--by category`)

```console
$ sales-insights --by category data/sample_orders.csv
Revenue by category
Category       Revenue  Orders  Share
Electronics  222708.35     152  85.2%
Home Goods    27116.34     159  10.4%
Clothing       8264.90     100   3.2%
Books          1775.55      57   0.7%
Accessories    1468.30      32   0.6%
```

**Revenue by month** (`--by month`)

```console
$ sales-insights --by month data/sample_orders.csv
Revenue by month
Month     Revenue  Orders
2025-01  63302.67     115
2025-02  57336.13     106
2025-03  61865.09     133
2025-04  78313.71     142
2025-05    515.84       4
```

**Revenue forecast** (`--forecast`). The sample file ends on 1 May, so the forecast learns from January to April and starts in May. Only four months of history is little, so the naive method is used and the command says so on stderr, which is separate from the answer:

```console
$ sales-insights --forecast 3 data/sample_orders.csv
Revenue forecast (naive method)
Month    Forecast     Lower      Upper
2025-05  78313.71  57861.09   98766.33
2025-06  78313.71  49389.34  107238.08
2025-07  78313.71  42888.74  113738.68
Error on the last 1 month, naive method: MAE 16448.62, MAPE 21.0%; baseline: MAE 16448.62, MAPE 21.0%
```

and on stderr:

```stderr
sales-insights: warning: The last month (2025-05) was left out because the data stops on day 1 of 31.
sales-insights: warning: Only 4 months of history: the naive method was used instead of holt_winters, which needs 24.
sales-insights: warning: With less than a year of history the forecast repeats the last month and cannot see the seasons of the year.
```

The last line of the answer is the error the method makes when it forecasts the most recent month it knows (here April), trained on the months before. With a longer history it is measured on the last 3 months. MAE is the mean absolute error, in the unit of the revenue; MAPE is the same error in percent of the real value (`n/a` when a real value is 0).

**A question in plain language** (`--ask`). It needs a model: set `SALES_AI_PROVIDER` and `SALES_AI_API_KEY` first (see [the AI guide](ai.md)). The project ships no provider, by design: one is added by registering a function that builds its client (see [Provider names](ai.md#provider-names)); until then `--ask` says `No provider is installed`. The model only chooses which functions to call; every number of the answer was returned by one of them, and the functions are listed so that you can see where it came from. The answer is printed on one line, without control characters and with the key replaced by `***`, so the text of a model can neither change the terminal nor print a list of functions of its own. This example is not run by the page tests with a real model: they run it with a scripted one.

```text
$ sales-insights --ask "What sells best?" data/sample_orders.csv
The best seller is Smartphone with 186 units.
Functions used:
  top_products(n=1)
```

Without the settings the command does not guess; it says what to set and exits with 84:

```text
$ sales-insights --ask "What sells best?" data/sample_orders.csv
sales-insights: error: The AI features are switched off. Set SALES_AI_API_KEY to switch them on.
```

**Data checks** (`--validate`). The sample dataset is clean.

```console
$ sales-insights --validate data/sample_orders.csv
Validation: no issues found
```

**Several options at once.** The answers come in the order of the options.

```console
$ sales-insights -T -t 2 -p Book data/sample_orders.csv
Total Revenue:  261333.44
1 - Smartphone  sold  186  times
2 - Book  sold  176  times
Top  2 :  ['Smartphone', 'Book']
Number of Book sold:  176
```

## Exit codes and errors

The exit code is **0** when the command worked and **84** for a usage error, a data error or a question that could not be answered. Messages are written to the error output (stderr) and start with `sales-insights: error: `. The answers themselves go to the normal output (stdout), so `sales-insights -T data.csv > total.txt` only stores the answer.

| Message | Cause | Fix |
|---------|-------|-----|
| `the following arguments are required: file` | No file was given, or an option that expects a value took the file as its value (`-c data.csv`). | Put the file last, after every option and its value. |
| `choose at least one option, for example -T (see -h)` | A file but no option. | Add an option. |
| `unrecognized arguments: -x` | An option that does not exist. Option names cannot be shortened (`--val` is not accepted). | Check the spelling with `-h`. |
| `argument -t: invalid int value: 'abc'` | `-t` needs a whole number. | Write the number, for example `-t 3`. |
| `argument --by: invalid choice: 'colour'` | `--by` accepts `country`, `category` or `month`. | Use one of the three. |
| `months must be from 1 to 12, not 13` | `--forecast` with a number outside 1 to 12. | Choose a whole number from 1 to 12. |
| `The forecast needs at least 3 months of history, found 2` | `--forecast` on a file with fewer than 3 complete months. | Use a file with more months (a last month that the data does not finish does not count). |
| `The AI features are switched off. Set SALES_AI_API_KEY to switch them on.` | `--ask` without a key. | Set the variables of [the AI guide](ai.md). |
| `The text contained numbers that are not in the results: 37%` | `--ask`: the model wrote a number that no function returned, twice, so no text is shown. | Ask again, or in other words. |
| `I can't answer that with the data and functions I have.` | `--ask` with a question that the functions cannot answer (the weather, a cause, a forecast). | Ask about revenue, products, customers, countries, categories or months. |
| `The AI features are switched off. Set SALES_AI_PROVIDER to the provider to use.` | `--ask` with a key but no provider. | Set `SALES_AI_PROVIDER` (see [the AI guide](ai.md)). |
| `No provider is installed, so 'x' cannot be used` | `--ask` with a provider name, but no provider registered in this installation. | Register one with `register_provider` (see [the AI guide](ai.md#provider-names)). |
| `SALES_AI_MAX_CALLS must be a whole number from 1 to 10000, not 'many'` | `--ask` with a bad limit of calls. | Use a whole number from 1 to 10000, or leave it unset (20). |
| `The question is empty` | `--ask` with an empty question, or only spaces. | Write the question. |
| `The question is longer than 500 characters` | `--ask` with a question of more than 500 characters. | Ask a shorter question. |
| `The language model could not answer: The limit of 1 calls for this session is reached` | `--ask` when the call failed: a timeout, an error of the provider, or the limit of `SALES_AI_MAX_CALLS` reached by one question. | Try again, or raise the limit. |
| `Wrong number of products` | `-t N` with an N below 0 or above the number of products. | Choose N between 0 and the number of products (`-u` lists them). |

Problems with the file itself (not found, wrong columns, a value that cannot be read, a file that is not UTF-8) use the same exit code and are listed in [Data format](data-schema.md#errors-you-may-see).

When the data has validation errors, the other options still answer (empty cells are skipped in the sums) and print a warning on stderr:

```
sales-insights: warning: 1 error found in the data, so some figures may be unreliable; run with --validate for details
```

## Coming from `python3 main.py`

The first version of the tool was a script run as `python3 main.py -T data.csv`. The command is now `sales-insights`, with the same options and the same output for `-T`, `-u`, `-p`, `-c` and `-t`. What changed:

- `-c` counts **unique customers**; it used to count orders (46 instead of 45 for `Laptop` on the sample dataset).
- `-t N` ranks every product correctly: the first product alphabetically was never ranked and tied products were listed twice.
- Errors go to stderr with exit code 84. A bad `-t` value and a folder given as the file used to end with a traceback.
- `-h` can be followed by a file and always exits with 0. `--by` and `--validate` are new.
