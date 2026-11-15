# Contributing

Thank you for helping. This page says how to set up the project, the rules a change follows and how to propose it. How the code is organised is in [the architecture overview](docs/architecture.md).

## Set up

You need Linux or macOS and Python 3.11 or newer.

```bash
git clone git@github.com:Priscilla47/E-Commerce-Sales-Dashboard_Project.git
cd E-Commerce-Sales-Dashboard_Project
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

`.[dev]` installs the test and lint tools and the dashboard extra, so that no test is skipped. `pre-commit install` runs ruff and two whitespace fixers before each commit.

## Run the checks

The same checks as the CI workflow (`.github/workflows/ci.yml`):

```bash
ruff check .
ruff format --check .
pytest --cov=sales_insights --cov-fail-under=85
```

All three must pass before a pull request is opened.

## Rules for a change

- **Tests in the same pull request.** Every feature and every fix comes with unit tests. A bug fix starts with a test that fails because of the bug. Tests use small hand-written tables that can be checked by hand, cover the edge cases (empty data, ties, invalid input, limits) and never call a real language model: they use `FakeLLM`.
- **Docs with the code.** A feature is done when its page in `docs/` or the README says what it does. Many pages have tests that run their examples, so a change that breaks a page breaks a test.
- **The layers keep their rules.** `analytics` holds pure functions on the orders table and imports no interface; `cli` and `dashboard` only call and display; a language model never computes a number. The architecture overview lists what may import what, and a test checks it.
- **No secrets.** Keys go in `.env`, which git ignores; `.env.example` lists the variables.
- **Small commits** with [Conventional Commits](https://www.conventionalcommits.org/) subjects: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `build:`, `ci:` or `chore:`, lowercase and in the imperative, under 72 characters.

## Propose a change

1. Open an issue first for anything larger than a typo (templates: bug, feature, question), so that the change can be agreed on.
2. Branch from `develop`: `feat/<issue>-<topic>`, `fix/<issue>-<topic>` or `docs/<issue>-<topic>`.
3. Open a pull request to `develop` and fill in the template: what changed, why, how to test it, and `Closes #<issue>`.
4. `main` only receives `develop` for a release.

## Report a bug

Open an issue with the bug template: the command or the steps, what you expected, what happened (the full message), your Python version and your system. A small CSV file that shows the problem helps most; never attach real customer data.
