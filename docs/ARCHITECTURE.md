# Expert-in-a-Box V2 Architecture

## Design Philosophy

**Capacity, not decisions.** We build the toggle surfaces and capability enums. Mission-specific choices are made by the admins who deploy devices.

## Core Components

### 1. Policy Engine (`src/core/policy.py`)
- JSON-based toggle system
- Every capability is configurable
- Validation on load
- Runtime evaluation

### 2. Key Registry (`src/core/keys.py`)
- Override key management
- Scope-based authorization
- Time-boxed sessions
- Audit integration

### 3. Dual-Model Pipeline (`src/core/pipeline.py`)
- Worker: Generates responses
- Auditor: Reviews for safety/accuracy
- Resolver: Makes final decision (deterministic, not ML)

### 4. Pack Loader (`src/core/packs.py`)
- Domain-specific capability bundles
- Auto-discovery from `packs/` directory
- Hot-loadable per policy

### 5. Profile Manager (`src/core/profile.py`)
- User adaptation (reading level, format)
- QR/BLE ingest (future)
- Not for authorization

### 6. Audit Logger (`src/core/audit.py`)
- Append-only logging
- Checksum chain (tamper-evident)
- Query and export

## Data Flow

```
User Input
    │
    ▼
┌─────────────────┐
│  Ingest Layer   │ ← Profile, sensors (future)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Policy Check   │ ← Is this allowed?
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Pack Selection │ ← Which module handles this?
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Worker Model   │ ← Generate response
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Auditor Model  │ ← Review response
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Resolver     │ ← Final decision
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Output Adapt   │ ← Format for user
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Audit Log     │ ← Record everything
└─────────────────┘
```

## Extension Points

### Adding Input Channels
1. Implement adapter in `src/adapters/`
2. Add toggle to policy schema
3. Wire into ingest layer

### Adding Module Packs
1. Create `packs/<id>/manifest.json`
2. Add prompts and knowledge
3. Auto-discovered on startup

### Adding LLM Backends
1. Implement `LLMAdapter` protocol
2. Register in config
3. Supports hot-swapping

### Adding RAO Transports
1. Implement `RAOTransport` protocol
2. Register with RAOManager
3. Policy controls which are active

## Security Model

- **Defense in depth**: Multiple validation layers
- **Principle of least privilege**: Scoped keys
- **Audit everything**: Full trail
- **Fail safe**: Conservative defaults
