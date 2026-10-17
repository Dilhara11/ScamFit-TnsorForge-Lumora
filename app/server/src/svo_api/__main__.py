import logging
import uvicorn

logging.basicConfig(level=logging.INFO, format='%(message)s')
uvicorn.run('svo_api.main:create_app', factory=True, host='0.0.0.0', port=8000,
            workers=1, access_log=False, proxy_headers=False, timeout_graceful_shutdown=25)
