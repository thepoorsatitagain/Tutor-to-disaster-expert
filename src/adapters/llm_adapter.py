"""
LLM Adapters — Model-agnostic interface for different backends.

Currently supported:
- Ollama (local)

Future:
- llama.cpp direct
- Cloud escalation (when network enabled)
"""

import json
import re
import requests
from typing import Optional, Any
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Configuration for an LLM adapter."""
    model: str
    base_url: str = "http://localhost:11434"
    timeout: int = 120
    default_temperature: float = 0.7
    default_max_tokens: int = 2048


class OllamaAdapter:
    """
    Adapter for Ollama local LLM server.
    
    Ollama must be running locally with a model pulled.
    """
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.base_url = config.base_url.rstrip('/')
    
    def is_available(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code != 200:
                return False
            
            data = response.json()
            models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
            return self.config.model.split(":")[0] in models
        except requests.RequestException:
            return False
    
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate a text response.
        
        Args:
            prompt: The user prompt
            system: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text
        """
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature or self.config.default_temperature,
                "num_predict": max_tokens or self.config.default_max_tokens
            }
        }
        
        if system:
            payload["system"] = system
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except requests.RequestException as e:
            raise RuntimeError(f"Ollama request failed: {str(e)}")
    
    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        schema: Optional[dict] = None,
        temperature: Optional[float] = None
    ) -> dict:
        """
        Generate a JSON response.
        
        Args:
            prompt: The user prompt (should ask for JSON output)
            system: Optional system prompt
            schema: Expected JSON schema (for validation, not enforced by Ollama)
            temperature: Sampling temperature
            
        Returns:
            Parsed JSON dict
        """
        # Add JSON instruction to system prompt
        json_system = system or ""
        json_system += "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no explanation, just the JSON object."
        
        raw = self.generate(
            prompt=prompt,
            system=json_system,
            temperature=temperature or 0.3,  # Lower temp for structured output
            max_tokens=self.config.default_max_tokens
        )
        
        # Try to extract JSON from response
        return self._parse_json(raw)
    
    def _parse_json(self, text: str) -> dict:
        """Extract and parse JSON from text."""
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON in markdown code blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON object in text
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # Last resort: return error structure
        return {
            "error": "Could not parse JSON from response",
            "raw": text[:500]
        }
    
    def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Chat completion with message history.
        
        Args:
            messages: List of {"role": "user"|"assistant", "content": "..."}
            system: Optional system prompt
            temperature: Sampling temperature
            
        Returns:
            Assistant response
        """
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature or self.config.default_temperature
            }
        }
        
        if system:
            payload["messages"] = [{"role": "system", "content": system}] + messages
        
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")
        except requests.RequestException as e:
            raise RuntimeError(f"Ollama chat request failed: {str(e)}")


class MockAdapter:
    """
    Mock adapter for testing without a real LLM.
    
    Returns predefined responses for testing the pipeline.
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig(model="mock")
        self._responses: list[str] = []
        self._json_responses: list[dict] = []
    
    def set_responses(self, responses: list[str]) -> None:
        """Set responses to return in order."""
        self._responses = responses.copy()
    
    def set_json_responses(self, responses: list[dict]) -> None:
        """Set JSON responses to return in order."""
        self._json_responses = responses.copy()
    
    def is_available(self) -> bool:
        return True
    
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        if self._responses:
            return self._responses.pop(0)
        return "Mock response for: " + prompt[:50]
    
    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        schema: Optional[dict] = None,
        temperature: Optional[float] = None
    ) -> dict:
        if self._json_responses:
            return self._json_responses.pop(0)
        return {
            "response": "Mock response",
            "confidence": 0.8,
            "citations": [],
            "reasoning": "Mock reasoning",
            "caveats": []
        }


def create_adapter(adapter_type: str, config: LLMConfig) -> Any:
    """
    Factory function to create an LLM adapter.
    
    Args:
        adapter_type: "ollama", "mock", etc.
        config: LLM configuration
        
    Returns:
        Configured adapter instance
    """
    adapters = {
        "ollama": OllamaAdapter,
        "mock": MockAdapter
    }
    
    adapter_class = adapters.get(adapter_type.lower())
    if not adapter_class:
        raise ValueError(f"Unknown adapter type: {adapter_type}")
    
    return adapter_class(config)


# Stub for future cloud escalation
class CloudEscalationAdapter:
    """
    Stub for cloud LLM escalation.
    
    Future implementation will route to cloud API when:
    - Local model can't answer
    - Policy allows escalation
    - Network is available
    """
    
    def __init__(self, config: LLMConfig, policy: Any = None):
        self.config = config
        self.policy = policy
    
    def is_available(self) -> bool:
        """Check if cloud escalation is available."""
        # Would check: policy allows, network available, API key configured
        return False
    
    def escalate(
        self,
        prompt: str,
        local_response: Optional[str] = None,
        reason: str = "unknown"
    ) -> str:
        """
        Escalate a query to cloud LLM.
        
        TODO: Implement actual cloud API call
        """
        raise NotImplementedError("Cloud escalation not yet implemented")
