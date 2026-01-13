"""
Policy Engine — The heart of the toggle-driven architecture.

Every capability is a toggle. Admins set these before deployment.
This module validates, loads, and evaluates policy configurations.
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class Mode(Enum):
    EDUCATION = "education"
    EMERGENCY = "emergency"
    HYBRID = "hybrid"


class ReadingLevel(Enum):
    CHILD = "child"
    TEEN = "teen"
    GENERAL = "general"
    TECHNICAL = "technical"
    EXPERT = "expert"


class RedactionLevel(Enum):
    NONE = "none"
    MINIMAL = "minimal"
    STANDARD = "standard"
    STRICT = "strict"


@dataclass
class PolicyViolation:
    """Represents a policy violation or validation error."""
    field: str
    message: str
    severity: str = "error"  # error, warning


@dataclass 
class PolicyEvaluation:
    """Result of evaluating whether an action is allowed."""
    allowed: bool
    requires_key: bool = False
    key_scope: Optional[str] = None
    reason: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


class Policy:
    """
    Policy configuration and evaluation.
    
    All toggles are capacity — we define what CAN be configured,
    not what SHOULD be configured. That's the admin's job.
    """
    
    # Schema definition — what toggles exist
    SCHEMA = {
        "device_id": {"type": str, "required": True},
        "organization": {"type": str, "required": False, "default": ""},
        "deployment_context": {"type": str, "required": False, "default": ""},
        
        "mode": {
            "type": dict,
            "required": True,
            "schema": {
                "current": {"type": str, "enum": ["education", "emergency", "hybrid"]},
                "allowed": {"type": list, "required": True},
                "switch_requires_key": {"type": bool, "default": True},
                "switch_key_scope": {"type": str, "default": "mode_control"}
            }
        },
        
        "modules": {
            "type": dict,
            "required": True,
            "dynamic_keys": True,  # Keys are module names
            "value_schema": {
                "enabled": {"type": bool, "default": False},
                "loaded": {"type": bool, "default": False}
            }
        },
        
        "safety": {
            "type": dict,
            "required": True,
            "schema": {
                "require_auditor": {"type": bool, "default": True},
                "auditor_strict": {"type": bool, "default": True},
                "allow_override_on_conflict": {"type": bool, "default": False},
                "override_requires_key": {"type": bool, "default": True},
                "override_key_scope": {"type": str, "default": "safety_override"},
                "redaction_level": {"type": str, "enum": ["none", "minimal", "standard", "strict"], "default": "standard"}
            }
        },
        
        "output": {
            "type": dict,
            "required": True,
            "schema": {
                "adapt_to_profile": {"type": bool, "default": True},
                "default_reading_level": {"type": str, "enum": ["child", "teen", "general", "technical", "expert"], "default": "general"},
                "default_format": {"type": str, "default": "conversational"},
                "allow_profile_override": {"type": bool, "default": True}
            }
        },
        
        "sensors": {
            "type": dict,
            "required": False,
            "schema": {
                "video": {"type": dict, "schema": {"enabled": {"type": bool, "default": False}}},
                "wearables": {"type": dict, "schema": {"enabled": {"type": bool, "default": False}}},
                "audio": {"type": dict, "schema": {"enabled": {"type": bool, "default": False}}}
            }
        },
        
        "network": {
            "type": dict,
            "required": False,
            "schema": {
                "updates": {"type": dict, "schema": {"enabled": {"type": bool, "default": False}}},
                "escalation": {"type": dict, "schema": {"enabled": {"type": bool, "default": False}}},
                "telecom": {"type": dict, "schema": {"enabled": {"type": bool, "default": False}}}
            }
        },
        
        "rao": {
            "type": dict,
            "required": False,
            "schema": {
                "enabled": {"type": bool, "default": False},
                "transports": {"type": list, "default": []}
            }
        },
        
        "audit": {
            "type": dict,
            "required": True,
            "schema": {
                "log_queries": {"type": bool, "default": True},
                "log_responses": {"type": bool, "default": True},
                "log_overrides": {"type": bool, "default": True},
                "log_mode_changes": {"type": bool, "default": True},
                "retention_days": {"type": int, "default": 365}
            }
        }
    }
    
    def __init__(self, config_path: Optional[Path] = None):
        self._config: dict[str, Any] = {}
        self._violations: list[PolicyViolation] = []
        
        if config_path:
            self.load(config_path)
    
    def load(self, config_path: Path) -> bool:
        """Load and validate policy from JSON file."""
        try:
            with open(config_path, 'r') as f:
                self._config = json.load(f)
            return self.validate()
        except json.JSONDecodeError as e:
            self._violations.append(PolicyViolation(
                field="<root>",
                message=f"Invalid JSON: {e}"
            ))
            return False
        except FileNotFoundError:
            self._violations.append(PolicyViolation(
                field="<root>",
                message=f"Policy file not found: {config_path}"
            ))
            return False
    
    def load_dict(self, config: dict[str, Any]) -> bool:
        """Load and validate policy from dictionary."""
        self._config = config
        return self.validate()
    
    def validate(self) -> bool:
        """Validate the loaded configuration against schema."""
        self._violations = []
        self._validate_object(self._config, self.SCHEMA, "")
        return len([v for v in self._violations if v.severity == "error"]) == 0
    
    def _validate_object(self, obj: Any, schema: dict, path: str) -> None:
        """Recursively validate an object against its schema."""
        if not isinstance(obj, dict):
            self._violations.append(PolicyViolation(
                field=path or "<root>",
                message=f"Expected object, got {type(obj).__name__}"
            ))
            return
        
        for key, spec in schema.items():
            field_path = f"{path}.{key}" if path else key
            
            if key not in obj:
                if spec.get("required", False):
                    self._violations.append(PolicyViolation(
                        field=field_path,
                        message="Required field missing"
                    ))
                continue
            
            value = obj[key]
            expected_type = spec.get("type")
            
            # Type check
            if expected_type and not isinstance(value, expected_type):
                self._violations.append(PolicyViolation(
                    field=field_path,
                    message=f"Expected {expected_type.__name__}, got {type(value).__name__}"
                ))
                continue
            
            # Enum check
            if "enum" in spec and value not in spec["enum"]:
                self._violations.append(PolicyViolation(
                    field=field_path,
                    message=f"Value must be one of: {spec['enum']}"
                ))
            
            # Nested schema
            if expected_type == dict and "schema" in spec:
                self._validate_object(value, spec["schema"], field_path)
            
            # Dynamic keys (like modules)
            if expected_type == dict and spec.get("dynamic_keys") and "value_schema" in spec:
                for sub_key, sub_value in value.items():
                    self._validate_object(sub_value, spec["value_schema"], f"{field_path}.{sub_key}")
    
    @property
    def violations(self) -> list[PolicyViolation]:
        """Get validation violations."""
        return self._violations
    
    @property
    def is_valid(self) -> bool:
        """Check if policy is valid (no errors)."""
        return len([v for v in self._violations if v.severity == "error"]) == 0
    
    # --- Accessors ---
    
    @property
    def device_id(self) -> str:
        return self._config.get("device_id", "unknown")
    
    @property
    def current_mode(self) -> Mode:
        mode_str = self._config.get("mode", {}).get("current", "education")
        return Mode(mode_str)
    
    @property
    def allowed_modes(self) -> list[Mode]:
        modes = self._config.get("mode", {}).get("allowed", ["education"])
        return [Mode(m) for m in modes]
    
    def get(self, path: str, default: Any = None) -> Any:
        """Get a config value by dot-notation path."""
        parts = path.split(".")
        value = self._config
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value
    
    # --- Evaluators ---
    
    def can_switch_mode(self, target_mode: Mode) -> PolicyEvaluation:
        """Evaluate whether mode switch is allowed."""
        if target_mode not in self.allowed_modes:
            return PolicyEvaluation(
                allowed=False,
                reason=f"Mode '{target_mode.value}' not in allowed modes"
            )
        
        requires_key = self.get("mode.switch_requires_key", True)
        key_scope = self.get("mode.switch_key_scope", "mode_control")
        
        return PolicyEvaluation(
            allowed=True,
            requires_key=requires_key,
            key_scope=key_scope if requires_key else None
        )
    
    def can_use_module(self, module_name: str) -> PolicyEvaluation:
        """Evaluate whether a module can be used."""
        module = self.get(f"modules.{module_name}")
        
        if module is None:
            return PolicyEvaluation(
                allowed=False,
                reason=f"Module '{module_name}' not configured"
            )
        
        if not module.get("enabled", False):
            return PolicyEvaluation(
                allowed=False,
                reason=f"Module '{module_name}' is disabled"
            )
        
        if not module.get("loaded", False):
            return PolicyEvaluation(
                allowed=False,
                reason=f"Module '{module_name}' is not loaded",
                warnings=["Module is enabled but not loaded — may need to load pack"]
            )
        
        return PolicyEvaluation(allowed=True)
    
    def can_override_safety(self) -> PolicyEvaluation:
        """Evaluate whether safety override is available."""
        if not self.get("safety.allow_override_on_conflict", False):
            return PolicyEvaluation(
                allowed=False,
                reason="Safety overrides are disabled"
            )
        
        requires_key = self.get("safety.override_requires_key", True)
        key_scope = self.get("safety.override_key_scope", "safety_override")
        
        return PolicyEvaluation(
            allowed=True,
            requires_key=requires_key,
            key_scope=key_scope if requires_key else None
        )
    
    def requires_auditor(self) -> bool:
        """Check if auditor model is required."""
        return self.get("safety.require_auditor", True)
    
    def get_reading_level(self, profile_level: Optional[str] = None) -> ReadingLevel:
        """Get effective reading level, considering profile override."""
        if profile_level and self.get("output.allow_profile_override", True):
            try:
                return ReadingLevel(profile_level)
            except ValueError:
                pass
        
        default = self.get("output.default_reading_level", "general")
        return ReadingLevel(default)
    
    def get_redaction_level(self) -> RedactionLevel:
        """Get current redaction level."""
        level = self.get("safety.redaction_level", "standard")
        return RedactionLevel(level)
    
    def to_dict(self) -> dict[str, Any]:
        """Export current configuration."""
        return self._config.copy()
    
    def export_status(self) -> dict[str, Any]:
        """Export a status summary for UI/API."""
        return {
            "device_id": self.device_id,
            "mode": self.current_mode.value,
            "allowed_modes": [m.value for m in self.allowed_modes],
            "modules": {
                name: {
                    "enabled": mod.get("enabled", False),
                    "loaded": mod.get("loaded", False)
                }
                for name, mod in self.get("modules", {}).items()
            },
            "safety": {
                "require_auditor": self.requires_auditor(),
                "redaction_level": self.get_redaction_level().value
            },
            "sensors": {
                name: sensor.get("enabled", False)
                for name, sensor in self.get("sensors", {}).items()
            },
            "network": {
                name: channel.get("enabled", False)
                for name, channel in self.get("network", {}).items()
            },
            "rao_enabled": self.get("rao.enabled", False)
        }
