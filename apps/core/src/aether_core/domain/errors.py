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


class EmptyBackupError(ValidationFailedError):
    """Não havia nada para salvar.

    Tem tipo próprio porque quem exige backup antes de uma operação de risco
    precisa distinguir "o backup falhou" (disco cheio, permissão) de "não havia
    o que salvar" — no segundo caso não há nada a perder, e recusar a operação
    criaria um impasse: não instala porque o backup falha, e o backup falha
    porque ainda não há instalação.
    """


class ContentFolderMissingError(ValidationFailedError):
    pass


class TargetExistsError(ConflictError):
    pass
