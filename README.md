# E-Commerce Sales Dashboard

A Python tool to explore e-commerce order data: revenue, best-selling products, customers, and (soon) an interactive dashboard with AI-assisted insights.

> **Status: early stage, being restructured.** The command-line tool works today. The dashboard and AI features are on the roadmap below.

## Goals

- Turn a raw orders CSV into clear answers: how much did we sell, what sells best, who buys what, and where.
- Offer two ways to use it: a command-line tool and an interactive dashboard, both built on the same analytics code.
- Add an AI layer that answers questions in plain language, writes short insights about trends, and forecasts revenue. Numbers are always computed by code; the language model only interprets them.
- Stay simple to install, easy to read, and well documented.

## What works today

A CLI that reads an orders CSV and answers questions about it.

| Flag      | Description                                       |
|-----------|---------------------------------------------------|
| `-h`      | Show usage                                        |
| `-T`      | Total revenue (quantity x unit price)             |
| `-u`      | List the unique products sold                     |
| `-p NAME` | Units sold for one product                        |
| `-c NAME` | Number of orders for one product                  |
| `-t N`    | The N best-selling products                       |

The CSV path is always the last argument.

## Quick start

```bash
git clone git@github.com:Priscilla47/E-Commerce-Sales-Dashboard_Project.git
cd E-Commerce-Sales-Dashboard_Project

python3 -m venv .venv
source .venv/bin/activate
pip install -e .

sales-insights -T data/sample_orders.csv
sales-insights -t 3 data/sample_orders.csv
sales-insights -p Laptop -c Laptop data/sample_orders.csv
```

Example output:

```
$ sales-insights -t 3 data/sample_orders.csv
1 - Smartphone  sold  186  times
2 - Book  sold  176  times
3 - Desk Lamp  sold  175  times
```

## Data format

`data/sample_orders.csv` is a sample dataset of 500 orders with these columns:

| Column       | Description                         |
|--------------|-------------------------------------|
| `OrderID`    | Unique order identifier             |
| `Date`       | Order date (`YYYY-MM-DD`)           |
| `Product`    | Product name                        |
| `Category`   | Product category                    |
| `UnitPrice`  | Price of one unit                   |
| `Quantity`   | Units ordered                       |
| `CustomerID` | Customer identifier                 |
| `Country`    | Customer country                    |

See [Data format](docs/data-schema.md) for the full description, the loading rules and the validation checks.

## Project layout

```
.
├── src/sales_insights/
│   ├── analytics/   analytics functions
│   ├── cli/         command-line interface
│   ├── data/        data loading and validation (planned)
│   ├── dashboard/   interactive dashboard (planned)
│   └── ai/          AI-assisted features (planned)
├── tests/           unit tests
└── data/
    └── sample_orders.csv
```

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

pytest
```

Every feature and every fix comes with unit tests. Tests live in `tests/` and use small fixtures that can be checked by hand.

## Roadmap

- [ ] Restructure into a proper Python package with tests and CI
- [ ] Data loading with validation and clear error messages
- [ ] More analytics: revenue by country, category and time period
- [ ] Interactive dashboard
- [ ] AI features: natural-language questions, automatic insights, revenue forecasting
- [ ] Docker image and deployment guide

## Contributing

The project is changing quickly, so a contribution guide will come once the new structure is in place. Issues and suggestions are welcome.
