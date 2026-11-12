"""HTTP problem types shared by the JSON API and the page routes."""

from __future__ import annotations


class ApiProblem(Exception):
    """An error that maps directly onto an HTTP status plus a safe message."""

    def __init__(
        self,
        status: int,
        error: str,
        errors: dict[str, str] | None = None,
        message: str | None = None,
    ) -> None:
        super().__init__(error)
        self.status = status
        self.error = error
        self.errors = errors or {}
        self.message = message

    def payload(self) -> dict:
        body: dict = {"error": self.error}
        if self.message:
            body["message"] = self.message
        if self.errors:
            body["errors"] = self.errors
        return body


class ValidationFailed(ApiProblem):
    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__(422, "validation_failed", errors)


class NotFound(ApiProblem):
    def __init__(self, error: str = "not_found") -> None:
        super().__init__(404, error)
