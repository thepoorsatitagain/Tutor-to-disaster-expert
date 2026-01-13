"""
Basic tests for Expert-in-a-Box core components.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.policy import Policy, Mode, PolicyEvaluation
from core.keys import KeyRegistry, KeyValidation
from core.audit import AuditLogger, EventType
from core.profile import ProfileManager, ProfileEnvelope
from core.packs import PackLoader, PackManifest


def test_policy_validation():
    """Test policy loading and validation."""
    policy = Policy()
    
    valid_config = {
        "device_id": "test-001",
        "mode": {
            "current": "education",
            "allowed": ["education", "emergency"]
        },
        "modules": {
            "education": {"enabled": True, "loaded": True}
        },
        "safety": {
            "require_auditor": True,
            "redaction_level": "standard"
        },
        "output": {
            "default_reading_level": "general"
        },
        "audit": {
            "log_queries": True
        }
    }
    
    assert policy.load_dict(valid_config) == True
    assert policy.device_id == "test-001"
    assert policy.current_mode == Mode.EDUCATION
    print("✓ Policy validation passed")


def test_key_hashing():
    """Test key hashing and validation."""
    plaintext = "test-secret-key"
    hash1 = KeyRegistry.hash_key(plaintext)
    hash2 = KeyRegistry.hash_key(plaintext)
    
    assert hash1 == hash2, "Same input should produce same hash"
    assert hash1 != plaintext, "Hash should differ from plaintext"
    print("✓ Key hashing passed")


def test_key_validation():
    """Test key validation with scopes."""
    registry = KeyRegistry()
    
    test_key = "my-secret-key"
    test_hash = KeyRegistry.hash_key(test_key)
    
    registry.load_dict({
        "keys": [
            {
                "id": "test-key",
                "hash": test_hash,
                "scopes": ["mode_control", "safety_override"]
            }
        ]
    })
    
    # Valid key, valid scope
    result = registry.validate(test_key, "mode_control")
    assert result.valid == True
    
    # Valid key, invalid scope
    result = registry.validate(test_key, "admin_override")
    assert result.valid == False
    
    # Invalid key
    result = registry.validate("wrong-key", "mode_control")
    assert result.valid == False
    
    print("✓ Key validation passed")


def test_profile_envelope():
    """Test profile creation and validation."""
    profile = ProfileEnvelope(
        profile_id="user-001",
        reading_level="teen",
        format_preference="conversational",
        language="en"
    )
    
    assert profile.reading_level == "teen"
    
    # Test serialization
    json_str = profile.to_json()
    loaded = ProfileEnvelope.from_json(json_str)
    assert loaded.reading_level == "teen"
    
    print("✓ Profile envelope passed")


def test_profile_manager():
    """Test profile manager."""
    manager = ProfileManager()
    
    result = manager.load({
        "reading_level": "child",
        "format_preference": "step_by_step"
    })
    
    assert result.valid == True
    assert manager.current_profile.reading_level == "child"
    
    print("✓ Profile manager passed")


def test_pack_manifest():
    """Test pack manifest parsing."""
    manifest_data = {
        "id": "test-pack",
        "name": "Test Pack",
        "version": "1.0.0",
        "description": "A test pack",
        "modes": ["education"],
        "safety_profile": "standard"
    }
    
    manifest = PackManifest.from_dict(manifest_data)
    assert manifest.id == "test-pack"
    assert manifest.safety_profile == "standard"
    
    print("✓ Pack manifest passed")


def run_all_tests():
    """Run all tests."""
    print("\n=== Expert-in-a-Box Core Tests ===\n")
    
    test_policy_validation()
    test_key_hashing()
    test_key_validation()
    test_profile_envelope()
    test_profile_manager()
    test_pack_manifest()
    
    print("\n=== All tests passed! ===\n")


if __name__ == "__main__":
    run_all_tests()
