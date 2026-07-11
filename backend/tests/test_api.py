"""Smoke tests for the HTTP API using the bundled snapshot as the data source.

These exercise the full request path (including the datetime comparison that previously 500'd
for a team with an upcoming fixture). They rely on data/snapshot.json being present so startup
ingestion can populate the database offline.
"""

import pytest
from fastapi.testclient import TestClient

from app.ingestion import SNAPSHOT_PATH
from app.main import app


@pytest.fixture(scope="module")
def client():
    if not SNAPSHOT_PATH.exists():
        pytest.skip("no snapshot available for offline API test")
    with TestClient(app) as c:  # triggers lifespan -> startup ingestion
        yield c


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_groups_populated(client):
    groups = client.get("/api/groups").json()
    assert len(groups) >= 1
    assert all("standings" in g and g["standings"] for g in groups)


def test_team_status_with_upcoming_fixture(client):
    # A team with a scheduled knockout match must not 500 on the naive/aware datetime compare.
    teams = client.get("/api/teams").json()
    assert teams
    for t in teams:
        resp = client.get(f"/api/teams/{t['id']}")
        assert resp.status_code == 200, f"team {t['name']} -> {resp.status_code}"
        body = resp.json()
        assert "progression" in body
        # Matches endpoint must also succeed (same datetime comparison lives there).
        assert client.get(f"/api/matches/team/{t['id']}").status_code == 200
