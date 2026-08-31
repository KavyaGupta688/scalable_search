import logging
import time
import random
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)

class TransientError(Exception):
    """Exception raised for infrastructure failures that should be retried."""
    pass

class DataQualityError(Exception):
    """Exception raised for data problems that should NOT be retried."""
    pass

def with_retry(
    fn: Callable, 
    *args: Any, 
    max_retries: int = 3, 
    backoff_base: float = 2.0, 
    **kwargs: Any
) -> Any:
    """
    Executes a function with retry logic for TransientError.
    Uses exponential backoff with jitter to prevent thundering herd.
    """
    attempt = 0
    while True:
        try:
            return fn(*args, **kwargs)
        except DataQualityError as e:
            # Do not retry on data quality issues
            logger.error(f"DataQualityError in {fn.__name__}: {str(e)}. Not retrying.")
            raise
        except TransientError as e:
            attempt += 1
            if attempt > max_retries:
                logger.error(f"TransientError in {fn.__name__} after {max_retries} retries: {str(e)}")
                raise
            
            # Exponential backoff + random jitter (0 to 1 second)
            delay = (backoff_base ** attempt) + random.uniform(0, 1.0)
            logger.warning(
                f"TransientError in {fn.__name__} (attempt {attempt}/{max_retries}). "
                f"Retrying in {delay:.2f} seconds. Error: {str(e)}"
            )
            time.sleep(delay)
        except Exception as e:
            # We only automatically retry TransientError
            logger.error(f"Unexpected error in {fn.__name__}: {str(e)}")
            raise

def retry_decorator(max_retries: int = 3, backoff_base: float = 2.0) -> Callable:
    """
    Decorator version of with_retry.
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return with_retry(
                fn, 
                *args, 
                max_retries=max_retries, 
                backoff_base=backoff_base, 
                **kwargs
            )
        return wrapper
    return decorator
