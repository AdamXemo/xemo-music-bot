import os

import pytest


@pytest.fixture
def database_url() -> str:
    """URL of a disposable test database, or skip when none is configured.

    Deliberately not DATABASE_URL: these tests drop tables, so they must never run
    against the development database by accident.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        # In CI a missing URL is a broken workflow, not a choice; a skip would hide it.
        if os.environ.get("CI"):
            pytest.fail("TEST_DATABASE_URL must be set in CI")
        pytest.skip("TEST_DATABASE_URL is not set")
    return url
