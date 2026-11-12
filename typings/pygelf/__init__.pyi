from logging import Handler

class GelfTcpHandler(Handler):
    def __init__(self, host: str, port: int, include_extra_fields: bool = ...) -> None: ...
