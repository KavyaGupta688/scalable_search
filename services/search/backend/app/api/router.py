from fastapi import APIRouter
from app.api.routes import (
    search,
    text_search,
    vector_search,
    similar_search,
    facets,
    files,
    datasets,
    trending,
    suggestions,
    events,
    download_plan,
)

api_router = APIRouter()

# Register routes matching exact specifications in section 9 & 10 of design document
api_router.include_router(search.router, prefix="/search", tags=["Hybrid Search"])
api_router.include_router(text_search.router, prefix="/search/text", tags=["Keyword & Metadata Search"])
api_router.include_router(vector_search.router, prefix="/search/vector", tags=["Vector Similarity Search"])
api_router.include_router(similar_search.router, prefix="/search/similar", tags=["Similar File Search"])
api_router.include_router(facets.router, prefix="/search/facets", tags=["Faceted Search"])
api_router.include_router(download_plan.router, prefix="/search/download-plan", tags=["Download Planning"])
api_router.include_router(files.router, prefix="/files", tags=["File Metadata & Previews"])
api_router.include_router(datasets.router, prefix="/datasets", tags=["Popular Datasets"])
api_router.include_router(trending.router, prefix="/search/trending", tags=["Trending Searches"])
api_router.include_router(suggestions.router, prefix="/search/suggestions", tags=["Search Suggestions"])
api_router.include_router(events.router, prefix="/events", tags=["Search & Audit Events"])
