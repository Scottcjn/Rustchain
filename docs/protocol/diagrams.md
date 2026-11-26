# RustChain Protocol Diagrams

These diagrams are explanatory views of the contracts in [PROTOCOL.md](../PROTOCOL.md), [API.md](../API.md), and [epoch-settlement.md](../epoch-settlement.md).

## Attestation and enrollment

```mermaid
sequenceDiagram
    participant M as Miner
    participant N as RustChain node
    participant E as Epoch ledger

    M->>N: POST /attest/challenge
    N-->>M: nonce and challenge context
    M->>M: collect device and fingerprint signals
    M->>N: POST /attest/submit
    N->>N: validate shape, identity, nonce, rate, and fingerprint
    alt eligible
        N-->>M: accepted attestation
        M->>N: POST /epoch/enroll
        N->>E: record eligible miner for current epoch
        E-->>M: enrollment status
    else rejected
        N-->>M: error code and failed check
    end
```

## Consensus and settlement

```mermaid
flowchart TD
    A[Attestation received] --> B{Validation passes?}
    B -- no --> X[Reject and record reason]
    B -- yes --> C[Enroll miner in active epoch]
    C --> D[Epoch window closes]
    D --> E[Compute eligible weight]
    E --> F[epoch_pot × miner_weight / total_weight]
    F --> G[Write pending reward ledger]
    G --> H[Confirm or void through settlement policy]
    H --> I[Anchor settlement evidence when configured]
```

## Network roles

```mermaid
graph LR
    M1[Miner A] --> N[Attestation / API node]
    M2[Miner B] --> N
    M3[Miner C] --> N
    N --> L[(SQLite and pending ledger)]
    N --> P[Public API and explorer]
    N --> A[External settlement anchor]
```

## Documentation contract

```mermaid
flowchart LR
    S[Protocol source and node behavior] --> O[OpenAPI and read-only API contract]
    O --> R[API reference and examples]
    S --> P[Protocol specification]
    P --> T[Topic index]
    T --> G[Glossary]
```
