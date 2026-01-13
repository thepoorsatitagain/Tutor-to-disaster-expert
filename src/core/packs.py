"""
Pack Loader — Domain-specific capability bundles.

Packs contain:
- System prompts for Worker/Auditor
- Knowledge documents (for RAG)
- Safety profiles
- Metadata

Packs are discovered from the packs/ directory and loaded based on policy.
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class PackManifest:
    """Pack metadata and configuration."""
    id: str
    name: str
    version: str
    description: str
    modes: list[str] = field(default_factory=lambda: ["education"])
    reading_levels: list[str] = field(default_factory=lambda: ["general"])
    languages: list[str] = field(default_factory=lambda: ["en"])
    safety_profile: str = "standard"
    requires_auditor: bool = True
    
    @classmethod
    def from_dict(cls, data: dict) -> "PackManifest":
        return cls(
            id=data["id"],
            name=data["name"],
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            modes=data.get("modes", ["education"]),
            reading_levels=data.get("reading_levels", ["general"]),
            languages=data.get("languages", ["en"]),
            safety_profile=data.get("safety_profile", "standard"),
            requires_auditor=data.get("requires_auditor", True)
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "modes": self.modes,
            "reading_levels": self.reading_levels,
            "languages": self.languages,
            "safety_profile": self.safety_profile,
            "requires_auditor": self.requires_auditor
        }


@dataclass
class Pack:
    """A loaded capability pack."""
    manifest: PackManifest
    path: Path
    system_prompt: str = ""
    worker_prompt: str = ""
    auditor_prompt: str = ""
    knowledge_docs: list[dict] = field(default_factory=list)
    
    @property
    def id(self) -> str:
        return self.manifest.id
    
    @property
    def name(self) -> str:
        return self.manifest.name
    
    def get_worker_system(self, mode: str, reading_level: str) -> str:
        """Get Worker system prompt, customized for context."""
        return self.worker_prompt.format(
            module=self.name,
            mode=mode,
            reading_level=reading_level,
            safety_profile=self.manifest.safety_profile
        )
    
    def get_auditor_system(self, mode: str, reading_level: str) -> str:
        """Get Auditor system prompt, customized for context."""
        return self.auditor_prompt.format(
            module=self.name,
            mode=mode,
            reading_level=reading_level,
            safety_profile=self.manifest.safety_profile
        )
    
    def get_knowledge_context(self, query: str, max_docs: int = 5) -> str:
        """
        Get relevant knowledge for a query.
        
        TODO: Implement actual RAG/vector search.
        For now, returns all docs (truncated).
        """
        if not self.knowledge_docs:
            return "No specific knowledge loaded for this module."
        
        # Simple implementation: return first N docs
        # Future: vector similarity search
        context_parts = []
        for doc in self.knowledge_docs[:max_docs]:
            context_parts.append(f"### {doc.get('title', 'Document')}\n{doc.get('content', '')[:2000]}")
        
        return "\n\n".join(context_parts)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "manifest": self.manifest.to_dict(),
            "knowledge_doc_count": len(self.knowledge_docs)
        }


class PackLoader:
    """
    Discovers and loads capability packs.
    
    Packs are auto-discovered from the packs directory.
    Loading is controlled by policy.
    """
    
    # Default prompts if pack doesn't provide custom ones
    DEFAULT_WORKER_PROMPT = """You are a knowledgeable assistant for the {module} module.

## Current Mode: {mode}
## Reading Level: {reading_level}
## Safety Profile: {safety_profile}

Provide helpful, accurate information within your domain. Always:
1. Stay within scope of this module
2. Cite sources when making claims
3. Be honest about uncertainty
4. Adapt language to the reading level
5. Include safety caveats where appropriate

Output JSON with: response, citations, confidence, reasoning, caveats
"""

    DEFAULT_AUDITOR_PROMPT = """You are a safety reviewer for the {module} module.

## Current Mode: {mode}
## Reading Level: {reading_level}  
## Safety Profile: {safety_profile}

Review responses for:
1. Safety - could this cause harm?
2. Accuracy - is information correct?
3. Scope - is this within the module's domain?
4. Appropriateness - does it match reading level?

Output JSON with: verdict, flags, reasoning, suggested_revision, risk_level
"""

    def __init__(self, packs_dir: Path, policy: Optional[Any] = None):
        self.packs_dir = Path(packs_dir)
        self.policy = policy
        self._packs: dict[str, Pack] = {}
        self._available: dict[str, PackManifest] = {}
        self._audit_callback = None
    
    def set_audit_callback(self, callback) -> None:
        """Set callback for audit logging."""
        self._audit_callback = callback
    
    def _audit(self, event_type: str, details: dict) -> None:
        """Log an audit event."""
        if self._audit_callback:
            self._audit_callback(event_type, details)
    
    def discover(self) -> dict[str, PackManifest]:
        """
        Discover available packs in the packs directory.
        
        Returns dict of pack_id -> manifest
        """
        self._available = {}
        
        if not self.packs_dir.exists():
            return self._available
        
        for pack_path in self.packs_dir.iterdir():
            if not pack_path.is_dir():
                continue
            
            manifest_path = pack_path / "manifest.json"
            if not manifest_path.exists():
                continue
            
            try:
                with open(manifest_path, 'r') as f:
                    data = json.load(f)
                manifest = PackManifest.from_dict(data)
                self._available[manifest.id] = manifest
            except (json.JSONDecodeError, KeyError) as e:
                # Log but continue
                self._audit("pack_discovery_error", {
                    "path": str(pack_path),
                    "error": str(e)
                })
        
        return self._available
    
    def load(self, pack_id: str) -> Optional[Pack]:
        """
        Load a pack by ID.
        
        Args:
            pack_id: The pack identifier
            
        Returns:
            Loaded Pack or None if not found/loadable
        """
        # Check if already loaded
        if pack_id in self._packs:
            return self._packs[pack_id]
        
        # Check if available
        if pack_id not in self._available:
            self.discover()
        
        if pack_id not in self._available:
            return None
        
        manifest = self._available[pack_id]
        pack_path = self.packs_dir / pack_id
        
        # Load prompts
        system_prompt = self._load_file(pack_path / "system_prompt.md", "")
        worker_prompt = self._load_file(pack_path / "worker_prompt.md", self.DEFAULT_WORKER_PROMPT)
        auditor_prompt = self._load_file(pack_path / "auditor_prompt.md", self.DEFAULT_AUDITOR_PROMPT)
        
        # Load knowledge documents
        knowledge_docs = self._load_knowledge(pack_path / "knowledge")
        
        pack = Pack(
            manifest=manifest,
            path=pack_path,
            system_prompt=system_prompt,
            worker_prompt=worker_prompt,
            auditor_prompt=auditor_prompt,
            knowledge_docs=knowledge_docs
        )
        
        self._packs[pack_id] = pack
        
        self._audit("pack_loaded", {
            "pack_id": pack_id,
            "name": manifest.name,
            "version": manifest.version,
            "knowledge_docs": len(knowledge_docs)
        })
        
        return pack
    
    def _load_file(self, path: Path, default: str) -> str:
        """Load a text file or return default."""
        try:
            with open(path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            return default
    
    def _load_knowledge(self, knowledge_dir: Path) -> list[dict]:
        """Load knowledge documents from a directory."""
        docs = []
        
        if not knowledge_dir.exists():
            return docs
        
        for doc_path in knowledge_dir.iterdir():
            if doc_path.suffix not in ['.md', '.txt', '.json']:
                continue
            
            try:
                with open(doc_path, 'r') as f:
                    content = f.read()
                
                if doc_path.suffix == '.json':
                    # JSON docs have structure
                    doc_data = json.loads(content)
                    docs.append(doc_data)
                else:
                    # Text/markdown docs
                    docs.append({
                        "title": doc_path.stem.replace('_', ' ').title(),
                        "content": content,
                        "source": doc_path.name
                    })
            except Exception:
                continue
        
        return docs
    
    def unload(self, pack_id: str) -> bool:
        """Unload a pack from memory."""
        if pack_id in self._packs:
            del self._packs[pack_id]
            self._audit("pack_unloaded", {"pack_id": pack_id})
            return True
        return False
    
    def get_loaded(self) -> dict[str, Pack]:
        """Get all loaded packs."""
        return self._packs.copy()
    
    def get_available(self) -> dict[str, PackManifest]:
        """Get all available packs (discovered but not necessarily loaded)."""
        if not self._available:
            self.discover()
        return self._available.copy()
    
    def get_pack(self, pack_id: str) -> Optional[Pack]:
        """Get a loaded pack by ID."""
        return self._packs.get(pack_id)
    
    def get_pack_for_mode(self, mode: str) -> list[Pack]:
        """Get all loaded packs that support a given mode."""
        return [
            pack for pack in self._packs.values()
            if mode in pack.manifest.modes
        ]
    
    def create_pack_template(self, pack_id: str, name: str, description: str) -> Path:
        """
        Create a new pack template directory.
        
        Returns path to the created pack directory.
        """
        pack_path = self.packs_dir / pack_id
        pack_path.mkdir(parents=True, exist_ok=True)
        
        # Create manifest
        manifest = {
            "id": pack_id,
            "name": name,
            "version": "1.0.0",
            "description": description,
            "modes": ["education"],
            "reading_levels": ["child", "teen", "general", "technical"],
            "languages": ["en"],
            "safety_profile": "standard",
            "requires_auditor": True
        }
        
        with open(pack_path / "manifest.json", 'w') as f:
            json.dump(manifest, f, indent=2)
        
        # Create prompt templates
        with open(pack_path / "worker_prompt.md", 'w') as f:
            f.write(self.DEFAULT_WORKER_PROMPT)
        
        with open(pack_path / "auditor_prompt.md", 'w') as f:
            f.write(self.DEFAULT_AUDITOR_PROMPT)
        
        # Create knowledge directory
        (pack_path / "knowledge").mkdir(exist_ok=True)
        
        # Create example knowledge doc
        with open(pack_path / "knowledge" / "example.md", 'w') as f:
            f.write(f"# {name} Knowledge Base\n\nAdd your knowledge documents here.\n")
        
        return pack_path
    
    def export_pack_list(self) -> list[dict]:
        """Export list of all packs with status."""
        if not self._available:
            self.discover()
        
        result = []
        for pack_id, manifest in self._available.items():
            result.append({
                "id": pack_id,
                "name": manifest.name,
                "version": manifest.version,
                "description": manifest.description,
                "modes": manifest.modes,
                "loaded": pack_id in self._packs
            })
        
        return result
