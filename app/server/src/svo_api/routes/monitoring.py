from fastapi import APIRouter, Request
from svo_api.schemas import Monitoring

router = APIRouter(prefix='/api/v1')


@router.get('/monitoring', response_model=Monitoring)
async def monitoring(request: Request):
    return await request.app.state.engine.call('monitoring')
