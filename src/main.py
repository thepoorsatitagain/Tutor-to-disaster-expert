"""
Expert-in-a-Box V2 — Main Application Entry Point

This is the orchestrator that ties everything together:
- Loads configuration
- Initializes components
- Starts the web UI
- Handles the query loop
"""

import os
import sys
import json
import secrets
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.policy import Policy, Mode
from core.keys import KeyRegistry
from core.audit import AuditLogger, EventType, create_audit_callback
from core.profile import ProfileManager
from core.packs import PackLoader
from core.pipeline import Pipeline, WORKER_SYSTEM_TEMPLATE, AUDITOR_SYSTEM_TEMPLATE
from adapters.llm_adapter import OllamaAdapter, LLMConfig, create_adapter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("expert-in-a-box")


class ExpertInABox:
    """
    Main application class.
    
    Orchestrates all components and provides the main interface.
    """
    
    def __init__(self, config_dir: Path = None, data_dir: Path = None):
        """
        Initialize Expert-in-a-Box.
        
        Args:
            config_dir: Directory containing policy.json, keys.json
            data_dir: Directory for logs, packs, etc.
        """
        self.base_dir = Path(__file__).parent.parent
        self.config_dir = config_dir or self.base_dir / "config"
        self.data_dir = data_dir or self.base_dir / "data"
        self.packs_dir = self.base_dir / "packs"
        
        # Ensure directories exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.packs_dir.mkdir(parents=True, exist_ok=True)
        
        # Components (initialized in setup())
        self.policy: Optional[Policy] = None
        self.keys: Optional[KeyRegistry] = None
        self.audit: Optional[AuditLogger] = None
        self.profile: Optional[ProfileManager] = None
        self.packs: Optional[PackLoader] = None
        self.pipeline: Optional[Pipeline] = None
        
        # LLM adapters
        self.worker_llm = None
        self.auditor_llm = None
        
        # Session tracking
        self._current_session_id = None
        self._initialized = False
    
    def setup(self) -> bool:
        """
        Initialize all components.
        
        Returns True if setup successful.
        """
        logger.info("Starting Expert-in-a-Box setup...")
        
        # 1. Load policy
        policy_path = self.config_dir / "policy.json"
        if not policy_path.exists():
            logger.warning("No policy.json found, creating default...")
            self._create_default_policy(policy_path)
        
        self.policy = Policy(policy_path)
        if not self.policy.is_valid:
            logger.error(f"Policy validation failed: {self.policy.violations}")
            return False
        
        logger.info(f"Policy loaded: device={self.policy.device_id}, mode={self.policy.current_mode.value}")
        
        # 2. Load keys
        keys_path = self.config_dir / "keys.json"
        if not keys_path.exists():
            logger.warning("No keys.json found, creating default...")
            self._create_default_keys(keys_path)
        
        self.keys = KeyRegistry(keys_path)
        logger.info(f"Keys loaded: {len(self.keys.list_keys())} keys registered")
        
        # 3. Initialize audit logger
        log_path = self.data_dir / "audit.jsonl"
        self.audit = AuditLogger(
            log_path=log_path,
            device_id=self.policy.device_id,
            redaction_level=self.policy.get_redaction_level().value
        )
        
        # Wire up audit callbacks
        audit_callback = create_audit_callback(self.audit, self._current_session_id)
        self.keys.set_audit_callback(audit_callback)
        
        logger.info(f"Audit logger initialized: {log_path}")
        
        # 4. Initialize profile manager
        self.profile = ProfileManager(self.policy)
        self.profile.set_audit_callback(audit_callback)
        
        # 5. Initialize pack loader
        self.packs = PackLoader(self.packs_dir, self.policy)
        self.packs.set_audit_callback(audit_callback)
        self.packs.discover()
        
        available_packs = self.packs.get_available()
        logger.info(f"Packs discovered: {list(available_packs.keys())}")
        
        # Load enabled packs
        for pack_id, config in self.policy.get("modules", {}).items():
            if config.get("loaded", False):
                pack = self.packs.load(pack_id)
                if pack:
                    logger.info(f"Pack loaded: {pack_id}")
        
        # 6. Initialize LLM adapters
        llm_config = LLMConfig(
            model=os.environ.get("EXPERT_MODEL", "llama3.2"),
            base_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
            timeout=120
        )
        
        try:
            self.worker_llm = create_adapter("ollama", llm_config)
            self.auditor_llm = create_adapter("ollama", llm_config)
            
            if self.worker_llm.is_available():
                logger.info(f"LLM adapter ready: {llm_config.model}")
            else:
                logger.warning(f"LLM not available: {llm_config.model} — using mock mode")
                self.worker_llm = create_adapter("mock", llm_config)
                self.auditor_llm = create_adapter("mock", llm_config)
        except Exception as e:
            logger.warning(f"LLM setup failed: {e} — using mock mode")
            self.worker_llm = create_adapter("mock", llm_config)
            self.auditor_llm = create_adapter("mock", llm_config)
        
        # 7. Initialize pipeline
        self.pipeline = Pipeline(
            worker_adapter=self.worker_llm,
            auditor_adapter=self.auditor_llm,
            policy=self.policy
        )
        self.pipeline.set_audit_callback(audit_callback)
        
        # Log startup
        self.audit.log(EventType.STARTUP, {
            "device_id": self.policy.device_id,
            "mode": self.policy.current_mode.value,
            "packs_loaded": list(self.packs.get_loaded().keys())
        })
        
        self._initialized = True
        logger.info("Expert-in-a-Box setup complete!")
        return True
    
    def _create_default_policy(self, path: Path) -> None:
        """Create a default policy file."""
        default_policy = {
            "device_id": f"device-{secrets.token_hex(4)}",
            "organization": "Default Organization",
            "deployment_context": "development",
            
            "mode": {
                "current": "education",
                "allowed": ["education", "emergency", "hybrid"],
                "switch_requires_key": True,
                "switch_key_scope": "mode_control"
            },
            
            "modules": {
                "education": {"enabled": True, "loaded": True},
                "medical": {"enabled": True, "loaded": False},
                "disaster": {"enabled": True, "loaded": False}
            },
            
            "safety": {
                "require_auditor": True,
                "auditor_strict": True,
                "allow_override_on_conflict": True,
                "override_requires_key": True,
                "override_key_scope": "safety_override",
                "redaction_level": "standard"
            },
            
            "output": {
                "adapt_to_profile": True,
                "default_reading_level": "general",
                "default_format": "conversational",
                "allow_profile_override": True
            },
            
            "sensors": {
                "video": {"enabled": False},
                "wearables": {"enabled": False},
                "audio": {"enabled": False}
            },
            
            "network": {
                "updates": {"enabled": False},
                "escalation": {"enabled": False},
                "telecom": {"enabled": False}
            },
            
            "rao": {
                "enabled": False,
                "transports": []
            },
            
            "audit": {
                "log_queries": True,
                "log_responses": True,
                "log_overrides": True,
                "log_mode_changes": True,
                "retention_days": 365
            }
        }
        
        with open(path, 'w') as f:
            json.dump(default_policy, f, indent=2)
    
    def _create_default_keys(self, path: Path) -> None:
        """Create a default keys file with a generated master key."""
        # Generate a master key
        master_key = secrets.token_urlsafe(32)
        master_hash = KeyRegistry.hash_key(master_key)
        
        default_keys = {
            "keys": [
                {
                    "id": "master-001",
                    "hash": master_hash,
                    "scopes": ["*"],
                    "description": "Master override key (auto-generated)"
                }
            ],
            "_generated_master_key": master_key,
            "_note": "SAVE THE MASTER KEY ABOVE! It will not be shown again."
        }
        
        with open(path, 'w') as f:
            json.dump(default_keys, f, indent=2)
        
        logger.warning(f"Generated master key: {master_key}")
        logger.warning("Save this key! It will not be shown again.")
    
    def new_session(self) -> str:
        """Start a new session."""
        self._current_session_id = secrets.token_urlsafe(16)
        return self._current_session_id
    
    def query(
        self,
        message: str,
        session_id: Optional[str] = None,
        module: Optional[str] = None
    ) -> dict:
        """
        Process a user query.
        
        Args:
            message: The user's question
            session_id: Session identifier (creates new if not provided)
            module: Specific module to use (auto-selects if not provided)
            
        Returns:
            Dict with response, caveats, audit info
        """
        if not self._initialized:
            return {"error": "System not initialized. Call setup() first."}
        
        # Session management
        if not session_id:
            session_id = self.new_session()
        
        # Log query
        self.audit.log(EventType.QUERY, {
            "message": message,
            "module": module
        }, session_id)
        
        # Determine module
        if not module:
            module = self._select_module(message)
        
        # Get pack
        pack = self.packs.get_pack(module)
        if not pack:
            # Try to load it
            pack = self.packs.load(module)
        
        if not pack:
            # Fall back to first loaded pack
            loaded = self.packs.get_loaded()
            if loaded:
                pack = list(loaded.values())[0]
                module = pack.id
        
        # Build context
        profile_ctx = self.profile.get_context()
        context = {
            "module": module or "general",
            "mode": self.policy.current_mode.value,
            "reading_level": profile_ctx.get("reading_level", "general"),
            "format": profile_ctx.get("format", "conversational"),
            "safety_profile": pack.manifest.safety_profile if pack else "standard",
            "knowledge": pack.get_knowledge_context(message) if pack else ""
        }
        
        # Build prompts
        if pack:
            worker_system = pack.get_worker_system(context["mode"], context["reading_level"])
            auditor_system = pack.get_auditor_system(context["mode"], context["reading_level"])
        else:
            worker_system = WORKER_SYSTEM_TEMPLATE.format(**context)
            auditor_system = AUDITOR_SYSTEM_TEMPLATE.format(**context)
        
        # Run pipeline
        decision = self.pipeline.run(
            query=message,
            context=context,
            worker_system=worker_system,
            auditor_system=auditor_system
        )
        
        # Log response
        self.audit.log(EventType.RESPONSE, {
            "action": decision.action,
            "response_length": len(decision.response),
            "caveats": decision.caveats
        }, session_id)
        
        return {
            "response": decision.response,
            "caveats": decision.caveats,
            "action": decision.action,
            "module": module,
            "mode": self.policy.current_mode.value,
            "session_id": session_id,
            "override_available": decision.override_available,
            "override_scope": decision.override_scope
        }
    
    def _select_module(self, message: str) -> str:
        """Select appropriate module based on message content."""
        # Simple keyword matching for now
        # Future: Use classifier model
        message_lower = message.lower()
        
        loaded = self.packs.get_loaded()
        
        # Check for emergency keywords
        emergency_keywords = ["emergency", "help", "urgent", "injury", "hurt", "bleeding", "disaster", "earthquake", "flood"]
        if any(kw in message_lower for kw in emergency_keywords):
            if "disaster" in loaded:
                return "disaster"
            if "medical" in loaded:
                return "medical"
        
        # Check for medical keywords
        medical_keywords = ["sick", "pain", "symptom", "medicine", "doctor", "health", "fever", "cough"]
        if any(kw in message_lower for kw in medical_keywords):
            if "medical" in loaded:
                return "medical"
        
        # Default to education or first loaded
        if "education" in loaded:
            return "education"
        
        if loaded:
            return list(loaded.keys())[0]
        
        return "general"
    
    def switch_mode(self, target_mode: str, key: Optional[str] = None) -> dict:
        """
        Switch operating mode.
        
        Args:
            target_mode: Mode to switch to
            key: Override key if required
            
        Returns:
            Result dict
        """
        try:
            target = Mode(target_mode)
        except ValueError:
            return {"success": False, "error": f"Invalid mode: {target_mode}"}
        
        # Check policy
        eval_result = self.policy.can_switch_mode(target)
        
        if not eval_result.allowed:
            return {"success": False, "error": eval_result.reason}
        
        if eval_result.requires_key:
            if not key:
                return {
                    "success": False,
                    "error": "Key required for mode switch",
                    "key_scope": eval_result.key_scope
                }
            
            validation = self.keys.validate(key, eval_result.key_scope)
            if not validation.valid:
                return {"success": False, "error": validation.error}
        
        # Update policy (in memory)
        # Note: Doesn't persist — would need to write back to file
        old_mode = self.policy.current_mode.value
        self.policy._config["mode"]["current"] = target_mode
        
        # Log mode change
        self.audit.log(EventType.MODE_CHANGE, {
            "from": old_mode,
            "to": target_mode,
            "key_used": eval_result.requires_key
        })
        
        return {
            "success": True,
            "mode": target_mode,
            "previous_mode": old_mode
        }
    
    def get_status(self) -> dict:
        """Get current system status."""
        if not self._initialized:
            return {"initialized": False}
        
        return {
            "initialized": True,
            "device_id": self.policy.device_id,
            "mode": self.policy.current_mode.value,
            "allowed_modes": [m.value for m in self.policy.allowed_modes],
            "modules": {
                name: {
                    "enabled": config.get("enabled", False),
                    "loaded": name in self.packs.get_loaded()
                }
                for name, config in self.policy.get("modules", {}).items()
            },
            "profile_active": self.profile.current_profile is not None,
            "llm_available": self.worker_llm.is_available() if self.worker_llm else False,
            "audit_stats": self.audit.get_stats()
        }
    
    def shutdown(self) -> None:
        """Clean shutdown."""
        if self.audit:
            self.audit.log(EventType.SHUTDOWN, {
                "device_id": self.policy.device_id if self.policy else "unknown"
            })
        logger.info("Expert-in-a-Box shutdown complete")


# CLI entry point
def main():
    """Command-line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Expert-in-a-Box V2")
    parser.add_argument("--config", type=Path, help="Config directory")
    parser.add_argument("--data", type=Path, help="Data directory")
    parser.add_argument("--web", action="store_true", help="Start web UI")
    parser.add_argument("--port", type=int, default=8080, help="Web UI port")
    
    args = parser.parse_args()
    
    # Initialize
    app = ExpertInABox(
        config_dir=args.config,
        data_dir=args.data
    )
    
    if not app.setup():
        logger.error("Setup failed!")
        sys.exit(1)
    
    if args.web:
        # Start web UI
        from ui.web import start_server
        start_server(app, port=args.port)
    else:
        # Interactive CLI
        print("\nExpert-in-a-Box V2 — Interactive Mode")
        print(f"Mode: {app.policy.current_mode.value}")
        print("Type 'quit' to exit, 'status' for system status\n")
        
        session_id = app.new_session()
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == 'quit':
                    break
                
                if user_input.lower() == 'status':
                    print(json.dumps(app.get_status(), indent=2))
                    continue
                
                result = app.query(user_input, session_id=session_id)
                
                print(f"\nAssistant: {result['response']}")
                
                if result.get('caveats'):
                    print(f"\n⚠️  {'; '.join(result['caveats'])}")
                
                print()
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
        
        app.shutdown()


if __name__ == "__main__":
    main()
