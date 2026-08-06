"""Configuration models for application runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


TRUTHY_VALUES = {"1", "true", "yes", "on"}
FALSY_VALUES = {"0", "false", "no", "off"}


class ConfigError(ValueError):
    """Raised when runtime configuration is invalid."""


@dataclass(frozen=True)
class AppConfig:
    input_dir: Path
    output_dir: Path
    lmstudio_base_url: str
    model_name: str
    enable_semantic_annotation: bool = True
    enable_debug_logging: bool = False

    @classmethod
    def from_mapping(cls, values: dict[str, object]) -> "AppConfig":
        return cls(
            input_dir=_required_path(values, "input_dir"),
            output_dir=_required_path(values, "output_dir"),
            lmstudio_base_url=_required_string(values, "lmstudio_base_url"),
            model_name=_required_string(values, "model_name"),
            enable_semantic_annotation=_optional_bool(
                values,
                "enable_semantic_annotation",
                default=True,
            ),
            enable_debug_logging=_optional_bool(
                values,
                "enable_debug_logging",
                default=False,
            ),
        )

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "AppConfig":
        env = environ or os.environ
        return cls.from_mapping(
            {
                "input_dir": env.get("NETWORK_MVP_INPUT_DIR"),
                "output_dir": env.get("NETWORK_MVP_OUTPUT_DIR"),
                "lmstudio_base_url": env.get("NETWORK_MVP_LMSTUDIO_BASE_URL"),
                "model_name": env.get("NETWORK_MVP_MODEL_NAME"),
                "enable_semantic_annotation": env.get(
                    "NETWORK_MVP_ENABLE_SEMANTIC_ANNOTATION"
                ),
                "enable_debug_logging": env.get("NETWORK_MVP_ENABLE_DEBUG_LOGGING"),
            }
        )


def _required_string(values: dict[str, object], key: str) -> str:
    raw_value = values.get(key)
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ConfigError(f"Missing required configuration value: {key}")
    return raw_value.strip()


def _required_path(values: dict[str, object], key: str) -> Path:
    raw_value = values.get(key)
    if isinstance(raw_value, Path):
        path = raw_value
    elif isinstance(raw_value, str) and raw_value.strip():
        path = Path(raw_value.strip())
    else:
        raise ConfigError(f"Missing required configuration value: {key}")
    return path.expanduser()


def _optional_bool(values: dict[str, object], key: str, default: bool) -> bool:
    raw_value = values.get(key)
    if raw_value is None:
        return default
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        normalized = raw_value.strip().lower()
        if normalized in TRUTHY_VALUES:
            return True
        if normalized in FALSY_VALUES:
            return False
    raise ConfigError(f"Invalid boolean configuration value for {key}: {raw_value!r}")
