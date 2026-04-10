# Contributing to climate-shift

Thanks for your interest in contributing! This project is a global glacier retreat monitoring toolkit, built to help climate scientists and communicators tell the story of vanishing ice.

## Ways to contribute

- **Report bugs** — Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.yml).
- **Request features** — See [feature request template](.github/ISSUE_TEMPLATE/feature_request.yml).
- **Add a glacier** — Suggest a new glacier for the built-in registry via [glacier request template](.github/ISSUE_TEMPLATE/glacier_request.yml).
- **Improve documentation** — README, docstrings, examples.
- **Write code** — Bug fixes, new features, refactors.
- **Share results** — Tag the project when you publish glacier visualizations.

## Development setup

```bash
# 1. Clone and enter the repo
git clone https://github.com/bijanf/climate-shift.git
cd climate-shift

# 2. Create a virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 3. Install with all optional dependencies
pip install -e ".[geo,gee,dev]"

# 4. Install pre-commit hooks
pre-commit install

# 5. Verify everything works
pytest tests/
ruff check glacier_toolkit/ tests/
ruff format --check glacier_toolkit/ tests/
```

## Running tests

```bash
# Fast unit tests (no network, no GEE)
pytest tests/

# With coverage
pytest tests/ --cov=glacier_toolkit --cov-report=term-missing

# Run a specific test file
pytest tests/test_statistics.py -v

# Run a single test
pytest tests/test_glof.py::TestClassifyRisk::test_high_risk_lake -v
```

## Code style

We use `ruff` for both linting and formatting. Configuration is in `pyproject.toml`.

```bash
# Auto-fix lint issues
ruff check --fix glacier_toolkit/ tests/

# Auto-format code
ruff format glacier_toolkit/ tests/
```

Pre-commit hooks run these automatically on every commit.

### Style guidelines

- **Line length**: 100 characters
- **Quotes**: Double quotes for strings
- **Type hints**: Use them for new public functions
- **Docstrings**: NumPy style (Parameters / Returns / Notes sections)
- **Imports**: `ruff` (`isort` preset) handles ordering automatically
- **No emojis** in code, comments, or docs (except where data files need them)

## Commit messages

Use clear, present-tense commit messages:

- Good: `Add Pamir glacier registry entries`
- Good: `Fix NDSI threshold edge case for tropical glaciers`
- Bad: `update`
- Bad: `fixed bug`

Reference issues with `#NNN` when relevant: `Fix #42: glacier name with slash breaks file path`.

## Pull request process

1. Fork the repo and create a feature branch from `main`
2. Make your changes with tests
3. Run `pytest`, `ruff check`, and `ruff format --check` locally
4. Push your branch and open a PR using the [PR template](.github/pull_request_template.md)
5. Wait for CI to pass
6. Address review feedback
7. Once approved, your PR will be merged

## Adding a new glacier to the registry

1. Edit `glacier_toolkit/config.py` and add an entry to `GLACIER_REGISTRY`
2. Required fields: `name`, `region`, `lat`, `lon`, `bbox`, `hemisphere`, `season`, `notes`
3. Use the appropriate season constant (`SEASON_NH_SUMMER`, `SEASON_SH_SUMMER`, or a custom dry-season list for tropical glaciers)
4. Add a test to `tests/test_config.py` if your glacier introduces a new edge case
5. Update `docs/QUICKSTART.md` if it's a particularly notable example

## Adding a new analysis module

1. Place pure-function modules under `glacier_toolkit/analyze/`
2. Visualization helpers go under `glacier_toolkit/visualize/`
3. Pipeline scripts (CLI entry points) go under `glacier_toolkit/pipelines/`
4. Add a corresponding test file under `tests/`
5. Update the README's module table if your module is user-facing

## Reporting security issues

If you discover a security vulnerability, please email bijan.fallah@gmail.com directly rather than opening a public issue.

## Code of conduct

By participating, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
