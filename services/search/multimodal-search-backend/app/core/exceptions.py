from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

class MultimodalSearchException(Exception):
    def __init__(self, message: str, status_code: int = 500, details: dict = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class ResourceNotFoundException(MultimodalSearchException):
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            message=f"{resource_type} with ID '{resource_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource_type": resource_type, "resource_id": resource_id}
        )

class VectorSearchException(MultimodalSearchException):
    def __init__(self, message: str, details: dict = None):
        super().__init__(
            message=f"Vector search failed: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details
        )

class InvalidFilterException(MultimodalSearchException):
    def __init__(self, filter_name: str, message: str):
        super().__init__(
            message=f"Invalid filter parameter '{filter_name}': {message}",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"filter_name": filter_name}
        )

class VectorBackendUnavailableException(MultimodalSearchException):
    """
    Raised when the Qdrant vector backend cannot be reached in production.
    Must surface as a loud 503, never as a silent empty-result fallback -
    an empty in-memory Qdrant client returning zero hits is indistinguishable
    from "no matches" to the caller and corrupts search-quality metrics.
    """
    def __init__(self, message: str, details: dict = None):
        super().__init__(
            message=f"Vector search backend unavailable: {message}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={**(details or {}), "error_code": "VECTOR_BACKEND_UNAVAILABLE"}
        )

class CacheBackendUnavailableException(MultimodalSearchException):
    """
    Raised only when Redis is unreachable AND REDIS_FALLBACK_MEMORY=False,
    i.e. the operator has explicitly opted out of degraded in-memory caching.
    """
    def __init__(self, message: str, details: dict = None):
        super().__init__(
            message=f"Cache backend unavailable: {message}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={**(details or {}), "error_code": "CACHE_BACKEND_UNAVAILABLE"}
        )

async def multimodal_exception_handler(request: Request, exc: MultimodalSearchException):
    logger.error(f"Handled MultimodalSearchException: {exc.message} - details: {exc.details}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details,
            "path": str(request.url)
        }
    )
