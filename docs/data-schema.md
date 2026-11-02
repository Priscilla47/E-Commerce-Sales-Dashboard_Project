# Data format

This page describes the file the project reads, how it is loaded, and the checks applied to its content.

## Columns

An orders file is a CSV file with a header row. It must contain these eight columns, in any order. Extra columns are allowed and are kept untouched.

| Name | Type | Value required | Example | Description |
|------|------|----------------|---------|-------------|
| `OrderID` | whole number | yes | `1000` | Identifier of the order line. Must be unique. |
| `Date` | date | yes | `2025-04-17` | Order date, written `YYYY-MM-DD`. |
| `Product` | text | yes | `Blender` | Product name. |
| `Category` | text | no | `Home Goods` | Product category. |
| `UnitPrice` | number | yes | `61.18` | Price of one unit. Must not be negative. |
| `Quantity` | whole number | yes | `3` | Units ordered. Must not be negative. |
| `CustomerID` | text | no | `CUST410` | Customer identifier. |
| `Country` | text | no | `Nigeria` | Customer country. |

"Value required" means an empty cell is reported as an error by the validation step. The column itself must always be present.

## What loading produces

`load_orders(path)` returns a table with:

- the eight columns above, in this order, with the types shown;
- then any extra columns of the file;
- then a computed `Revenue` column, defined as `UnitPrice * Quantity`. A `Revenue` column in the file is ignored and recomputed.

Details worth knowing:

- Empty cells are kept as missing values, not rejected. The validation step reports them.
- A date may also carry a time of day or a UTC offset (`2025-04-17T10:30:00+01:00`), as long as every date uses the same offset.
- Text such as `NA` is a normal value (it is a real country code), not a missing cell.
- `OrderID` and `Quantity` are plain integers, or nullable integers when a cell is empty.
- A value that cannot be read as its column's type (a date that is not `YYYY-MM-DD`, a price that is not a finite number such as `abc` or `inf`, a quantity such as `2.5`) stops the loading with an error that gives the column, the line number and the value.

```python
from sales_insights.data.loader import load_orders
from sales_insights.data.validation import validate_orders

orders = load_orders("data/sample_orders.csv")
report = validate_orders(orders)
print(report.summary())
```

## Validation rules

`validate_orders(orders)` checks the content of a loaded table and returns a report. It never raises on bad data: problems are collected in the report. An **error** makes the data invalid. A **warning** is worth a look but does not make it invalid.

Lines in the report are line numbers of the CSV file: the header is line 1, so the first order is line 2.

| Code | Severity | What is checked | Example |
|------|----------|-----------------|---------|
| `missing_value` | error | An empty cell in `OrderID`, `Date`, `Product`, `UnitPrice` or `Quantity`. | A line with no product name. |
| `negative_value` | error | A `UnitPrice` or `Quantity` below zero. | `Quantity` of `-1`. |
| `duplicate_order_id` | error | The same `OrderID` on more than one line. One finding per duplicated ID. | `OrderID` 1001 on lines 3 and 5. |
| `zero_quantity` | warning | A `Quantity` equal to zero. | `Quantity` of `0`. |
| `future_date` | warning | A `Date` after today. | A date next year. |
| `untrimmed_text` | warning | Spaces before or after the text in `Product` or `Country`. | `Book ` instead of `Book`. |
| `inconsistent_casing` | warning | The same `Product` or `Country` written with different capital letters. | `France` and `france`. |

Example of a report:

```
Validation: 1 error, 1 warning
  [error] Duplicate OrderID 1001 (lines 3 and 5)
  [warning] Quantity is zero (line 4)
```

## A minimal valid file

Copy this into a file to try the project. It loads without errors and passes validation.

```csv
OrderID,Date,Product,Category,UnitPrice,Quantity,CustomerID,Country
1000,2025-01-05,Book,Books,10.0,2,C1,France
1001,2025-01-20,Laptop,Electronics,500.0,1,C2,UK
1002,2025-02-03,Book,Books,10.0,3,C1,France
```

## Errors you may see

On the command line, each of these stops the program with exit code 84. The message is written to the error output (stderr), after `sales-insights: error: `.

| Message | Cause | Fix |
|---------|-------|-----|
| `Orders file not found: <path>` | The path does not point to a file: it is missing, or it is a folder. | Check the path. |
| `The orders file is not UTF-8 text; in a spreadsheet, save it as 'CSV UTF-8'` | The file is saved as Latin-1, UTF-16 or another encoding, or it is not a text file. | Save it again as "CSV UTF-8". |
| `The orders file is empty: it has no header row` | The file has no content. | Add the header row and the data. |
| `The orders file is not valid CSV: Expected 8 fields in line 3, saw 9` | A row has more values than the header, or a quote is never closed. The reason and the line come from the CSV reader. | Fix the row: remove the extra value, or quote the text that contains a comma. |
| `The orders file is not valid CSV: its rows have more values than the header` | Every row has one value too many. | Add the missing column name to the header, or remove the extra values. |
| `Duplicate column(s) in the header: Quantity` | The same column name appears twice in the header. | Keep a single column of that name. |
| `Missing required column(s): Quantity` | One or more of the eight columns are absent. All missing columns are listed. | Add the columns, or rename them to match the table above. |
| `Column 'Date' mixes time zones; write every date with the same offset, or none` | Some dates have a UTC offset (such as `+01:00`) and others have a different one, or none. | Use the same offset on every date, or remove the offsets. |
| `Column 'Date' must hold a date (YYYY-MM-DD); line 3 has 'abc'` | A value cannot be read as the column's type. The first bad line is shown, with a count of the others. | Correct the value. |
