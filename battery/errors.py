"""Adapter failures shared by Battery workflow slices."""


class AdapterError(RuntimeError):
    pass


class AmbiguousTransport(AdapterError):
    """The request may have reached IRIS, but no response established outcome."""
