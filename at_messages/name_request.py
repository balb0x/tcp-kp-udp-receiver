from at_messages.base_request import BaseRequest


class NameRequest(BaseRequest):
    def __init__(self):
        super().__init__("AT+NAME=?")
