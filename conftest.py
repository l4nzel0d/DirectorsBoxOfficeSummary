"""Shared pytest config: gate the live-API integration tests.

Integration tests are skipped by default. Run them with:
    .venv/bin/pytest --integration
They additionally skip if API_KEY is unavailable.
"""

import os

import pytest
from dotenv import load_dotenv

load_dotenv()


def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="run integration tests that hit the live IMDb API",
    )


def pytest_collection_modifyitems(config, items):
    run_integration = config.getoption("--integration")
    has_key = bool(os.getenv("API_KEY"))
    for item in items:
        if "integration" not in item.keywords:
            continue
        if not run_integration:
            item.add_marker(pytest.mark.skip(reason="pass --integration to run live API tests"))
        elif not has_key:
            item.add_marker(pytest.mark.skip(reason="API_KEY not set"))
