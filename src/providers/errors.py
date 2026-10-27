"""Shared translation of provider failures into Gossip's domain exceptions.

The domain exceptions also inherit from the matching built-in exception (PermissionError,
FileNotFoundError, ValueError, RuntimeError), so callers may catch either.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Optional, Tuple, Type, Union

from src.exceptions import (
    PermissionDeniedError,
    ProviderError,
    ProviderOperationError,
    ResourceNotFoundError,
    SecretConflictError,
)
from src.i18n import _

DENIED = "denied"
MISSING = "missing"
CONFLICT = "conflict"
OTHER = "other"

_BY_KIND = {
    DENIED: PermissionDeniedError,
    MISSING: ResourceNotFoundError,
    CONFLICT: SecretConflictError,
    OTHER: ProviderOperationError,
}


def kind_for_status(status: int) -> str:
    """Classify an HTTP status code (0 means the server could not be reached)."""
    if status in (401, 403):
        return DENIED
    if status == 404:
        return MISSING
    if status == 409:
        return CONFLICT
    return OTHER


def provider_error(
    kind: str, message: str, provider: str, cause: Optional[BaseException] = None
) -> ProviderError:
    """Build the domain exception for ``kind`` (denied, missing, conflict or other).

    Args:
        kind: One of the module constants.
        message: Human-readable, already translated description.
        provider: Provider identifier the failure belongs to.
        cause: Original SDK exception, kept for diagnostics.
    """
    return _BY_KIND.get(kind, ProviderOperationError)(
        message, provider=provider, original_error=cause
    )


CONNECT_TIMEOUT = 10
READ_TIMEOUT = 30
RETRIES = 2


def guard_network(
    provider: str, service: str, network_errors: Tuple[Type[BaseException], ...], *methods: str
) -> Callable[[type], type]:
    """Class decorator: turn timeouts and connection failures of ``methods`` into a clear error.

    Without it a server that is down only surfaces the SDK's raw message after a long wait.

    Args:
        provider: Provider identifier.
        service: Human-readable service name used in the message.
        network_errors: SDK exception types that mean "could not reach / timed out".
        *methods: Names of the methods defined on the decorated class to wrap.
    """

    def wrap(method: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(method)
        def guarded(self: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                return method(self, *args, **kwargs)
            except network_errors as exc:
                raise provider_error(
                    OTHER,
                    _(
                        "{service} did not answer in time or could not be reached ({detail}). "
                        "Check your network connection and the endpoint, then try again."
                    ).format(service=service, detail=exc),
                    provider,
                    exc,
                ) from exc

        return guarded

    def decorate(cls: type) -> type:
        for name in methods:
            if name in cls.__dict__:
                setattr(cls, name, wrap(cls.__dict__[name]))
        return cls

    return decorate


Message = Union[str, Callable[[str], str]]

AWS_DENIED_CODES = ("AccessDeniedException", "UnauthorizedException")
AWS_MISSING_CODES = ("ResourceNotFoundException",)
AWS_CONFLICT_CODES = ("ResourceExistsException",)


def _text(message: Message, detail: str) -> str:
    """A fixed prefix gets the provider's detail appended; a callable builds the whole text."""
    return message(detail) if callable(message) else f"{message}: {detail}"


def _whole(message: Message, detail: str) -> str:
    """A complete message (used as is) or a callable that builds it from the detail."""
    return message(detail) if callable(message) else message


def client_failure(
    exc: BaseException,
    provider: str,
    *,
    denied: Message,
    other: Message,
    missing: Optional[Message] = None,
    conflict: Optional[Message] = None,
    denied_codes: Tuple[str, ...] = AWS_DENIED_CODES,
    missing_codes: Tuple[str, ...] = AWS_MISSING_CODES,
    conflict_codes: Tuple[str, ...] = AWS_CONFLICT_CODES,
) -> ProviderError:
    """Translate a botocore ``ClientError`` (error code in ``exc.response``).

    Args:
        exc: The ClientError.
        provider: Provider identifier.
        denied: Message for permission failures (prefix, or a callable receiving the detail).
        other: Message for any other failure.
        missing: Complete message when the code means "not found" (optional).
        conflict: Complete message when the code means "already exists" (optional).
        denied_codes: Error codes that mean permission denied.
        missing_codes: Error codes that mean not found.
        conflict_codes: Error codes that mean already exists.
    """
    error = getattr(exc, "response", {}).get("Error", {})
    code, detail = error.get("Code", ""), error.get("Message", str(exc))
    if code in denied_codes:
        return provider_error(DENIED, _text(denied, detail), provider, exc)
    if missing is not None and code in missing_codes:
        return provider_error(MISSING, _whole(missing, detail), provider, exc)
    if conflict is not None and code in conflict_codes:
        return provider_error(CONFLICT, _whole(conflict, detail), provider, exc)
    return provider_error(OTHER, _text(other, detail), provider, exc)


def status_failure(
    exc: BaseException,
    provider: str,
    *,
    status: Optional[int],
    detail: str,
    denied: Message,
    other: Message,
    missing: Optional[Message] = None,
) -> ProviderError:
    """Translate an HTTP-style failure by status code (Azure's ``HttpResponseError``).

    Args:
        exc: The original exception.
        provider: Provider identifier.
        status: HTTP status code (None counts as a failure with no code).
        detail: The service's message.
        denied: Message for 401 and 403.
        other: Message for any other failure.
        missing: Message for 404 (optional).
    """
    kind = kind_for_status(status or 0)
    if kind == DENIED:
        return provider_error(DENIED, _text(denied, detail), provider, exc)
    if kind == MISSING and missing is not None:
        return provider_error(MISSING, _whole(missing, detail), provider, exc)
    return provider_error(OTHER, _text(other, detail), provider, exc)
