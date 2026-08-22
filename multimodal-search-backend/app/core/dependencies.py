from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client import QdrantClient

from app.db.postgres import get_db_session
from app.db.qdrant import get_qdrant_client
from app.clients.embedding_client import get_embedding_client, EmbeddingClient
from app.clients.metadata_client import get_metadata_client, MetadataClient
from app.clients.audit_client import get_audit_client, AuditClient
from app.clients.download_client import get_download_client, DownloadClient

from app.repositories.file_repository import FileRepository
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.search_repository import SearchRepository
from app.repositories.analytics_repository import AnalyticsRepository

from app.services.query_processor import get_query_processor, QueryProcessor
from app.services.text_search_service import TextSearchService
from app.services.vector_search_service import VectorSearchService
from app.services.similar_search_service import SimilarSearchService
from app.services.hybrid_search_service import HybridSearchService
from app.services.ranking_service import get_ranking_service, RankingService
from app.services.facet_service import FacetService
from app.services.metadata_service import MetadataService
from app.services.popular_dataset_service import PopularDatasetService
from app.services.trending_service import TrendingService
from app.services.event_service import EventService
from app.services.search_service import SearchService

# Repositories
def get_file_repository(db: AsyncSession = Depends(get_db_session)) -> FileRepository:
    return FileRepository(db)

def get_dataset_repository(db: AsyncSession = Depends(get_db_session)) -> DatasetRepository:
    return DatasetRepository(db)

def get_search_repository(db: AsyncSession = Depends(get_db_session)) -> SearchRepository:
    return SearchRepository(db)

def get_analytics_repository(db: AsyncSession = Depends(get_db_session)) -> AnalyticsRepository:
    return AnalyticsRepository(db)

# Services
def get_text_search_service(file_repo: FileRepository = Depends(get_file_repository)) -> TextSearchService:
    return TextSearchService(file_repo)

def get_vector_search_service(
    qdrant: QdrantClient = Depends(get_qdrant_client),
    embedder: EmbeddingClient = Depends(get_embedding_client)
) -> VectorSearchService:
    return VectorSearchService(qdrant, embedder)

def get_similar_search_service(
    qdrant: QdrantClient = Depends(get_qdrant_client),
    vector_service: VectorSearchService = Depends(get_vector_search_service),
    file_repo: FileRepository = Depends(get_file_repository)
) -> SimilarSearchService:
    return SimilarSearchService(qdrant, vector_service, file_repo)

def get_hybrid_search_service(
    text_service: TextSearchService = Depends(get_text_search_service),
    vector_service: VectorSearchService = Depends(get_vector_search_service)
) -> HybridSearchService:
    return HybridSearchService(text_service, vector_service)

def get_facet_service(file_repo: FileRepository = Depends(get_file_repository)) -> FacetService:
    return FacetService(file_repo)

def get_metadata_service(file_repo: FileRepository = Depends(get_file_repository)) -> MetadataService:
    return MetadataService(file_repo)

def get_popular_dataset_service(dataset_repo: DatasetRepository = Depends(get_dataset_repository)) -> PopularDatasetService:
    return PopularDatasetService(dataset_repo)

def get_trending_service(analytics_repo: AnalyticsRepository = Depends(get_analytics_repository)) -> TrendingService:
    return TrendingService(analytics_repo)

def get_event_service(
    analytics_repo: AnalyticsRepository = Depends(get_analytics_repository),
    file_repo: FileRepository = Depends(get_file_repository),
    dataset_repo: DatasetRepository = Depends(get_dataset_repository),
    audit_client: AuditClient = Depends(get_audit_client),
    download_client: DownloadClient = Depends(get_download_client)
) -> EventService:
    return EventService(analytics_repo, file_repo, dataset_repo, audit_client, download_client)

def get_search_service(
    query_processor: QueryProcessor = Depends(get_query_processor),
    hybrid_service: HybridSearchService = Depends(get_hybrid_search_service),
    text_service: TextSearchService = Depends(get_text_search_service),
    vector_service: VectorSearchService = Depends(get_vector_search_service),
    ranking_service: RankingService = Depends(get_ranking_service),
    metadata_service: MetadataService = Depends(get_metadata_service),
    facet_service: FacetService = Depends(get_facet_service),
    analytics_repo: AnalyticsRepository = Depends(get_analytics_repository)
) -> SearchService:
    return SearchService(
        query_processor=query_processor,
        hybrid_service=hybrid_service,
        text_service=text_service,
        vector_service=vector_service,
        ranking_service=ranking_service,
        metadata_service=metadata_service,
        facet_service=facet_service,
        analytics_repo=analytics_repo
    )
