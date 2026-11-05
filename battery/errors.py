"""Adapter failures shared by Battery workflow slices."""


class AdapterError(RuntimeError):
    def __init__(self, message, *, http_status=None):
        super().__init__(message)
        self.http_status = http_status


class AmbiguousTransport(AdapterError):
    """The request may have reached IRIS, but no response established outcome."""
