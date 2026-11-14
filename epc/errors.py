class CatalogError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(CatalogError):
    pass


class InvalidRequestError(CatalogError):
    pass


class UnavailableError(CatalogError):
    pass
