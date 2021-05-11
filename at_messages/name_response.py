from at_messages.base_response import BaseResponse


class NameResponse(BaseResponse):
    def __init__(self, payload, address):
        super().__init__(payload, address)
        self.name = self.param

    @staticmethod
    def get_header():
        return "+NAME"
