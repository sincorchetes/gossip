from __future__ import annotations

import unittest

from src.exceptions import (
    PermissionDeniedError,
    ProviderError,
    ProviderOperationError,
    ResourceNotFoundError,
    SecretConflictError,
)
from src.providers import errors


class TestProviderErrors(unittest.TestCase):
    def test_status_classification(self):
        self.assertEqual(errors.kind_for_status(401), errors.DENIED)
        self.assertEqual(errors.kind_for_status(403), errors.DENIED)
        self.assertEqual(errors.kind_for_status(404), errors.MISSING)
        self.assertEqual(errors.kind_for_status(409), errors.CONFLICT)
        for status in (0, 400, 500):
            self.assertEqual(errors.kind_for_status(status), errors.OTHER)

    def test_domain_exceptions_are_also_builtin_ones(self):
        cause = KeyError("x")
        cases = [
            (errors.DENIED, PermissionDeniedError, PermissionError),
            (errors.MISSING, ResourceNotFoundError, FileNotFoundError),
            (errors.CONFLICT, SecretConflictError, ValueError),
            (errors.OTHER, ProviderOperationError, RuntimeError),
            ("unknown", ProviderOperationError, RuntimeError),
        ]
        for kind, domain, builtin in cases:
            exc = errors.provider_error(kind, "message", "aws", cause)
            self.assertIsInstance(exc, domain)
            self.assertIsInstance(exc, builtin)
            self.assertIsInstance(exc, ProviderError)
            self.assertEqual(
                (str(exc), exc.provider, exc.original_error), ("message", "aws", cause)
            )


class TestFailureHelpers(unittest.TestCase):
    def client_error(self, code, message="detail text"):
        from botocore.exceptions import ClientError

        return ClientError({"Error": {"Code": code, "Message": message}}, "Op")

    def test_client_failure_picks_the_exception_from_the_error_code(self):
        exc = self.client_error("AccessDeniedException")
        out = errors.client_failure(exc, "aws", denied="No permission", other="Failed")
        self.assertIsInstance(out, PermissionDeniedError)
        self.assertEqual(str(out), "No permission: detail text")  # prefix + the service's detail

        missing = errors.client_failure(
            self.client_error("ResourceNotFoundException"),
            "aws",
            denied="d",
            other="o",
            missing="Not there",
        )
        self.assertIsInstance(missing, ResourceNotFoundError)
        self.assertEqual(str(missing), "Not there")  # complete messages are used as they are

        conflict = errors.client_failure(
            self.client_error("ResourceExistsException"),
            "aws",
            denied="d",
            other="o",
            conflict="Exists",
        )
        self.assertIsInstance(conflict, SecretConflictError)

        other = errors.client_failure(
            self.client_error("Throttling"), "aws", denied="d", other="Failed"
        )
        self.assertIsInstance(other, ProviderOperationError)
        self.assertEqual(str(other), "Failed: detail text")

    def test_codes_without_a_message_for_them_fall_through_to_other(self):
        out = errors.client_failure(
            self.client_error("ResourceNotFoundException"), "aws", denied="d", other="Failed"
        )
        self.assertIsInstance(out, ProviderOperationError)

    def test_callables_build_the_whole_text_and_codes_can_be_overridden(self):
        out = errors.client_failure(
            self.client_error("ParameterNotFound", "gone"),
            "ssm",
            denied=lambda detail: f"denied {detail}",
            other=lambda detail: f"other {detail}",
            missing=lambda detail: f"missing {detail}",
            missing_codes=("ParameterNotFound",),
        )
        self.assertEqual(str(out), "missing gone")
        denied = errors.client_failure(
            self.client_error("Nope", "x"),
            "ssm",
            denied=lambda d: f"D {d}",
            other="o",
            denied_codes=("Nope",),
        )
        self.assertEqual(str(denied), "D x")

    def test_exceptions_without_a_response_are_still_handled(self):
        out = errors.client_failure(RuntimeError("plain"), "aws", denied="d", other="Failed")
        self.assertEqual(str(out), "Failed: plain")

    def test_status_failure(self):
        exc = RuntimeError("x")
        denied = errors.status_failure(
            exc, "azure", status=403, detail="why", denied="No", other="Bad"
        )
        self.assertIsInstance(denied, PermissionDeniedError)
        self.assertEqual(str(denied), "No: why")
        missing = errors.status_failure(
            exc, "azure", status=404, detail="why", denied="No", other="Bad", missing="Gone"
        )
        self.assertIsInstance(missing, ResourceNotFoundError)
        self.assertEqual(str(missing), "Gone")
        for status in (404, 500, None):  # 404 without a message, server errors, no code at all
            other = errors.status_failure(
                exc, "azure", status=status, detail="why", denied="No", other="Bad"
            )
            self.assertEqual(str(other), "Bad: why")
