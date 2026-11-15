# Changelog

All notable changes to this project are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

Compared with the first version of the tool: a few Python scripts at the root of the repository (`main.py`, `calculate.py`, `parsing.py`, `usage.py`) that read a CSV and printed some figures, without tests.

### Added

- **Packaging and quality.** An installable `sales_insights` package with a `sales-insights` command, unit tests, ruff and pre-commit, and a CI workflow with a coverage gate of 85% (#1, #2, #3, #4, #17, #18).
- **Data layer.** A schema and a CSV loader, a validation report that lists every problem by line, and a storage interface with a local implementation (#5, #6, #7).
- **Analytics.** Revenue, average order value, revenue by country and by category, revenue over time by day, month or year, and filters by period, country and category (#12, #13, #14, #41).
- **Command line.** An `argparse` interface that keeps the old flags and adds `--by`, `--forecast`, `--ask` and `--validate` (#15, #49, #75).
- **Dashboard.** A Streamlit page with a data source (sample or upload), key figures, charts, empty and error states, and tabs for the forecast, the insights and questions (#42, #43, #44, #45, #46, #49, #76).
- **Forecast.** A revenue forecast with a naive baseline and Holt-Winters, and its error measured on the last months (#48).
- **AI layer.** A provider interface with a switched-off mode, a fake client and a limit of calls per session (#47); statistical facts (#50); written insights whose numbers are checked against the facts (#51); a registry of analytics functions a model may ask for (#69); answers to questions with registered functions only, every number checked (#70); ids that pair requests and results (#82); an evaluation set of 24 questions and a runner (#77).
- **Container.** A `Dockerfile`, a compose file and a deployment guide (#81).
- **Documentation.** The data format, the command-line reference, the architecture overview, decision records, the dashboard guide, the AI guide, the deployment guide, this changelog and a contribution guide (#8, #16, #19, #20, #83).

### Changed

- The code moved from the scripts at the root into the `sales_insights` package, organised in `data`, `analytics`, `cli`, `dashboard` and `ai` (#4).
- Errors exit with code 84 and a message on stderr, never with a traceback (#15).

### Fixed

- The top-N products skipped the first product and mishandled ties (#9).
- A size mismatch raised `NameError` instead of `ValueError` (#10).
- The "number of clients" counted orders instead of unique customers (#11).
