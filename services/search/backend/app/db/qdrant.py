from modules.shared.vector_store import provision


def init_qdrant():
    return provision()


def get_qdrant_client():
    return provision()
