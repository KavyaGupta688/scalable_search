from modules.shared.vector_store import provision, client


def init_qdrant():
    return provision()


def get_qdrant_client():
    # Schema validation runs at startup, not on every keyword-only request.
    return client()
