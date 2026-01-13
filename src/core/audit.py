"""
Audit Logger — Append-only event logging for compliance and debugging.

All sensitive operations are logged:
- Queries and responses
- Override attempts (success and failure)
- Mode changes
- Policy changes
- Key usage

The log is designed to be:
- Append-only (tamper-evident)
- Exportable (JSON lines format)
- Queryable (by time, type, session)
"""

import json
import hashlib
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum


class EventType(Enum):
    """Types of audit events."""
    # Query/Response
    QUERY = "query"
    RESPONSE = "response"
    PIPELINE_COMPLETE = "pipeline_complete"
    
    # Worker/Auditor
    WORKER_COMPLETE = "worker_complete"
    AUDITOR_COMPLETE = "auditor_complete"
    AUDITOR_SKIPPED = "auditor_skipped"
    RESOLVER_DECISION = "resolver_decision"
    
    # Keys/Overrides
    KEY_VALIDATION_SUCCESS = "key_validation_success"
    KEY_VALIDATION_FAILED = "key_validation_failed"
    OVERRIDE_SESSION_CREATED = "override_session_created"
    OVERRIDE_SESSION_EXPIRED = "override_session_expired"
    OVERRIDE_SESSION_REVOKED = "override_session_revoked"
    OVERRIDE_USED = "override_used"
    
    # Mode/Policy
    MODE_CHANGE = "mode_change"
    POLICY_LOADED = "policy_loaded"
    POLICY_CHANGED = "policy_changed"
    
    # Profile
    PROFILE_LOADED = "profile_loaded"
    PROFILE_CLEARED = "profile_cleared"
    
    # System
    STARTUP = "startup"
    SHUTDOWN = "shutdown"
    ERROR = "error"
    
    # RAO (future)
    RAO_BUNDLE_RECEIVED = "rao_bundle_received"
    RAO_BUNDLE_APPLIED = "rao_bundle_applied"
    RAO_BUNDLE_REJECTED = "rao_bundle_rejected"


@dataclass
class AuditEvent:
    """A single audit event."""
    timestamp: str
    event_type: str
    session_id: Optional[str]
    device_id: str
    details: dict
    checksum: str = ""
    previous_checksum: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class AuditLogger:
    """
    Append-only audit logger.
    
    Features:
    - Thread-safe logging
    - Checksum chain (tamper-evident)
    - JSON lines format for easy parsing
    - Configurable retention
    - Redaction support
    """
    
    def __init__(
        self,
        log_path: Path,
        device_id: str = "unknown",
        redaction_level: str = "standard"
    ):
        self.log_path = Path(log_path)
        self.device_id = device_id
        self.redaction_level = redaction_level
        self._lock = threading.Lock()
        self._last_checksum = "genesis"
        self._event_count = 0
        
        # Ensure log directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load last checksum if log exists
        if self.log_path.exists():
            self._load_last_checksum()
    
    def _load_last_checksum(self) -> None:
        """Load the last checksum from existing log."""
        try:
            last_line = None
            with open(self.log_path, 'r') as f:
                for line in f:
                    last_line = line
            if last_line:
                event = json.loads(last_line)
                self._last_checksum = event.get("checksum", "genesis")
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    
    def _compute_checksum(self, event: dict, previous: str) -> str:
        """Compute checksum for tamper evidence."""
        content = json.dumps(event, sort_keys=True) + previous
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _redact(self, details: dict) -> dict:
        """Apply redaction based on level."""
        if self.redaction_level == "none":
            return details
        
        redacted = details.copy()
        
        # Fields to potentially redact
        sensitive_fields = ["query", "response", "message"]
        
        if self.redaction_level in ["standard", "strict"]:
            # Truncate long text fields
            for field in sensitive_fields:
                if field in redacted and isinstance(redacted[field], str):
                    if len(redacted[field]) > 500:
                        redacted[field] = redacted[field][:500] + "...[truncated]"
        
        if self.redaction_level == "strict":
            # Hash sensitive fields instead of storing
            for field in sensitive_fields:
                if field in redacted and isinstance(redacted[field], str):
                    content = redacted[field]
                    redacted[field] = {
                        "redacted": True,
                        "hash": hashlib.sha256(content.encode()).hexdigest()[:16],
                        "length": len(content)
                    }
        
        return redacted
    
    def log(
        self,
        event_type: EventType | str,
        details: dict,
        session_id: Optional[str] = None
    ) -> AuditEvent:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event
            details: Event details (will be redacted based on policy)
            session_id: Optional session identifier
            
        Returns:
            The logged AuditEvent
        """
        with self._lock:
            # Normalize event type
            if isinstance(event_type, EventType):
                event_type_str = event_type.value
            else:
                event_type_str = event_type
            
            # Create event
            timestamp = datetime.utcnow().isoformat() + "Z"
            redacted_details = self._redact(details)
            
            event = AuditEvent(
                timestamp=timestamp,
                event_type=event_type_str,
                session_id=session_id,
                device_id=self.device_id,
                details=redacted_details,
                previous_checksum=self._last_checksum
            )
            
            # Compute checksum
            event_dict = event.to_dict()
            del event_dict["checksum"]  # Don't include checksum in its own computation
            event.checksum = self._compute_checksum(event_dict, self._last_checksum)
            
            # Write to log
            with open(self.log_path, 'a') as f:
                f.write(event.to_json() + "\n")
            
            # Update state
            self._last_checksum = event.checksum
            self._event_count += 1
            
            return event
    
    def query(
        self,
        event_types: Optional[list[str]] = None,
        session_id: Optional[str] = None,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> list[AuditEvent]:
        """
        Query the audit log.
        
        Args:
            event_types: Filter by event types
            session_id: Filter by session
            from_time: Start of time range
            to_time: End of time range
            limit: Maximum events to return
            
        Returns:
            List of matching AuditEvents
        """
        results = []
        
        if not self.log_path.exists():
            return results
        
        with open(self.log_path, 'r') as f:
            for line in f:
                if len(results) >= limit:
                    break
                
                try:
                    data = json.loads(line)
                    
                    # Apply filters
                    if event_types and data.get("event_type") not in event_types:
                        continue
                    
                    if session_id and data.get("session_id") != session_id:
                        continue
                    
                    if from_time:
                        event_time = datetime.fromisoformat(data["timestamp"].rstrip("Z"))
                        if event_time < from_time:
                            continue
                    
                    if to_time:
                        event_time = datetime.fromisoformat(data["timestamp"].rstrip("Z"))
                        if event_time > to_time:
                            continue
                    
                    results.append(AuditEvent(**data))
                    
                except (json.JSONDecodeError, KeyError):
                    continue
        
        return results
    
    def verify_integrity(self) -> tuple[bool, list[str]]:
        """
        Verify the integrity of the audit log.
        
        Returns:
            Tuple of (is_valid, list of issues found)
        """
        issues = []
        previous_checksum = "genesis"
        line_number = 0
        
        if not self.log_path.exists():
            return True, []
        
        with open(self.log_path, 'r') as f:
            for line in f:
                line_number += 1
                try:
                    data = json.loads(line)
                    
                    # Check previous checksum chain
                    if data.get("previous_checksum") != previous_checksum:
                        issues.append(f"Line {line_number}: Broken checksum chain")
                    
                    # Verify this event's checksum
                    stored_checksum = data.get("checksum", "")
                    data_copy = data.copy()
                    del data_copy["checksum"]
                    computed = self._compute_checksum(data_copy, data.get("previous_checksum", ""))
                    
                    if computed != stored_checksum:
                        issues.append(f"Line {line_number}: Checksum mismatch")
                    
                    previous_checksum = stored_checksum
                    
                except json.JSONDecodeError:
                    issues.append(f"Line {line_number}: Invalid JSON")
        
        return len(issues) == 0, issues
    
    def export(
        self,
        output_path: Path,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None
    ) -> int:
        """
        Export audit log to a file.
        
        Returns:
            Number of events exported
        """
        events = self.query(from_time=from_time, to_time=to_time, limit=100000)
        
        with open(output_path, 'w') as f:
            for event in events:
                f.write(event.to_json() + "\n")
        
        return len(events)
    
    def get_stats(self) -> dict:
        """Get statistics about the audit log."""
        if not self.log_path.exists():
            return {"events": 0, "size_bytes": 0}
        
        event_counts = {}
        total_events = 0
        
        with open(self.log_path, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    event_type = data.get("event_type", "unknown")
                    event_counts[event_type] = event_counts.get(event_type, 0) + 1
                    total_events += 1
                except json.JSONDecodeError:
                    pass
        
        return {
            "events": total_events,
            "size_bytes": self.log_path.stat().st_size,
            "by_type": event_counts,
            "integrity_verified": self.verify_integrity()[0]
        }


def create_audit_callback(logger: AuditLogger, session_id: Optional[str] = None):
    """Create a callback function for use with other components."""
    def callback(event_type: str, details: dict):
        logger.log(event_type, details, session_id)
    return callback
