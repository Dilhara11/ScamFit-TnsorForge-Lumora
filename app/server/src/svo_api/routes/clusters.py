from typing import Annotated
from fastapi import APIRouter, Path, Query, Request
from svo_api.errors import APIError
from svo_api.schemas import ClusterDetail, ClusterPage, ReviewPage, ReviewRequest, ReviewResult, ReviewStatus

router = APIRouter(prefix='/api/v1/clusters')
ClusterID = Annotated[int, Path(gt=0)]
Limit = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[int, Query(ge=0)]


@router.get('', response_model=ClusterPage)
async def clusters(request: Request, status: ReviewStatus | None = None, limit: Limit = 20, after_id: Cursor = 0):
    return await request.app.state.engine.call('clusters', status, limit, after_id)


@router.get('/{cluster_id}', response_model=ClusterDetail)
async def detail(cluster_id: ClusterID, request: Request):
    return await request.app.state.engine.call('detail', cluster_id)


@router.post('/{cluster_id}/reviews', response_model=ReviewResult)
async def review(cluster_id: ClusterID, body: ReviewRequest, request: Request):
    verified = request.app.state.settings.mode == 'authenticated'
    if verified and body.actor is not None:
        raise APIError(422, 'actor_not_allowed', 'Actor is derived from credentials')
    actor = request.state.actor if verified else body.actor or 'local-demo-analyst'
    return await request.app.state.engine.call('submit_review', cluster_id, body, actor, verified)


@router.get('/{cluster_id}/reviews', response_model=ReviewPage)
async def history(cluster_id: ClusterID, request: Request, limit: Limit = 20, after_id: Cursor = 0):
    return await request.app.state.engine.call('reviews', cluster_id, limit, after_id)
