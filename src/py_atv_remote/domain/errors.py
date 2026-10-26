"""Domain-specific exceptions."""


class DomainError(Exception):
    """Base exception for py-atv-remote domain errors."""


class TvUnreachableError(DomainError):
    """Raised when an Android TV cannot be reached on the network."""


class TvNotFoundError(DomainError):
    """Raised when looking up a TV profile that does not exist."""


class PairingRequiredError(DomainError):
    """Raised when a TV requires pairing before accepting commands."""


class PairingFailedError(DomainError):
    """Raised when the pairing process fails."""


class InvalidPinError(PairingFailedError):
    """Raised when the user enters an invalid or incorrect PIN."""
