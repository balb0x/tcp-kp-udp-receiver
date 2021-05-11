from at_messages.base_response import BaseResponse


class InputStatusResponse(BaseResponse):
    def __init__(self, payload, address):
        super().__init__(payload, address)
        self.input_states = self.param.split(",")

    @staticmethod
    def get_header():
        return "+OCCH_ALL"
