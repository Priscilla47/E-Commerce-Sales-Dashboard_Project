# Changelog

All notable changes to this project are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

Compared with the first version of the tool: a few Python scripts at the root of the repository (`main.py`, `calculate.py`, `parsing.py`, `usage.py`) that read a CSV and printed some figures, without tests.

### Added

- **Packaging and quality.** An installable `sales_insights` package with a `sales-insights` command, unit tests, ruff and pre-commit, and a CI workflow with a coverage gate of 85% ([#1](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/1), [#2](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/2), [#3](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/3), [#4](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/4), [#17](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/17), [#18](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/18)).
- **Data layer.** A schema and a CSV loader, a validation report that says what is wrong and on which lines, and a storage interface with a local implementation ([#5](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/5), [#6](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/6), [#7](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/7)).
- **Analytics.** Revenue, average order value, revenue by country and by category, revenue over time by day, month or year, and filters by period, country and category ([#12](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/12), [#13](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/13), [#14](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/14), [#41](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/41)).
- **Command line.** An `argparse` interface that keeps the old flags and adds `--by`, `--forecast`, `--ask` and `--validate` ([#15](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/15), [#49](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/49), [#75](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/75)).
- **Dashboard.** A Streamlit page with a data source (sample or upload), key figures, charts, empty and error states, and tabs for the forecast, the insights and questions ([#42](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/42), [#43](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/43), [#44](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/44), [#45](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/45), [#46](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/46), [#49](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/49), [#76](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/76)).
- **Forecast.** A revenue forecast with a naive baseline and Holt-Winters, and its error measured on the last months ([#48](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/48)).
- **AI layer.** A provider interface with a switched-off mode, a fake client and a limit of calls per session ([#47](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/47)); statistical facts ([#50](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/50)); written insights whose numbers are checked against the facts ([#51](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/51)); a registry of analytics functions a model may ask for ([#69](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/69)); answers to questions with registered functions only, every number checked ([#70](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/70)); ids that pair requests and results ([#82](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/82)); an evaluation set of 24 questions and a runner ([#77](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/77)).
- **Container.** A `Dockerfile`, a compose file and a deployment guide ([#81](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/81)).
- **Documentation.** The data format, the command-line reference, the architecture overview, decision records, the dashboard guide, the AI guide, the deployment guide, this changelog and a contribution guide ([#8](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/8), [#16](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/16), [#19](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/19), [#20](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/20), [#83](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/83)).

### Changed

- The code moved from the scripts at the root into the `sales_insights` package, organised in `data`, `analytics`, `cli`, `dashboard` and `ai` ([#4](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/4)).
- A usage or data error prints a clear message on stderr instead of a traceback, with the exit code 84 that the first version used ([#15](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/15)). Output piped into a reader that stops early (`| head`) ends quietly.

### Fixed

- The top-N products skipped the first product and mishandled ties ([#9](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/9)).
- A size mismatch raised `NameError` instead of `ValueError` ([#10](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/10)).
- The "number of clients" counted orders instead of unique customers ([#11](https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/issues/11)).

[Unreleased]: https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project/compare/main...develop
