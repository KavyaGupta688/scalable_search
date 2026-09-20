"""Non-mutating dependency readiness for separately deployed services."""

import os
import json
from pathlib import Path
from fastapi.responses import JSONResponse
from sqlalchemy import text
from modules.shared.integration import database_engine


def readiness(schema, *, broker=False, vault=False, vectors=False, models=False):
    checks = {}

    def check(name, fn):
        try:
            checks[name] = bool(fn())
        except Exception:
            checks[name] = False

    def database():
        with database_engine(schema).connect() as c:
            return c.execute(text("SELECT 1")).scalar() == 1

    check("postgres", database)
    import redis

    check(
        "redis",
        lambda: redis.Redis.from_url(
            os.environ["REDIS_URL"], socket_timeout=3, socket_connect_timeout=3
        ).ping(),
    )
    if vectors:
        from modules.shared.vector_store import provision

        check("vector_collection", lambda: provision(create=False) is not False)
    if broker:
        from confluent_kafka.admin import AdminClient

        check(
            "kafka",
            lambda: bool(
                AdminClient(
                    {"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"]}
                )
                .list_topics(timeout=3)
                .brokers
            ),
        )
    if vault:
        import hvac

        check(
            "vault",
            lambda: hvac.Client(
                url=os.environ["VAULT_URL"], token=os.environ["VAULT_TOKEN"], timeout=3
            ).is_authenticated(),
        )
    if models:
        checks["ram_checkpoint"] = Path(
            os.environ.get("RAM_CHECKPOINT_PATH", "/models/ram_plus_swin_large_14m.pth")
        ).is_file()
        manifest = os.environ.get("AI_MODEL_READINESS_FILE")
        if manifest:
            def initialized_models():
                results = json.loads(Path(manifest).read_text())
                required = {"clip", "yolo", "blip", "whisper", "ram", "paddleocr",
                            "presidio", "nudenet", "bart_mnli", "spacy", "keybert",
                            "summarizer", "face_detector", "toxicity", "ai_generated_detector"}
                return all(results.get(name, {}).get("ready") is True for name in required)
            check("model_initialization", initialized_models)
    return JSONResponse(
        {"checks": checks}, status_code=200 if all(checks.values()) else 503
    )
