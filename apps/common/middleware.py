from uuid import uuid4

MAX_REQUEST_ID_LENGTH = 128


class RequestIdMiddleware:
    header_name = "X-Request-ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = _request_id_or_new(request.headers.get(self.header_name))
        request.request_id = request_id

        response = self.get_response(request)
        response[self.header_name] = request_id

        return response


def _request_id_or_new(request_id: str | None) -> str:
    if not request_id:
        return str(uuid4())

    if len(request_id) > MAX_REQUEST_ID_LENGTH:
        return str(uuid4())

    if "\r" in request_id or "\n" in request_id:
        return str(uuid4())

    return request_id
