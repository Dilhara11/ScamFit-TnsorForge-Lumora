from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware

from svo_api.auth import Boundary
from svo_api.errors import APIError, error_response
from svo_api.routes import clusters, health, monitoring, predictions
from svo_api.services.engine import Engine
from svo_api.settings import Settings


def create_app(settings: Settings | None = None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        engine = Engine(settings)
        app.state.engine = engine
        try:
            await engine.start()
            yield
        finally:
            await engine.close()

    app = FastAPI(title='Scam Variant Observatory API', version='1.0.0', lifespan=lifespan,
                  docs_url=None, redoc_url=None, redirect_slashes=False,
                  description='Private unreviewed demonstration. Uncalibrated scores; lexical novelty.')
    app.state.settings = settings
    app.add_middleware(Boundary, settings=settings)
    if settings.allowed_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins),
                           allow_methods=['GET', 'POST'],
                           allow_headers=['Content-Type', 'Authorization', 'X-API-Key'],
                           expose_headers=['X-Request-ID'], allow_credentials=False)

    @app.exception_handler(APIError)
    async def api_error(request: Request, exc: APIError):
        return error_response(exc, request.state.request_id)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        malformed = any(e['type'] == 'json_invalid' for e in exc.errors())
        return error_response(APIError(400 if malformed else 422,
                                      'invalid_json' if malformed else 'invalid_request',
                                      'Malformed JSON body' if malformed else 'Request does not match the API schema'),
                              request.state.request_id)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error_response(APIError(exc.status_code, 'http_error',
                                      'Resource not found' if exc.status_code == 404 else 'Request is not supported',
                                      exc.headers), request.state.request_id)

    for router in (health.router, predictions.router, monitoring.router, clusters.router):
        app.include_router(router)

    @app.get('/docs', include_in_schema=False)
    async def docs():
        # Self-contained offline documentation; OpenAPI is also available to client generators.
        from starlette.responses import HTMLResponse
        return HTMLResponse('<!doctype html><html><head><title>SVO API</title></head><body>'
                            '<h1>Scam Variant Observatory API</h1><p>Private demonstration.</p>'
                            '<p>See the server README for examples and authentication. '
                            '<a href="/openapi.json">Download OpenAPI JSON</a>.</p></body></html>')

    original_openapi = app.openapi

    def openapi():
        schema = original_openapi()
        if settings.mode == 'authenticated':
            schema.setdefault('components', {}).setdefault('securitySchemes', {})['ApiKey'] = {
                'type': 'apiKey', 'in': 'header', 'name': 'X-API-Key'}
            for path, operations in schema['paths'].items():
                if path.startswith('/api/'):
                    for operation in operations.values():
                        operation['security'] = [{'ApiKey': []}]
        return schema

    app.openapi = openapi
    return app
