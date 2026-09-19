"""Real database/broker outage acceptance, orchestrated only on the isolated project."""

import sys, time
from sqlalchemy import text
from sqlalchemy.orm import Session
from modules.shared.delivery import enqueue
from modules.shared.integration import database_engine

engine = database_engine("ingestion")
key = "acceptance-broker-recovery-v1"
phase = sys.argv[1]
if phase == "enqueue":
    with engine.connect() as c:
        payload = c.execute(
            text(
                "SELECT payload FROM integration_outbox WHERE kind='ai-processing' ORDER BY created_at LIMIT 1"
            )
        ).scalar_one()
    with Session(engine) as s:
        enqueue(s, "acceptance-rolled-back", "ai-processing", payload)
        s.rollback()
    with Session(engine) as s:
        enqueue(s, key, "ai-processing", payload)
        s.commit()
    with engine.connect() as c:
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM integration_outbox WHERE key='acceptance-rolled-back'"
                )
            ).scalar()
            == 0
        )
    print("PASS: rollback produced no durable delivery; committed replay queued")
elif phase == "outage":
    for _ in range(65):
        with engine.connect() as c:
            r = c.execute(
                text(
                    "SELECT attempts,delivered_at FROM integration_outbox WHERE key=:k"
                ),
                {"k": key},
            ).one()
        if r.attempts:
            break
        time.sleep(1)
    assert r.attempts >= 1 and r.delivered_at is None, r
    print("PASS: broker failure retained committed work")
elif phase == "recovered":
    for _ in range(90):
        with engine.connect() as c:
            r = c.execute(
                text(
                    "SELECT attempts,delivered_at FROM integration_outbox WHERE key=:k"
                ),
                {"k": key},
            ).one()
        if r.delivered_at:
            break
        time.sleep(1)
    assert r.delivered_at is not None, r
    print("PASS: broker restart delivered retained work")
