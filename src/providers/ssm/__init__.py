"""AWS Systems Manager Parameter Store provider package."""

from src.providers.ssm.client import SSMClient

__all__ = ["SSMClient"]
