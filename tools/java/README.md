# RustChain Java SDK

A pure-Java implementation of the RustChain Proof-of-Antiquity toolchain.  
Zero external runtime dependencies — only `java.net.http` (JDK 11+) and `java.security`.

---

## Contents

| Class | Purpose |
|-------|---------|
| `RustChainClient` | HTTP client wrapping every public API endpoint |
| `Fingerprint` | Hardware identity collector (CPU, memory, clock-drift, SHA-256) |
| `Miner` | CLI mining loop: fingerprint → attest → sleep |

---

## Requirements

| Tool | Version |
|------|---------|
| Java | 11 or newer |
| Maven | 3.8+ |

---

## Build

```bash
cd tools/java/rustchain-sdk

# Compile + run tests
mvn clean verify

# Build executable fat JAR
mvn clean package -DskipTests

# The fat JAR lands at:
# target/rustchain-sdk-1.0.0-jar-with-dependencies.jar
```

---

## Run the Miner

```bash
java -jar target/rustchain-sdk-1.0.0-jar-with-dependencies.jar \
     --node-url  https://rustchain.org \
     --miner-id  my-powerbook-g4 \
     --interval  60
```

### CLI flags

| Flag | Default | Description |
|------|---------|-------------|
| `--node-url` | `https://rustchain.org` | RustChain node base URL |
| `--miner-id` | `java-miner-<username>` | Unique miner identifier |
| `--interval`  | `60` | Seconds between attestation cycles |
| `--help` | — | Print usage |

Press **Ctrl-C** to stop. The miner prints a summary (cycles, successes, failures) on exit.

---

## Use the SDK in Your Own Project

### Create a client

```java
// Default: 15 s timeout, 3 retries
RustChainClient client = new RustChainClient("https://rustchain.org");

// Custom timeout and retry count
RustChainClient client = new RustChainClient("https://rustchain.org", 30, 5);
```

### API reference

#### `healthCheck()`
```java
ApiResponse resp = client.healthCheck();
// GET /health → {"ok":true,"version":"2.2.1-rip200","uptime_s":200000}
System.out.println(resp.extractField("version")); // "2.2.1-rip200"
```

#### `getEpoch()`
```java
ApiResponse resp = client.getEpoch();
// GET /epoch → {"epoch":95,"slot":12345,"height":67890}
System.out.println(resp.extractField("epoch")); // "95"
```

#### `getMiners()`
```java
ApiResponse resp = client.getMiners();
// GET /api/miners → JSON array of active miner objects
System.out.println(resp.getBody());
```

#### `getStats()`
```java
ApiResponse resp = client.getStats();
// GET /api/stats → network-wide statistics
System.out.println(resp.getBody());
```

#### `submitAttestation(Map<String,Object> payload)`
```java
Fingerprint fp = Fingerprint.collect();

Map<String, Object> payload = new LinkedHashMap<>();
payload.put("miner_id",    "my-miner-001");
payload.put("device",      fp.toDeviceMap());
payload.put("fingerprint", fp.toFingerprintMap());

ApiResponse resp = client.submitAttestation(payload);
if (resp.isSuccess()) {
    System.out.println("Reward: " + resp.extractField("reward"));
} else {
    System.err.println("Failed: HTTP " + resp.getStatusCode());
    System.err.println(resp.getBody());
}
```

### Working with `ApiResponse`

```java
resp.isSuccess()           // true for HTTP 2xx
resp.getStatusCode()       // e.g. 200, 400, -1 (network error)
resp.getBody()             // raw JSON string
resp.extractField("epoch") // naive top-level field extraction
```

### Hardware Fingerprint

```java
Fingerprint fp = Fingerprint.collect();

fp.getArch()          // "amd64", "aarch64", …
fp.getCores()         // logical CPU count
fp.getTotalMemoryMb() // JVM heap total (MB)
fp.getFreeMemoryMb()  // JVM heap free  (MB)
fp.getOsName()        // "Linux", "Mac OS X", …
fp.getOsVersion()     // kernel / OS version string
fp.getJvmVersion()    // "11.0.21", "17.0.9", …
fp.getClockDriftNs()  // average ns for internal timing loop
fp.getHash()          // "sha256:a1b2c3…" stable machine identity

// Payload-ready maps
fp.toDeviceMap();      // for attestation "device" field
fp.toFingerprintMap(); // for attestation "fingerprint" field
```

---

## Run Tests

```bash
mvn test
```

All tests are offline (no network required).

---

## License

MIT — see [LICENSE](../../LICENSE).
