# Expert-in-a-Box V2

**Educator-to-Emergency Expert System**

A mission-agnostic, policy-driven, offline-first (online-capable) expert service designed for expertise deserts — remote communities, disaster zones, and anywhere specialists are scarce.

## Philosophy

This system has a **dual role**:

1. **Baseline Mode (Education/Tutor)** — Day-to-day community learning companion
2. **Emergency Mode** — Same trusted device transforms into triage assistant, safety guide, or whatever the positioning organization needs

The device builds community trust *before* a crisis, then leverages that relationship when it matters most.

## Core Principles

- **Capacity, not decisions** — We build toggle surfaces and capability enums. Mission-specific choices are made by admins who deploy the device.
- **Policy-driven** — Every safety option, capability, and behavior is a toggle set before deployment
- **Keyed overrides** — Tiered or shared keys unlock capabilities in the field
- **Audit everything** — Full trail of queries, responses, overrides, and mode changes
- **Model-agnostic** — Swap LLMs without changing the architecture
- **Offline-first, online-capable** — Works without connectivity, leverages it when available

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         INPUT CHANNELS                          │
├──────────┬──────────┬──────────┬──────────┬────────────────────┤
│ Text/Voice│  QR Code │ Bluetooth│  Video   │ Wearables/Sensors  │
│ (Primary) │ (Profile)│ (Profile)│ (Future) │ (Future)           │
└─────┬─────┴────┬─────┴────┬─────┴────┬─────┴─────────┬──────────┘
      │          │          │          │               │
      ▼          ▼          ▼          ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      INGEST ABSTRACTION                         │
│  (Unified interface for all input types, policy-gated)          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       POLICY ENGINE                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Toggles   │  │ Key Registry│  │   Profile Envelope      │  │
│  │ (capabilities)│ │ (overrides) │  │ (user adaptation)       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MODULE PACK SYSTEM                           │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐       │
│  │ Education │ │  Medical  │ │ Disaster  │ │Agriculture│  ...  │
│  │   Pack    │ │   Pack    │ │   Pack    │ │   Pack    │       │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 DUAL-MODEL PIPELINE                             │
│                                                                 │
│  ┌─────────┐    ┌─────────┐    ┌──────────┐    ┌─────────┐     │
│  │ WORKER  │───▶│ AUDITOR │───▶│ RESOLVER │───▶│ OUTPUT  │     │
│  │ (Generate)   │ (Verify) │    │(Decide)  │    │         │     │
│  └─────────┘    └─────────┘    └──────────┘    └─────────┘     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      OUTPUT ADAPTATION                          │
│  (Reading level, format, language based on profile)             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       AUDIT LOG                                 │
│  (Append-only, tamper-evident, exportable)                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## V1 Prototype (This Release)

### ✅ Implemented

- **Policy Engine** — JSON-based toggle system with validation
- **Key Registry** — Override key management with scopes and tiers
- **Dual-Model Pipeline** — Worker/Auditor/Resolver orchestration
- **LLM Adapter Interface** — Model-agnostic, supports Ollama out of the box
- **Pack Loader** — Load domain-specific prompt packs
- **Profile Envelope** — User adaptation (reading level, format preferences)
- **Audit Logger** — Append-only event logging
- **Web UI** — Local browser-based interface
- **Mode Switching** — Education ↔ Emergency toggle

### 🔲 Specified But Not Yet Implemented

These are fully specified in the codebase with interfaces and schemas ready for implementation:

#### Sensor Inputs (Future Phase)
```yaml
video_ingest:
  description: Camera/webcam/drone feed processing
  interface: src/adapters/sensor_adapter.py (stub)
  use_cases:
    - Injury assessment
    - Environmental hazard ID
    - Document/label reading
  toggle: policy.sensors.video.enabled

wearable_ingest:
  description: Smartwatch/health device data
  interface: src/adapters/sensor_adapter.py (stub)
  use_cases:
    - Heart rate monitoring
    - SpO2 levels
    - Fall detection
    - GPS coordinates
  toggle: policy.sensors.wearables.enabled

audio_ingest:
  description: Voice input beyond text transcription
  interface: src/adapters/sensor_adapter.py (stub)
  use_cases:
    - Ambient sound analysis
    - Distress detection
  toggle: policy.sensors.audio.enabled
```

#### Remote Access Override — RAO (Future Phase)
```yaml
rao_system:
  description: Remote policy updates post-deployment
  interface: src/core/rao.py (stub)
  transports:
    - internet (HTTPS pull/push)
    - SMS/telecom
    - emergency broadcast (receive-only)
    - satellite (future)
  capabilities:
    - Toggle policy changes
    - Unlock/lock module packs
    - Push new packs
    - Key rotation
  security:
    - Ed25519 signed bundles
    - Sequence numbers (anti-replay)
    - Atomic apply with rollback
  toggle: policy.rao.enabled
```

#### Connectivity Channels (Future Phase)
```yaml
connectivity:
  description: Online capabilities when available
  interface: src/adapters/network_adapter.py (stub)
  channels:
    updates:
      description: Pull pack/model updates
      toggle: policy.network.updates.enabled
    escalation:
      description: Route queries to cloud LLM when local can't answer
      toggle: policy.network.escalation.enabled
    telecom:
      description: Connect to human experts via call/SMS
      toggle: policy.network.telecom.enabled
  philosophy: Local-first, explicit escalation, full audit
```

#### QR/Bluetooth Profile Ingest (Partial)
```yaml
profile_ingest:
  qr:
    status: Schema defined, decoder not implemented
    interface: src/adapters/profile_adapter.py
  bluetooth:
    status: Schema defined, BLE not implemented
    interface: src/adapters/profile_adapter.py
```

---

## Installation

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai) installed and running (or another supported LLM backend)
- A compatible model pulled (e.g., `ollama pull llama3.2` or `ollama pull llama3.2:1b` for smaller devices)

### Setup

```bash
# Clone or extract the project
cd expert-in-a-box-v2

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy example config
cp config/policy.example.json config/policy.json
cp config/keys.example.json config/keys.json

# Edit config/policy.json to set your toggles
# Edit config/keys.json to set your override keys

# Run the server
python -m src.main
```

Open `http://localhost:8080` in your browser.

---

## Configuration

### Policy Schema (`config/policy.json`)

Every capability is a toggle. Admins set these before deployment.

```json
{
  "device_id": "device-001",
  "organization": "Example Org",
  "deployment_context": "remote-education",
  
  "mode": {
    "current": "education",
    "allowed": ["education", "emergency", "hybrid"],
    "switch_requires_key": true,
    "switch_key_scope": "mode_control"
  },
  
  "modules": {
    "education": { "enabled": true, "loaded": true },
    "medical": { "enabled": true, "loaded": false },
    "disaster": { "enabled": true, "loaded": false },
    "agriculture": { "enabled": false, "loaded": false }
  },
  
  "safety": {
    "require_auditor": true,
    "auditor_strict": true,
    "allow_override_on_conflict": true,
    "override_requires_key": true,
    "override_key_scope": "safety_override",
    "redaction_level": "standard"
  },
  
  "output": {
    "adapt_to_profile": true,
    "default_reading_level": "general",
    "default_format": "conversational",
    "allow_profile_override": true
  },
  
  "sensors": {
    "video": { "enabled": false },
    "wearables": { "enabled": false },
    "audio": { "enabled": false }
  },
  
  "network": {
    "updates": { "enabled": false },
    "escalation": { "enabled": false },
    "telecom": { "enabled": false }
  },
  
  "rao": {
    "enabled": false,
    "transports": []
  },
  
  "audit": {
    "log_queries": true,
    "log_responses": true,
    "log_overrides": true,
    "log_mode_changes": true,
    "retention_days": 365
  }
}
```

### Key Registry (`config/keys.json`)

Keys can be shared (one key for everything) or tiered (different keys for different scopes).

```json
{
  "keys": [
    {
      "id": "master-001",
      "hash": "<bcrypt hash>",
      "scopes": ["*"],
      "description": "Master override key"
    },
    {
      "id": "mode-001",
      "hash": "<bcrypt hash>",
      "scopes": ["mode_control"],
      "description": "Mode switching only"
    },
    {
      "id": "safety-001",
      "hash": "<bcrypt hash>",
      "scopes": ["safety_override"],
      "description": "Safety override only"
    }
  ]
}
```

---

## Module Packs

Packs are domain-specific capability bundles in `packs/`. Each pack contains:

```
packs/
├── education/
│   ├── manifest.json      # Pack metadata
│   ├── system_prompt.md   # Base system prompt
│   ├── worker_prompt.md   # Worker model instructions
│   ├── auditor_prompt.md  # Auditor model instructions
│   └── knowledge/         # RAG documents (optional)
│       ├── math_basics.md
│       └── ...
├── medical/
│   └── ...
└── disaster/
    └── ...
```

### Pack Manifest Example

```json
{
  "id": "education",
  "name": "Education Pack",
  "version": "1.0.0",
  "description": "General education and tutoring",
  "modes": ["education", "hybrid"],
  "reading_levels": ["child", "teen", "general", "technical"],
  "languages": ["en"],
  "safety_profile": "standard",
  "requires_auditor": true
}
```

---

## Dual-Model Pipeline

The system uses two model passes for safety and accuracy:

### Worker Model
- Generates the response
- Has access to pack knowledge
- Outputs structured JSON with source citations

### Auditor Model
- Reviews Worker output
- Checks for safety, accuracy, scope
- Returns verdict: APPROVE / REVISE / REJECT / ESCALATE

### Resolver
- Deterministic logic (not a model)
- Combines verdicts with policy
- Decides final action

```
User Query
    │
    ▼
┌─────────┐     ┌─────────────────────────────────┐
│ WORKER  │────▶│ { response, citations, confidence }
└─────────┘     └─────────────────────────────────┘
    │
    ▼
┌─────────┐     ┌─────────────────────────────────┐
│ AUDITOR │────▶│ { verdict, flags, reasoning }   │
└─────────┘     └─────────────────────────────────┘
    │
    ▼
┌──────────┐    ┌─────────────────────────────────┐
│ RESOLVER │───▶│ Final decision based on policy  │
└──────────┘    └─────────────────────────────────┘
    │
    ▼
Output (possibly with caveats/disclaimers)
```

---

## API Reference

### REST Endpoints

```
POST /api/query
  Body: { "message": string, "session_id"?: string }
  Returns: { "response": string, "audit": object }

POST /api/override
  Body: { "key": string, "scope": string, "action": object }
  Returns: { "success": boolean, "expires"?: datetime }

GET /api/status
  Returns: { "mode": string, "modules": object, "policy": object }

POST /api/mode
  Body: { "mode": string, "key"?: string }
  Returns: { "success": boolean, "mode": string }

POST /api/profile
  Body: { "envelope": object } (or QR data)
  Returns: { "success": boolean, "profile_id": string }

GET /api/audit
  Query: ?from=datetime&to=datetime&type=string
  Returns: { "events": array }
```

---

## Security Considerations

### Implemented
- Key hashing (bcrypt)
- Scope-limited overrides
- Audit logging of all sensitive operations
- Policy validation on load

### Future (RAO Phase)
- Ed25519 signed remote bundles
- Sequence numbers for anti-replay
- TLS for network channels
- Secure enclave for keys (hardware-dependent)

---

## Extension Points

The architecture is designed to never paint you into a corner:

### Adding a New Input Channel
1. Create adapter in `src/adapters/`
2. Implement the `IngestAdapter` interface
3. Add toggle to policy schema
4. Register in `src/core/ingest.py`

### Adding a New Module Pack
1. Create directory in `packs/`
2. Write manifest, prompts, knowledge docs
3. Pack auto-discovered on startup

### Adding a New LLM Backend
1. Create adapter in `src/adapters/`
2. Implement the `LLMAdapter` interface
3. Register in config

### Adding RAO Transport
1. Implement `RAOTransport` interface
2. Add to `src/core/rao.py` transport registry
3. Add toggle to policy schema

---

## Roadmap

### Phase 1 (Current) — Core Loop
- [x] Policy engine
- [x] Dual-model pipeline
- [x] Pack loader
- [x] Local web UI
- [x] Audit logging
- [x] Profile envelope (manual input)

### Phase 2 — Connectivity
- [ ] QR code profile ingest
- [ ] Bluetooth profile ingest
- [ ] Network update channel
- [ ] Cloud escalation channel

### Phase 3 — Sensors
- [ ] Video input processing
- [ ] Wearable data ingest
- [ ] Audio analysis

### Phase 4 — Remote Operations
- [ ] RAO core implementation
- [ ] Internet transport
- [ ] SMS/telecom transport
- [ ] Emergency broadcast receiver

### Phase 5 — Hardening
- [ ] Secure enclave integration
- [ ] Tamper-evident audit logs
- [ ] Hardware watchdog
- [ ] Offline-first sync strategies

---

## License

[To be determined by deploying organization]

---

## Contributing

This is a humanitarian tool. Contributions that expand capability while respecting the mission-agnostic, policy-driven philosophy are welcome.

---

## Acknowledgments

Born from conversations about bridging expertise deserts — the places where specialists never go but knowledge is desperately needed.

*"Your remote African tutor is also whatever else the organization who positioned it wants it to be in emergencies."*
