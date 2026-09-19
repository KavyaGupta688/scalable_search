"""Compatibility facade for ingestion document lookup.

The ingestion API, not direct reads of ingestion-owned tables, is now the
authoritative boundary for document metadata and source access.
"""

import asyncio

from modules.ai_tag_description_generation.app.ingestion_client import (
    IngestionDocument as SourceDocument,
    get_document,
)


def get_source_document(document_id: str) -> SourceDocument:
    return get_document(document_id)


async def get_source_document_async(document_id: str) -> SourceDocument:
    return await asyncio.to_thread(get_document, document_id)
