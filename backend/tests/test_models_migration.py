"""init_db() must add columns introduced after a DB was first created
(create_all never ALTERs existing tables)."""
import models


def test_init_db_adds_is_active_to_legacy_businesses(db):
    # Simulate a legacy DB: businesses table without is_active.
    models.Base.metadata.drop_all(models.engine)
    with models.engine.connect() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE businesses (id INTEGER PRIMARY KEY, name VARCHAR(200), "
            "category VARCHAR(100))"
        )
        conn.commit()

    models.init_db()

    with models.engine.connect() as conn:
        cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(businesses)")]
    assert "is_active" in cols
