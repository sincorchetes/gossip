"""Discovery routines for AWS profiles and Secrets Manager supported regions."""

from __future__ import annotations

import os
from typing import Callable, List, Optional

import boto3
import botocore.session

COMMON_AWS_REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "eu-west-1",
    "eu-west-2",
    "eu-west-3",
    "eu-central-1",
    "eu-north-1",
    "eu-south-1",
    "sa-east-1",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
    "ap-northeast-2",
    "ap-south-1",
    "ca-central-1",
    "me-south-1",
    "af-south-1",
]


def list_available_profiles() -> List[str]:
    """List all configured AWS profiles available on the system.

    Returns:
        List[str]: Alphabetical list of configured profile names.
    """
    try:
        profiles = botocore.session.Session().available_profiles
        if not profiles:
            return ["default"]
        return sorted(list(set(profiles)))
    except Exception:
        return ["default"]


def list_available_regions() -> List[str]:
    """List standard AWS regions supported by Secrets Manager.

    Returns:
        List[str]: List of AWS region code strings.
    """
    try:
        sess = boto3.Session()
        regions = sess.get_available_regions("secretsmanager")
        if regions:
            return sorted(regions)
    except Exception:
        pass
    return COMMON_AWS_REGIONS


def detect_profile(list_profiles_fn: Optional[Callable[[], List[str]]] = None) -> str:
    """Detect active AWS credentials profile from environment variables or local configuration.

    Args:
        list_profiles_fn: Optional callable returning available profiles list.

    Returns:
        str: Detected profile name, defaulting to 'default'.
    """
    for var in ("AWS_PROFILE", "AWS_DEFAULT_PROFILE"):
        val = os.getenv(var)
        if val and val.strip():
            return val.strip()

    profile_getter = list_profiles_fn or list_available_profiles
    available = profile_getter()
    if "default" in available:
        return "default"
    elif available:
        return available[0]
    return "default"


def detect_region() -> str:
    """Detect active AWS target region from environment variables, session, or default.

    Returns:
        str: Detected region code, defaulting to 'us-east-1'.
    """
    for var in ("AWS_REGION", "AWS_DEFAULT_REGION"):
        val = os.getenv(var)
        if val and val.strip():
            return val.strip()

    try:
        sess = boto3.Session()
        if sess.region_name:
            return sess.region_name
    except Exception:
        pass

    return "us-east-1"
