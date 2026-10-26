"""Credential resolution without putting secrets in serializable settings."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Mapping

from .config import ConfigError


def resolve_credential(
    *,
    environment_name: str,
    credential_file: Path | str | None,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Resolve an environment or explicit credential-file secret safely."""

    environment = os.environ if environ is None else environ
    if credential_file is not None:
        path = Path(credential_file).expanduser()
        try:
            metadata = path.stat()
        except OSError as exc:
            raise ConfigError(validation_errors=[f"cannot access credential file: {exc.strerror}"]) from exc
        if not stat.S_ISREG(metadata.st_mode):
            raise ConfigError(validation_errors=["credential file must be a regular file"])
        if os.name == "posix" and metadata.st_mode & 0o077:
            raise ConfigError(
                validation_errors=["credential file must have owner-only permissions on POSIX systems"]
            )
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ConfigError(validation_errors=[f"cannot read credential file: {exc.strerror}"]) from exc
        if not value:
            raise ConfigError(validation_errors=["credential file is empty"])
        return value
    value = environment.get(environment_name, "").strip()
    if not value:
        raise ConfigError(missing_parameters=[f"credential environment variable {environment_name} or --credential-file"])
    return value
