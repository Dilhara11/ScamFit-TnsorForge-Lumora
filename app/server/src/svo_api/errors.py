from starlette.responses import JSONResponse


class APIError(Exception):
    def __init__(self, status, code, message, headers=None):
        self.status, self.code, self.message = status, code, message
        self.headers = headers or {}
        super().__init__(code)


def error_response(error, request_id):
    return JSONResponse({'error': {'code': error.code, 'message': error.message,
                                  'request_id': request_id}}, status_code=error.status,
                        headers={**error.headers, 'X-Request-ID': request_id})
