"""Exception classes of ISC-IMG v1 (research/algorithm_design.md §11)."""


class ISCError(Exception):
    """Base class. Messages never contain secret-dependent detail."""


class InvalidKey(ISCError):
    """The key is not exactly 32 bytes of type bytes/bytearray."""


class InvalidImage(ISCError):
    """Unsupported dtype, shape, channel count or size."""


class Malformed(ISCError):
    """The ciphertext violates the format or a validation rule (§11.2 steps 2-5)."""


class AuthenticationError(ISCError):
    """Tag mismatch: tampering or wrong key (indistinguishable by design)."""


class ProfileError(ISCError):
    """The numerical profile is unsupported here or failed its self-test."""


class NumericalDivergenceError(ISCError):
    """Authenticated ciphertext, but the regenerated lane states do not match the KCV."""
