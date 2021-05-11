class BaseResponse:
    def __init__(self, payload, address):
        payload = payload.replace('\r', '').replace('\n', '')
        parts = payload.split(":")
        self.action = parts[0]
        self.param = parts[1]
        self.ip = address[0]
        self.port = address[1]
        self.address = address

    @staticmethod
    def get_header():
        return ""
