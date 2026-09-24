"""Search integration fixtures use the isolated migrated/ingested acceptance catalog."""

import pytest
from sqlalchemy import text
from modules.shared.catalog import VISIBLE_SQL
from modules.shared.integration import assertion, database_engine


@pytest.fixture
def search_headers():
    return {
        "Authorization": "Bearer " + assertion("search-acceptance", "user", "search")
    }


@pytest.fixture
def canonical_file_id():
    with database_engine("search").connect() as conn:
        value = conn.execute(
            text(
                "SELECT file_id FROM file_metadata WHERE "
                + VISIBLE_SQL
                + " ORDER BY file_id LIMIT 1"
            )
        ).scalar()
    assert value, (
        "Populate isolated acceptance sources and run projection_workflow.py first"
    )
    return value


@pytest.fixture
def canonical_title(canonical_file_id):
    with database_engine("search").connect() as conn:
        return conn.execute(text("SELECT title FROM file_metadata WHERE file_id=:id"), {"id": canonical_file_id}).scalar_one()
