import pytest
from fastapi.testclient import TestClient

from credentialgate.bootstrap import seed
from credentialgate.service import create_app


@pytest.fixture
def fixture_data(tmp_path):
    tokens = seed(tmp_path)
    return tmp_path, tokens


@pytest.fixture
def api(fixture_data):
    directory, tokens = fixture_data
    with TestClient(create_app(directory)) as client:
        yield client, tokens, directory


def bearer(tokens, profile):
    return {"Authorization": f"Bearer {tokens[profile]}"}
