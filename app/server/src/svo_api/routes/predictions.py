from fastapi import APIRouter, Request
from svo_api.schemas import Prediction, PredictionRequest

router = APIRouter(prefix='/api/v1')


@router.get('/model')
async def model(request: Request):
    return request.app.state.engine.metadata


@router.post('/predictions', response_model=Prediction)
async def predict(body: PredictionRequest, request: Request):
    return await request.app.state.engine.call('predict', body)
