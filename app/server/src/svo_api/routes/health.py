from fastapi import APIRouter, Request
from svo_api.errors import APIError

router = APIRouter()


@router.get('/health/live')
async def live():
    return {'status': 'alive'}


@router.get('/health/ready')
async def ready(request: Request):
    engine = request.app.state.engine
    if not engine.ready or not engine.accepting:
        raise APIError(503, 'not_ready', 'Engine is not ready')
    return {'status': 'ready', 'model_version': engine.metadata['model_version']}
