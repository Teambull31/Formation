import pytest

from app.db import connect


@pytest.fixture
def db():
    conn = connect(":memory:")
    yield conn
    conn.close()
