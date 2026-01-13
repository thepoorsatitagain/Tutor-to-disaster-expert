"""
Profile Envelope — User adaptation and operator profiles.

The profile is a minimal "persona stub" for output shaping:
- Reading level
- Format preferences
- Language
- General permissions (not override keys)

Profiles can be loaded via:
- Manual input (current)
- QR code (future)
- Bluetooth (future)

The content semantics are admin/user-defined — we just provide the transport and validation.
"""

import json
import base64
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional, Any
from datetime import datetime
from enum import Enum


class ProfileFormat(Enum):
    """Output format preferences."""
    CONVERSATIONAL = "conversational"
    STRUCTURED = "structured"
    BULLET_POINTS = "bullet_points"
    STEP_BY_STEP = "step_by_step"
    BRIEF = "brief"
    DETAILED = "detailed"


@dataclass
class ProfileEnvelope:
    """
    Minimal profile for output adaptation.
    
    This is NOT for authorization — just for tailoring responses.
    Keys/overrides are handled separately.
    """
    # Identity (optional, for logging)
    profile_id: Optional[str] = None
    name: Optional[str] = None
    
    # Output shaping
    reading_level: str = "general"  # child, teen, general, technical, expert
    format_preference: str = "conversational"
    language: str = "en"
    
    # General permissions (not override keys)
    permissions: list[str] = field(default_factory=list)
    
    # Custom fields (admin-defined)
    custom: dict = field(default_factory=dict)
    
    # Metadata
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    signature: Optional[str] = None  # For signed profiles
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: dict) -> "ProfileEnvelope":
        """Create from dictionary."""
        return cls(
            profile_id=data.get("profile_id"),
            name=data.get("name"),
            reading_level=data.get("reading_level", "general"),
            format_preference=data.get("format_preference", "conversational"),
            language=data.get("language", "en"),
            permissions=data.get("permissions", []),
            custom=data.get("custom", {}),
            created_at=data.get("created_at"),
            expires_at=data.get("expires_at"),
            signature=data.get("signature")
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "ProfileEnvelope":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))
    
    def is_expired(self) -> bool:
        """Check if profile has expired."""
        if not self.expires_at:
            return False
        try:
            expires = datetime.fromisoformat(self.expires_at)
            return datetime.now() > expires
        except ValueError:
            return False
    
    def has_permission(self, permission: str) -> bool:
        """Check if profile has a general permission."""
        if "*" in self.permissions:
            return True
        return permission in self.permissions


@dataclass
class ProfileValidation:
    """Result of profile validation."""
    valid: bool
    profile: Optional[ProfileEnvelope] = None
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


class ProfileManager:
    """
    Manages profile loading, validation, and application.
    
    Supports multiple ingest methods (abstracted).
    """
    
    # Valid reading levels
    READING_LEVELS = ["child", "teen", "general", "technical", "expert"]
    
    # Valid format preferences
    FORMAT_PREFERENCES = [f.value for f in ProfileFormat]
    
    def __init__(self, policy: Optional[Any] = None):
        self.policy = policy
        self._current_profile: Optional[ProfileEnvelope] = None
        self._audit_callback = None
    
    def set_audit_callback(self, callback) -> None:
        """Set callback for audit logging."""
        self._audit_callback = callback
    
    def _audit(self, event_type: str, details: dict) -> None:
        """Log an audit event."""
        if self._audit_callback:
            self._audit_callback(event_type, details)
    
    @property
    def current_profile(self) -> Optional[ProfileEnvelope]:
        """Get current active profile."""
        return self._current_profile
    
    def validate(self, data: dict) -> ProfileValidation:
        """
        Validate profile data.
        
        Args:
            data: Profile data dictionary
            
        Returns:
            ProfileValidation result
        """
        warnings = []
        
        # Check reading level
        reading_level = data.get("reading_level", "general")
        if reading_level not in self.READING_LEVELS:
            warnings.append(f"Unknown reading level '{reading_level}', defaulting to 'general'")
            data["reading_level"] = "general"
        
        # Check format preference
        format_pref = data.get("format_preference", "conversational")
        if format_pref not in self.FORMAT_PREFERENCES:
            warnings.append(f"Unknown format '{format_pref}', defaulting to 'conversational'")
            data["format_preference"] = "conversational"
        
        # Create profile
        try:
            profile = ProfileEnvelope.from_dict(data)
        except Exception as e:
            return ProfileValidation(
                valid=False,
                error=f"Failed to parse profile: {str(e)}"
            )
        
        # Check expiration
        if profile.is_expired():
            return ProfileValidation(
                valid=False,
                error="Profile has expired"
            )
        
        # Check signature if required by policy
        if self.policy and self.policy.get("profile.require_signature", False):
            if not profile.signature:
                return ProfileValidation(
                    valid=False,
                    error="Profile signature required but not provided"
                )
            # Note: Actual signature verification would go here
            # For prototype, we just check presence
        
        return ProfileValidation(
            valid=True,
            profile=profile,
            warnings=warnings
        )
    
    def load(self, data: dict) -> ProfileValidation:
        """
        Load and activate a profile.
        
        Args:
            data: Profile data dictionary
            
        Returns:
            ProfileValidation result
        """
        validation = self.validate(data)
        
        if not validation.valid:
            self._audit("profile_load_failed", {
                "error": validation.error
            })
            return validation
        
        self._current_profile = validation.profile
        
        self._audit("profile_loaded", {
            "profile_id": validation.profile.profile_id,
            "reading_level": validation.profile.reading_level,
            "format_preference": validation.profile.format_preference
        })
        
        return validation
    
    def load_from_json(self, json_str: str) -> ProfileValidation:
        """Load profile from JSON string."""
        try:
            data = json.loads(json_str)
            return self.load(data)
        except json.JSONDecodeError as e:
            return ProfileValidation(
                valid=False,
                error=f"Invalid JSON: {str(e)}"
            )
    
    def load_from_qr(self, qr_data: str) -> ProfileValidation:
        """
        Load profile from QR code data.
        
        QR can contain:
        - Direct JSON
        - Base64-encoded JSON
        - Compact format (future)
        """
        # Try direct JSON first
        try:
            data = json.loads(qr_data)
            return self.load(data)
        except json.JSONDecodeError:
            pass
        
        # Try base64-encoded JSON
        try:
            decoded = base64.b64decode(qr_data).decode('utf-8')
            data = json.loads(decoded)
            return self.load(data)
        except Exception:
            pass
        
        return ProfileValidation(
            valid=False,
            error="Could not parse QR data as profile"
        )
    
    def clear(self) -> None:
        """Clear the current profile."""
        if self._current_profile:
            self._audit("profile_cleared", {
                "profile_id": self._current_profile.profile_id
            })
        self._current_profile = None
    
    def get_effective_reading_level(self, default: str = "general") -> str:
        """Get effective reading level (profile or default)."""
        if self._current_profile:
            if self.policy:
                if self.policy.get("output.allow_profile_override", True):
                    return self._current_profile.reading_level
            else:
                return self._current_profile.reading_level
        
        if self.policy:
            return self.policy.get("output.default_reading_level", default)
        
        return default
    
    def get_effective_format(self, default: str = "conversational") -> str:
        """Get effective format preference (profile or default)."""
        if self._current_profile:
            if self.policy:
                if self.policy.get("output.allow_profile_override", True):
                    return self._current_profile.format_preference
            else:
                return self._current_profile.format_preference
        
        if self.policy:
            return self.policy.get("output.default_format", default)
        
        return default
    
    def get_context(self) -> dict:
        """Get profile context for pipeline."""
        if not self._current_profile:
            return {
                "reading_level": self.get_effective_reading_level(),
                "format": self.get_effective_format(),
                "has_profile": False
            }
        
        return {
            "reading_level": self.get_effective_reading_level(),
            "format": self.get_effective_format(),
            "has_profile": True,
            "profile_id": self._current_profile.profile_id,
            "language": self._current_profile.language,
            "permissions": self._current_profile.permissions,
            "custom": self._current_profile.custom
        }
    
    def generate_qr_data(self, profile: ProfileEnvelope) -> str:
        """Generate QR-compatible data from a profile."""
        # Use compact JSON
        data = {
            "rl": profile.reading_level,
            "fmt": profile.format_preference,
            "lang": profile.language
        }
        
        if profile.profile_id:
            data["id"] = profile.profile_id
        
        if profile.permissions:
            data["perm"] = profile.permissions
        
        if profile.custom:
            data["cust"] = profile.custom
        
        return json.dumps(data, separators=(',', ':'))


# Stub for future QR decoder integration
class QRIngestAdapter:
    """
    Stub for QR code ingestion.
    
    Future implementation will use camera/scanner hardware.
    """
    
    def __init__(self, profile_manager: ProfileManager):
        self.profile_manager = profile_manager
    
    def decode_and_load(self, image_data: bytes) -> ProfileValidation:
        """
        Decode QR from image and load profile.
        
        TODO: Implement actual QR decoding (pyzbar, opencv, etc.)
        """
        # Stub - would use actual QR decoder
        return ProfileValidation(
            valid=False,
            error="QR decoding not yet implemented"
        )


# Stub for future Bluetooth integration
class BLEIngestAdapter:
    """
    Stub for Bluetooth Low Energy profile ingestion.
    
    Future implementation will use BLE hardware.
    """
    
    def __init__(self, profile_manager: ProfileManager):
        self.profile_manager = profile_manager
    
    def scan_and_load(self, timeout_seconds: int = 30) -> ProfileValidation:
        """
        Scan for BLE profile broadcast and load.
        
        TODO: Implement BLE scanning (bleak, etc.)
        """
        # Stub - would use actual BLE scanning
        return ProfileValidation(
            valid=False,
            error="BLE ingestion not yet implemented"
        )
