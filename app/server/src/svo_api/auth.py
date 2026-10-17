"""ASGI boundary: authentication precedes bounded body reads."""
import asyncio
import hmac
import json
import logging
import time
import uuid

from svo_api.errors import APIError, error_response

LOG = logging.getLogger('svo_api')


class Boundary:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_id = uuid.uuid4().hex
        scope.setdefault('state', {})['request_id'] = request_id
        started, status, sent = time.monotonic(), 500, False
        headers = {k.lower(): v for k, v in scope.get('headers', [])}

        async def wrapped_send(message):
            nonlocal status, sent
            if message['type'] == 'http.response.start':
                status, sent = message['status'], True
                message['headers'] = [(k, v) for k, v in message.get('headers', []) if k.lower() != b'x-request-id']
                message['headers'].append((b'x-request-id', request_id.encode()))
            await send(message)

        try:
            preflight = scope['method'] == 'OPTIONS' and b'access-control-request-method' in headers
            public = scope['path'] in ('/health/live', '/health/ready') or preflight
            actor = None
            if not public and self.settings.mode == 'authenticated':
                token = headers.get(b'authorization', b'')
                if token.startswith(b'Bearer '):
                    token = token[7:]
                else:
                    token = headers.get(b'x-api-key', b'')
                for alias, key in self.settings.credentials.items():
                    if hmac.compare_digest(token, key.encode('ascii')):
                        actor = alias
                if actor is None:
                    raise APIError(401, 'unauthorized', 'Valid API credentials required', {'WWW-Authenticate': 'Bearer'})
            scope['state']['actor'] = actor
            if scope['method'] in ('POST', 'PUT', 'PATCH'):
                media_type = headers.get(b'content-type', b'').split(b';', 1)[0].strip().lower()
                if media_type != b'application/json' or headers.get(b'content-encoding', b'identity').lower() != b'identity':
                    raise APIError(415, 'unsupported_media_type', 'Use uncompressed application/json')
                length = headers.get(b'content-length')
                if length is not None:
                    try:
                        size = int(length)
                    except ValueError:
                        raise APIError(400, 'invalid_length', 'Invalid Content-Length') from None
                    if size < 0:
                        raise APIError(400, 'invalid_length', 'Invalid Content-Length')
                    if size > self.settings.body_limit:
                        raise APIError(413, 'body_too_large', 'Request body exceeds 64 KiB')
                body = bytearray()
                try:
                    async with asyncio.timeout(10):
                        while True:
                            message = await receive()
                            if message['type'] == 'http.disconnect':
                                return
                            body.extend(message.get('body', b''))
                            if len(body) > self.settings.body_limit:
                                raise APIError(413, 'body_too_large', 'Request body exceeds 64 KiB')
                            if not message.get('more_body', False):
                                break
                except TimeoutError:
                    raise APIError(408, 'body_timeout', 'Request body timed out') from None
                # Reject nonstandard JSON constants and invalid UTF-8 before framework parsing.
                try:
                    json.loads(body.decode('utf-8'), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                except (ValueError, UnicodeError, RecursionError):
                    raise APIError(400, 'invalid_json', 'Malformed JSON body') from None
                delivered = False

                async def buffered_receive():
                    nonlocal delivered
                    if not delivered:
                        delivered = True
                        return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
                    return await receive()

                await self.app(scope, buffered_receive, wrapped_send)
            else:
                await self.app(scope, receive, wrapped_send)
        except APIError as exc:
            if not sent:
                await error_response(exc, request_id)(scope, receive, wrapped_send)
        except Exception:
            if not sent:
                await error_response(APIError(500, 'internal_error', 'Unexpected server error'), request_id)(scope, receive, wrapped_send)
        finally:
            # Route templates only: do not log user-controlled paths, queries, bodies or credentials.
            route = getattr(scope.get('route'), 'path', 'unmatched')
            LOG.info(json.dumps({'request_id': request_id, 'route': route, 'status': status,
                                 'duration_ms': round((time.monotonic()-started)*1000, 3)}))
