"""
Dual-Model Pipeline — Worker/Auditor/Resolver orchestration.

This is the core intelligence layer:
1. WORKER generates a response with citations
2. AUDITOR reviews for safety, accuracy, scope
3. RESOLVER makes the final decision based on policy

The models can be:
- Same model, different prompts
- Different models entirely
- Same model, different temperatures
"""

import json
from dataclasses import dataclass, field
from typing import Optional, Protocol, Any
from enum import Enum
from datetime import datetime


class Verdict(Enum):
    """Auditor verdicts."""
    APPROVE = "approve"      # Response is good
    REVISE = "revise"        # Minor issues, can be fixed
    REJECT = "reject"        # Cannot be sent as-is
    ESCALATE = "escalate"    # Beyond local capability


class Flag(Enum):
    """Auditor flags for issues found."""
    SAFETY = "safety"                # Safety concern
    ACCURACY = "accuracy"            # Factual accuracy issue
    SCOPE = "scope"                  # Outside module scope
    CONFIDENCE = "confidence"        # Low confidence response
    CITATION = "citation"            # Missing or invalid citations
    READING_LEVEL = "reading_level"  # Doesn't match user level
    HARMFUL = "harmful"              # Potentially harmful advice


@dataclass
class WorkerOutput:
    """Structured output from the Worker model."""
    response: str
    citations: list[dict] = field(default_factory=list)
    confidence: float = 0.8
    reasoning: str = ""
    caveats: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "response": self.response,
            "citations": self.citations,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "caveats": self.caveats
        }


@dataclass
class AuditorOutput:
    """Structured output from the Auditor model."""
    verdict: Verdict
    flags: list[Flag] = field(default_factory=list)
    reasoning: str = ""
    suggested_revision: Optional[str] = None
    risk_level: str = "low"  # low, medium, high, critical
    
    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "flags": [f.value for f in self.flags],
            "reasoning": self.reasoning,
            "suggested_revision": self.suggested_revision,
            "risk_level": self.risk_level
        }


@dataclass
class ResolverDecision:
    """Final decision from the Resolver."""
    action: str  # "send", "send_with_caveat", "revise", "reject", "escalate"
    response: str
    caveats: list[str] = field(default_factory=list)
    audit_notes: str = ""
    override_available: bool = False
    override_scope: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "response": self.response,
            "caveats": self.caveats,
            "audit_notes": self.audit_notes,
            "override_available": self.override_available,
            "override_scope": self.override_scope
        }


class LLMAdapter(Protocol):
    """Protocol for LLM adapters — implement this for different backends."""
    
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """Generate a response from the model."""
        ...
    
    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        schema: Optional[dict] = None,
        temperature: float = 0.7
    ) -> dict:
        """Generate a JSON response from the model."""
        ...


class Pipeline:
    """
    Dual-model pipeline orchestrator.
    
    Manages the Worker → Auditor → Resolver flow with policy integration.
    """
    
    # JSON schema for Worker output
    WORKER_SCHEMA = {
        "type": "object",
        "properties": {
            "response": {"type": "string", "description": "The main response to the user"},
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "quote": {"type": "string"},
                        "relevance": {"type": "string"}
                    }
                }
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reasoning": {"type": "string"},
            "caveats": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["response"]
    }
    
    # JSON schema for Auditor output
    AUDITOR_SCHEMA = {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["approve", "revise", "reject", "escalate"]},
            "flags": {
                "type": "array",
                "items": {"type": "string", "enum": ["safety", "accuracy", "scope", "confidence", "citation", "reading_level", "harmful"]}
            },
            "reasoning": {"type": "string"},
            "suggested_revision": {"type": "string"},
            "risk_level": {"type": "string", "enum": ["low", "medium", "high", "critical"]}
        },
        "required": ["verdict", "reasoning"]
    }
    
    def __init__(
        self,
        worker_adapter: LLMAdapter,
        auditor_adapter: Optional[LLMAdapter] = None,
        policy: Optional[Any] = None
    ):
        """
        Initialize pipeline.
        
        Args:
            worker_adapter: LLM adapter for Worker model
            auditor_adapter: LLM adapter for Auditor (defaults to worker_adapter)
            policy: Policy instance for configuration
        """
        self.worker = worker_adapter
        self.auditor = auditor_adapter or worker_adapter
        self.policy = policy
        self._audit_callback = None
    
    def set_audit_callback(self, callback) -> None:
        """Set callback for audit logging."""
        self._audit_callback = callback
    
    def _audit(self, event_type: str, details: dict) -> None:
        """Log an audit event."""
        if self._audit_callback:
            self._audit_callback(event_type, details)
    
    def run(
        self,
        query: str,
        context: dict,
        worker_system: str,
        auditor_system: str
    ) -> ResolverDecision:
        """
        Run the full pipeline.
        
        Args:
            query: User's question
            context: Additional context (module, profile, etc.)
            worker_system: System prompt for Worker
            auditor_system: System prompt for Auditor
            
        Returns:
            ResolverDecision with final action
        """
        # Step 1: Worker generates response
        worker_output = self._run_worker(query, context, worker_system)
        
        self._audit("worker_complete", {
            "query": query[:200],
            "confidence": worker_output.confidence,
            "citation_count": len(worker_output.citations)
        })
        
        # Step 2: Check if auditor is required
        skip_auditor = (
            self.policy and 
            not self.policy.requires_auditor() and
            worker_output.confidence > 0.9
        )
        
        if skip_auditor:
            self._audit("auditor_skipped", {"reason": "policy + high confidence"})
            return ResolverDecision(
                action="send",
                response=worker_output.response,
                caveats=worker_output.caveats,
                audit_notes="Auditor skipped per policy (high confidence)"
            )
        
        # Step 3: Auditor reviews
        auditor_output = self._run_auditor(
            query, worker_output, context, auditor_system
        )
        
        self._audit("auditor_complete", {
            "verdict": auditor_output.verdict.value,
            "flags": [f.value for f in auditor_output.flags],
            "risk_level": auditor_output.risk_level
        })
        
        # Step 4: Resolver decides
        decision = self._resolve(worker_output, auditor_output, context)
        
        self._audit("resolver_decision", {
            "action": decision.action,
            "override_available": decision.override_available
        })
        
        return decision
    
    def _run_worker(
        self,
        query: str,
        context: dict,
        system_prompt: str
    ) -> WorkerOutput:
        """Run the Worker model."""
        
        # Build the prompt
        prompt = f"""## User Query
{query}

## Context
- Module: {context.get('module', 'general')}
- Mode: {context.get('mode', 'education')}
- Reading Level: {context.get('reading_level', 'general')}

## Knowledge Context
{context.get('knowledge', 'No specific knowledge loaded.')}

## Instructions
Respond to the user's query. Output valid JSON matching this structure:
{{
    "response": "Your response to the user",
    "citations": [
        {{"source": "document name", "quote": "relevant quote", "relevance": "why relevant"}}
    ],
    "confidence": 0.85,
    "reasoning": "Brief explanation of your reasoning",
    "caveats": ["Any important caveats or limitations"]
}}
"""
        
        try:
            result = self.worker.generate_json(
                prompt=prompt,
                system=system_prompt,
                schema=self.WORKER_SCHEMA,
                temperature=0.7
            )
            
            return WorkerOutput(
                response=result.get("response", ""),
                citations=result.get("citations", []),
                confidence=result.get("confidence", 0.5),
                reasoning=result.get("reasoning", ""),
                caveats=result.get("caveats", [])
            )
        except Exception as e:
            # Fallback for non-JSON response
            raw = self.worker.generate(prompt=prompt, system=system_prompt)
            return WorkerOutput(
                response=raw,
                confidence=0.5,
                reasoning="Fallback: could not parse structured output"
            )
    
    def _run_auditor(
        self,
        query: str,
        worker_output: WorkerOutput,
        context: dict,
        system_prompt: str
    ) -> AuditorOutput:
        """Run the Auditor model."""
        
        prompt = f"""## Original Query
{query}

## Worker Response
{json.dumps(worker_output.to_dict(), indent=2)}

## Context
- Module: {context.get('module', 'general')}
- Mode: {context.get('mode', 'education')}
- Reading Level: {context.get('reading_level', 'general')}
- Safety Profile: {context.get('safety_profile', 'standard')}

## Your Task
Review the Worker's response for:
1. SAFETY: Could this cause harm?
2. ACCURACY: Is the information correct?
3. SCOPE: Is this within the module's domain?
4. CONFIDENCE: Is the confidence level appropriate?
5. CITATIONS: Are sources properly cited?
6. READING LEVEL: Does it match the user's level?

Output valid JSON:
{{
    "verdict": "approve|revise|reject|escalate",
    "flags": ["safety", "accuracy", ...],
    "reasoning": "Detailed explanation of your review",
    "suggested_revision": "If verdict is 'revise', provide the revision here",
    "risk_level": "low|medium|high|critical"
}}
"""
        
        try:
            result = self.auditor.generate_json(
                prompt=prompt,
                system=system_prompt,
                schema=self.AUDITOR_SCHEMA,
                temperature=0.3  # Lower temp for more consistent auditing
            )
            
            return AuditorOutput(
                verdict=Verdict(result.get("verdict", "approve")),
                flags=[Flag(f) for f in result.get("flags", []) if f in [e.value for e in Flag]],
                reasoning=result.get("reasoning", ""),
                suggested_revision=result.get("suggested_revision"),
                risk_level=result.get("risk_level", "low")
            )
        except Exception as e:
            # Conservative fallback
            return AuditorOutput(
                verdict=Verdict.REVISE,
                flags=[Flag.CONFIDENCE],
                reasoning=f"Auditor error: {str(e)}. Flagging for review.",
                risk_level="medium"
            )
    
    def _resolve(
        self,
        worker: WorkerOutput,
        auditor: AuditorOutput,
        context: dict
    ) -> ResolverDecision:
        """
        Deterministic resolver logic.
        
        This is NOT a model — it's policy-driven decision making.
        """
        
        # Critical safety issues are always rejected
        if Flag.HARMFUL in auditor.flags or auditor.risk_level == "critical":
            return ResolverDecision(
                action="reject",
                response="I'm not able to help with that request.",
                audit_notes=f"Rejected: {auditor.reasoning}",
                override_available=self._can_override("safety_critical"),
                override_scope="safety_critical" if self._can_override("safety_critical") else None
            )
        
        # Handle by verdict
        if auditor.verdict == Verdict.APPROVE:
            return ResolverDecision(
                action="send",
                response=worker.response,
                caveats=worker.caveats,
                audit_notes="Approved by auditor"
            )
        
        elif auditor.verdict == Verdict.REVISE:
            # Use suggested revision if available
            if auditor.suggested_revision:
                return ResolverDecision(
                    action="send_with_caveat",
                    response=auditor.suggested_revision,
                    caveats=worker.caveats + [f"Note: {auditor.reasoning}"],
                    audit_notes=f"Revised: {auditor.reasoning}"
                )
            else:
                # Send original with caveat
                return ResolverDecision(
                    action="send_with_caveat",
                    response=worker.response,
                    caveats=worker.caveats + [f"Note: This response may have limitations. {auditor.reasoning}"],
                    audit_notes=f"Sent with caveat: {auditor.reasoning}"
                )
        
        elif auditor.verdict == Verdict.REJECT:
            return ResolverDecision(
                action="reject",
                response="I'm not confident I can answer that accurately. Please consult a qualified professional.",
                audit_notes=f"Rejected: {auditor.reasoning}",
                override_available=self._can_override("safety_override"),
                override_scope="safety_override" if self._can_override("safety_override") else None
            )
        
        elif auditor.verdict == Verdict.ESCALATE:
            return ResolverDecision(
                action="escalate",
                response="This question is beyond my current capabilities. It should be referred to a human expert.",
                audit_notes=f"Escalated: {auditor.reasoning}",
                override_available=False
            )
        
        # Fallback
        return ResolverDecision(
            action="send_with_caveat",
            response=worker.response,
            caveats=["This response has not been fully verified."],
            audit_notes="Fallback decision"
        )
    
    def _can_override(self, scope: str) -> bool:
        """Check if override is available for a scope."""
        if not self.policy:
            return False
        
        eval_result = self.policy.can_override_safety()
        return eval_result.allowed


# Prompt templates for Worker and Auditor
WORKER_SYSTEM_TEMPLATE = """You are a knowledgeable assistant operating as part of the Expert-in-a-Box system.

## Your Role
You are the WORKER model. Your job is to provide helpful, accurate responses to user queries.

## Current Module: {module}
## Current Mode: {mode}

## Guidelines
1. Stay within the scope of the active module
2. Cite sources when making factual claims
3. Be honest about uncertainty — set confidence appropriately
4. Adapt your language to the user's reading level: {reading_level}
5. Include relevant caveats for important limitations

## Safety
- Never provide information that could cause serious harm
- For medical/emergency topics, always recommend professional consultation
- Flag anything you're unsure about

## Output Format
Always respond with valid JSON containing: response, citations, confidence, reasoning, caveats
"""

AUDITOR_SYSTEM_TEMPLATE = """You are a careful reviewer operating as part of the Expert-in-a-Box system.

## Your Role  
You are the AUDITOR model. Your job is to review Worker responses for safety, accuracy, and appropriateness.

## Current Module: {module}
## Current Mode: {mode}
## Safety Profile: {safety_profile}

## Your Task
Review each Worker response and assess:

1. **SAFETY** — Could this response cause harm? Physical, psychological, financial?
2. **ACCURACY** — Is the information factually correct? Are claims supported?
3. **SCOPE** — Is this within the module's domain? Should it be referred elsewhere?
4. **CONFIDENCE** — Is the Worker's confidence level appropriate?
5. **CITATIONS** — Are sources cited? Are they relevant and reliable?
6. **READING LEVEL** — Does the response match the user's expected level?

## Verdicts
- **APPROVE**: Response is safe, accurate, and appropriate
- **REVISE**: Minor issues that can be fixed; provide suggested_revision
- **REJECT**: Significant issues; cannot be sent as-is
- **ESCALATE**: Beyond local capability; needs human expert

## Be Conservative
When in doubt, flag for review. It's better to ask for clarification than to let harmful information through.

## Output Format
Always respond with valid JSON containing: verdict, flags, reasoning, suggested_revision (if applicable), risk_level
"""
