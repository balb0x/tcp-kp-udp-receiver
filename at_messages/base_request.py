class BaseRequest:
    def __init__(self, payload):
        self.payload = payload + "\r\n"
