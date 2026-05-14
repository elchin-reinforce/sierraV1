"""Shared test fixtures."""
from __future__ import annotations
import copy
import pytest
from pathlib import Path

# Ensure domain tools are registered before any test imports
import taufreebench.domains.retail.tools  # noqa: F401


DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture
def retail_db():
    from taufreebench.core.db import load_domain_db
    return load_domain_db("retail", DATA_DIR)


@pytest.fixture
def db(retail_db):
    """Fresh deep-copy of retail DB for each test."""
    return copy.deepcopy(retail_db)
