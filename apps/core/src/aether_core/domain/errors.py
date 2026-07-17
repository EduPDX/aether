"""Domain errors. The HTTP layer maps these to status codes."""


class AetherError(Exception):
    """Base class for expected, user-facing errors."""


class NotFoundError(AetherError):
    pass


class AuthenticationError(AetherError):
    """Missing or invalid credentials (HTTP 401)."""


class ForbiddenError(AetherError):
    """Authenticated but not allowed (HTTP 403)."""


class ConflictError(AetherError):
    pass


class ValidationFailedError(AetherError):
    pass


class InstanceNotFoundError(NotFoundError):
    pass


class ProviderNotFoundError(NotFoundError):
    pass


class ContentTypeNotFoundError(NotFoundError):
    pass


class ContentFileNotFoundError(NotFoundError):
    pass


class ContentFolderMissingError(ValidationFailedError):
    pass


class TargetExistsError(ConflictError):
    pass
