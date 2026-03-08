from pathlib import Path

import pytest


@pytest.fixture
def get_test_data_path():
    """Fixture that returns a function to get test data file paths by name."""

    def _get_test_data_path(filename: str) -> Path:
        """Get path to a test data file by filename."""
        return Path(__file__).parent / "data" / filename

    return _get_test_data_path
