"""
Key Registry — Override key management with scopes and tiers.

Keys can be:
- Shared: One master key for everything
- Tiered: Different keys for different scopes
- Scoped: Each key has explicit capability scopes

All key operations are logged for audit.
"""

import json
import hashlib
import secrets
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable
from datetime import datetime, timedelta


@dataclass
class KeyEntry:
    """A registered key with its scopes."""
    id: str
    hash: str  # bcrypt or sha256 hash
    scopes: list[str]  # ["*"] for master, or specific scopes
    description: str = ""
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    
    def has_scope(self, scope: str) -> bool:
        """Check if this key grants the given scope."""
        if "*" in self.scopes:
            return True
        return scope in self.scopes
    
    def is_expired(self) -> bool:
        """Check if key has expired."""
        if not self.expires_at:
            return False
        try:
            expires = datetime.fromisoformat(self.expires_at)
            return datetime.now() > expires
        except ValueError:
            return False


@dataclass
class OverrideSession:
    """An active override session (time-boxed)."""
    key_id: str
    scope: str
    granted_at: datetime
    expires_at: datetime
    action: dict = field(default_factory=dict)
    
    def is_active(self) -> bool:
        return datetime.now() < self.expires_at


@dataclass
class KeyValidation:
    """Result of key validation."""
    valid: bool
    key_id: Optional[str] = None
    scopes: list[str] = field(default_factory=list)
    error: Optional[str] = None


class KeyRegistry:
    """
    Manages override keys with scope-based authorization.
    
    Supports:
    - Hash-based key storage (never stores plaintext)
    - Scope-limited authorization
    - Time-boxed override sessions
    - Audit logging hooks
    """
    
    # Default session duration for overrides
    DEFAULT_SESSION_DURATION = timedelta(minutes=15)
    
    def __init__(self, config_path: Optional[Path] = None):
        self._keys: dict[str, KeyEntry] = {}
        self._active_sessions: dict[str, OverrideSession] = {}
        self._audit_callback: Optional[Callable] = None
        
        if config_path:
            self.load(config_path)
    
    def set_audit_callback(self, callback: Callable) -> None:
        """Set callback for audit logging."""
        self._audit_callback = callback
    
    def _audit(self, event_type: str, details: dict) -> None:
        """Log an audit event."""
        if self._audit_callback:
            self._audit_callback(event_type, details)
    
    def load(self, config_path: Path) -> bool:
        """Load keys from JSON file."""
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
            
            self._keys = {}
            for key_data in data.get("keys", []):
                entry = KeyEntry(
                    id=key_data["id"],
                    hash=key_data["hash"],
                    scopes=key_data.get("scopes", []),
                    description=key_data.get("description", ""),
                    created_at=key_data.get("created_at"),
                    expires_at=key_data.get("expires_at")
                )
                self._keys[entry.id] = entry
            
            return True
        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            return False
    
    def load_dict(self, data: dict) -> bool:
        """Load keys from dictionary."""
        try:
            self._keys = {}
            for key_data in data.get("keys", []):
                entry = KeyEntry(
                    id=key_data["id"],
                    hash=key_data["hash"],
                    scopes=key_data.get("scopes", []),
                    description=key_data.get("description", ""),
                    created_at=key_data.get("created_at"),
                    expires_at=key_data.get("expires_at")
                )
                self._keys[entry.id] = entry
            return True
        except KeyError:
            return False
    
    @staticmethod
    def hash_key(plaintext: str) -> str:
        """
        Hash a plaintext key for storage.
        
        In production, use bcrypt. For prototype, SHA-256 is acceptable.
        """
        # For prototype — in production use bcrypt
        return hashlib.sha256(plaintext.encode()).hexdigest()
    
    @staticmethod
    def generate_key() -> tuple[str, str]:
        """Generate a new key and its hash. Returns (plaintext, hash)."""
        plaintext = secrets.token_urlsafe(32)
        hashed = KeyRegistry.hash_key(plaintext)
        return plaintext, hashed
    
    def validate(self, plaintext_key: str, required_scope: str) -> KeyValidation:
        """
        Validate a key and check if it grants the required scope.
        
        Args:
            plaintext_key: The key provided by the user
            required_scope: The scope needed for the operation
            
        Returns:
            KeyValidation with result
        """
        key_hash = self.hash_key(plaintext_key)
        
        # Find matching key
        for key_id, entry in self._keys.items():
            if entry.hash == key_hash:
                # Found matching key
                if entry.is_expired():
                    self._audit("key_validation_failed", {
                        "key_id": key_id,
                        "reason": "expired",
                        "required_scope": required_scope
                    })
                    return KeyValidation(
                        valid=False,
                        key_id=key_id,
                        error="Key has expired"
                    )
                
                if not entry.has_scope(required_scope):
                    self._audit("key_validation_failed", {
                        "key_id": key_id,
                        "reason": "insufficient_scope",
                        "required_scope": required_scope,
                        "available_scopes": entry.scopes
                    })
                    return KeyValidation(
                        valid=False,
                        key_id=key_id,
                        scopes=entry.scopes,
                        error=f"Key does not have scope: {required_scope}"
                    )
                
                # Success
                self._audit("key_validation_success", {
                    "key_id": key_id,
                    "scope": required_scope
                })
                return KeyValidation(
                    valid=True,
                    key_id=key_id,
                    scopes=entry.scopes
                )
        
        # No matching key found
        self._audit("key_validation_failed", {
            "reason": "no_match",
            "required_scope": required_scope
        })
        return KeyValidation(
            valid=False,
            error="Invalid key"
        )
    
    def create_override_session(
        self,
        plaintext_key: str,
        scope: str,
        action: dict,
        duration: Optional[timedelta] = None
    ) -> tuple[bool, Optional[OverrideSession], Optional[str]]:
        """
        Create a time-boxed override session.
        
        Args:
            plaintext_key: The key to authorize with
            scope: The scope for this override
            action: Details of what's being overridden
            duration: How long the session lasts
            
        Returns:
            Tuple of (success, session, error_message)
        """
        validation = self.validate(plaintext_key, scope)
        
        if not validation.valid:
            return False, None, validation.error
        
        now = datetime.now()
        expires = now + (duration or self.DEFAULT_SESSION_DURATION)
        
        session = OverrideSession(
            key_id=validation.key_id,
            scope=scope,
            granted_at=now,
            expires_at=expires,
            action=action
        )
        
        # Store session
        session_id = secrets.token_urlsafe(16)
        self._active_sessions[session_id] = session
        
        self._audit("override_session_created", {
            "session_id": session_id,
            "key_id": validation.key_id,
            "scope": scope,
            "action": action,
            "expires_at": expires.isoformat()
        })
        
        return True, session, None
    
    def check_session(self, session_id: str, scope: str) -> bool:
        """Check if an override session is still active for a scope."""
        session = self._active_sessions.get(session_id)
        if not session:
            return False
        
        if not session.is_active():
            # Clean up expired session
            del self._active_sessions[session_id]
            self._audit("override_session_expired", {
                "session_id": session_id
            })
            return False
        
        return session.scope == scope or session.scope == "*"
    
    def revoke_session(self, session_id: str) -> bool:
        """Revoke an override session."""
        if session_id in self._active_sessions:
            session = self._active_sessions[session_id]
            del self._active_sessions[session_id]
            self._audit("override_session_revoked", {
                "session_id": session_id,
                "key_id": session.key_id,
                "scope": session.scope
            })
            return True
        return False
    
    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions. Returns count of removed sessions."""
        expired = [
            sid for sid, session in self._active_sessions.items()
            if not session.is_active()
        ]
        
        for sid in expired:
            del self._active_sessions[sid]
        
        if expired:
            self._audit("sessions_cleanup", {"count": len(expired)})
        
        return len(expired)
    
    def list_keys(self) -> list[dict]:
        """List all registered keys (without hashes)."""
        return [
            {
                "id": entry.id,
                "scopes": entry.scopes,
                "description": entry.description,
                "expired": entry.is_expired()
            }
            for entry in self._keys.values()
        ]
    
    def export_template(self) -> dict:
        """Export a template for key configuration."""
        return {
            "keys": [
                {
                    "id": "example-master",
                    "hash": "<generate with KeyRegistry.hash_key('your-secret')>",
                    "scopes": ["*"],
                    "description": "Master override key"
                },
                {
                    "id": "example-mode",
                    "hash": "<hash>",
                    "scopes": ["mode_control"],
                    "description": "Mode switching only"
                },
                {
                    "id": "example-safety",
                    "hash": "<hash>",
                    "scopes": ["safety_override"],
                    "description": "Safety override only"
                }
            ]
        }
