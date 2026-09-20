"""Bounded route labels; no URLs, identities or query text in Prometheus."""
import time
from prometheus_client import Histogram
from starlette.middleware.base import BaseHTTPMiddleware

DURATION = Histogram('platform_http_response_seconds', 'Time until gateway response headers',
                     ['route','method','status'], buckets=(.05,.1,.25,.5,1,2,5,10,30,60))


class HTTPMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        started = time.monotonic()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = getattr(request.scope.get('route'), 'path', 'unmatched')
            method = request.method if request.method in ('GET','POST','PUT','PATCH','DELETE','OPTIONS','HEAD') else 'OTHER'
            DURATION.labels(route, method, str(status)).observe(time.monotonic()-started)
