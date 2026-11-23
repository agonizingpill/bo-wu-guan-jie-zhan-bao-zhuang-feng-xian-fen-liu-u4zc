import logging
import time
import uuid

from starlette.responses import JSONResponse

logger = logging.getLogger('museum.requests')


async def request_history(request, call_next):
    request_id = uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.monotonic()
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    logger.info('%s %s %s %.0fms %s', request.method, request.url.path, response.status_code,
                (time.monotonic() - started) * 1000, request_id)
    return response


async def application_errors(request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception('Request failed %s', request.state.request_id)
        return JSONResponse({'detail': '档案服务操作失败，请刷新后重试。', 'request_id': request.state.request_id}, 500)
