package org.rustchain;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * RustChainClient — lightweight HTTP client for the RustChain Proof-of-Antiquity API.
 *
 * <p>Built entirely on {@code java.net.http} (JDK 11+). No external dependencies.
 *
 * <h3>Quick start</h3>
 * <pre>{@code
 * RustChainClient client = new RustChainClient("https://rustchain.org");
 * System.out.println(client.healthCheck());
 * System.out.println(client.getEpoch());
 * }</pre>
 *
 * <h3>Attestation</h3>
 * <pre>{@code
 * Map<String, Object> payload = new LinkedHashMap<>();
 * payload.put("miner_id", "my-miner-001");
 * payload.put("fingerprint", Map.of("hash", "sha256:abc123"));
 * ApiResponse resp = client.submitAttestation(payload);
 * }</pre>
 */
public class RustChainClient {

    private static final Logger LOG = Logger.getLogger(RustChainClient.class.getName());

    /** Default connection/request timeout (seconds). */
    public static final int DEFAULT_TIMEOUT_SECONDS = 15;

    /** Default number of retry attempts on transient failures. */
    public static final int DEFAULT_RETRIES = 3;

    /** Base delay between retries (ms), doubled on each attempt. */
    private static final long RETRY_BASE_DELAY_MS = 500;

    // ── Configuration ────────────────────────────────────────────────────────

    private final String baseUrl;
    private final int timeoutSeconds;
    private final int maxRetries;
    private final HttpClient httpClient;

    // ── Constructors ─────────────────────────────────────────────────────────

    /**
     * Create a client with default timeout (15 s) and 3 retries.
     *
     * @param baseUrl API base URL, e.g. {@code "https://rustchain.org"}
     */
    public RustChainClient(String baseUrl) {
        this(baseUrl, DEFAULT_TIMEOUT_SECONDS, DEFAULT_RETRIES);
    }

    /**
     * Create a fully-configured client.
     *
     * @param baseUrl        API base URL
     * @param timeoutSeconds per-request timeout
     * @param maxRetries     number of retries on 5xx / network errors
     */
    public RustChainClient(String baseUrl, int timeoutSeconds, int maxRetries) {
        this.baseUrl = baseUrl.replaceAll("/+$", ""); // strip trailing slashes
        this.timeoutSeconds = timeoutSeconds;
        this.maxRetries = maxRetries;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(timeoutSeconds))
                // Follow redirects so http:// → https:// works
                .followRedirects(HttpClient.Redirect.NORMAL)
                .build();
    }

    // ── Public API methods ────────────────────────────────────────────────────

    /**
     * GET /health — node liveness probe.
     *
     * @return {@link ApiResponse} with JSON body like {@code {"ok":true,"version":"2.2.1-rip200"}}
     */
    public ApiResponse healthCheck() {
        return get("/health");
    }

    /**
     * GET /epoch — current epoch, slot and block height.
     *
     * @return {@link ApiResponse} with JSON body like {@code {"epoch":95,"slot":12345,"height":67890}}
     */
    public ApiResponse getEpoch() {
        return get("/epoch");
    }

    /**
     * GET /api/miners — list of active miners with multipliers and balances.
     *
     * @return {@link ApiResponse} with JSON array of miner objects
     */
    public ApiResponse getMiners() {
        return get("/api/miners");
    }

    /**
     * GET /api/stats — network-wide statistics (total RTC, active miners, etc.).
     *
     * @return {@link ApiResponse} with JSON stats object
     */
    public ApiResponse getStats() {
        return get("/api/stats");
    }

    /**
     * POST /attest/submit — submit a hardware attestation for mining rewards.
     *
     * <p>The payload must contain at minimum:
     * <ul>
     *   <li>{@code miner_id} — unique miner identifier string</li>
     *   <li>{@code device}   — object with {@code arch}, {@code cpu}, {@code cores}</li>
     *   <li>{@code fingerprint} — object with {@code hash} (SHA-256 hex)</li>
     * </ul>
     *
     * @param payload key/value map that will be serialised to JSON
     * @return {@link ApiResponse}; check {@link ApiResponse#isSuccess()} and body
     */
    public ApiResponse submitAttestation(Map<String, Object> payload) {
        String json = toJson(payload);
        return post("/attest/submit", json);
    }

    // ── HTTP helpers ──────────────────────────────────────────────────────────

    /** Perform a GET request with retry logic. */
    private ApiResponse get(String path) {
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + path))
                .timeout(Duration.ofSeconds(timeoutSeconds))
                .header("Accept", "application/json")
                .header("User-Agent", "RustChain-Java-SDK/1.0")
                .GET()
                .build();
        return executeWithRetry(request);
    }

    /** Perform a POST request with JSON body and retry logic. */
    private ApiResponse post(String path, String jsonBody) {
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + path))
                .timeout(Duration.ofSeconds(timeoutSeconds))
                .header("Accept", "application/json")
                .header("Content-Type", "application/json")
                .header("User-Agent", "RustChain-Java-SDK/1.0")
                .POST(HttpRequest.BodyPublishers.ofString(jsonBody))
                .build();
        return executeWithRetry(request);
    }

    /** Execute an HTTP request, retrying on transient failures. */
    private ApiResponse executeWithRetry(HttpRequest request) {
        int attempt = 0;
        long delay = RETRY_BASE_DELAY_MS;

        while (true) {
            attempt++;
            try {
                HttpResponse<String> response = httpClient.send(
                        request, HttpResponse.BodyHandlers.ofString());
                int status = response.statusCode();

                // Retry only on server-side errors (5xx)
                if (status >= 500 && attempt <= maxRetries) {
                    LOG.log(Level.WARNING, "Server error {0} on attempt {1}/{2}, retrying in {3} ms",
                            new Object[]{status, attempt, maxRetries, delay});
                    sleep(delay);
                    delay *= 2;
                    continue;
                }

                return new ApiResponse(status, response.body());

            } catch (IOException e) {
                if (attempt > maxRetries) {
                    LOG.log(Level.SEVERE, "Request failed after {0} attempts: {1}",
                            new Object[]{maxRetries, e.getMessage()});
                    return new ApiResponse(-1, "{\"error\":\"" + escape(e.getMessage()) + "\"}");
                }
                LOG.log(Level.WARNING, "Network error on attempt {0}/{1}, retrying in {2} ms: {3}",
                        new Object[]{attempt, maxRetries, delay, e.getMessage()});
                sleep(delay);
                delay *= 2;

            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return new ApiResponse(-1, "{\"error\":\"interrupted\"}");
            }
        }
    }

    // ── Minimal JSON serialisation (no external libs) ─────────────────────────

    /**
     * Recursively serialise a {@code Map<String,Object>} to a JSON string.
     * Supported value types: {@code String}, {@code Number}, {@code Boolean},
     * {@code Map<String,Object>}, {@code Iterable<?>}, and {@code null}.
     */
    @SuppressWarnings("unchecked")
    static String toJson(Object value) {
        if (value == null) return "null";
        if (value instanceof Boolean || value instanceof Number) return value.toString();
        if (value instanceof String) return "\"" + escape((String) value) + "\"";
        if (value instanceof Map) {
            StringBuilder sb = new StringBuilder("{");
            boolean first = true;
            for (Map.Entry<?, ?> entry : ((Map<?, ?>) value).entrySet()) {
                if (!first) sb.append(',');
                sb.append('"').append(escape(entry.getKey().toString())).append("\":");
                sb.append(toJson(entry.getValue()));
                first = false;
            }
            return sb.append('}').toString();
        }
        if (value instanceof Iterable) {
            StringBuilder sb = new StringBuilder("[");
            boolean first = true;
            for (Object item : (Iterable<?>) value) {
                if (!first) sb.append(',');
                sb.append(toJson(item));
                first = false;
            }
            return sb.append(']').toString();
        }
        // Fallback — treat as string
        return "\"" + escape(value.toString()) + "\"";
    }

    /** Escape special characters for embedding in a JSON string literal. */
    static String escape(String raw) {
        if (raw == null) return "";
        return raw.replace("\\", "\\\\")
                  .replace("\"", "\\\"")
                  .replace("\n", "\\n")
                  .replace("\r", "\\r")
                  .replace("\t", "\\t");
    }

    private static void sleep(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); }
    }

    // ── Getters (useful for tests / logging) ─────────────────────────────────

    public String getBaseUrl()       { return baseUrl; }
    public int    getTimeoutSeconds(){ return timeoutSeconds; }
    public int    getMaxRetries()    { return maxRetries; }

    // ── Inner type ────────────────────────────────────────────────────────────

    /**
     * Immutable HTTP response wrapper returned by every API method.
     */
    public static final class ApiResponse {
        private final int    statusCode;
        private final String body;

        ApiResponse(int statusCode, String body) {
            this.statusCode = statusCode;
            this.body       = body == null ? "" : body;
        }

        /** HTTP status code, or {@code -1} on network / timeout error. */
        public int    getStatusCode() { return statusCode; }

        /** Raw response body (JSON string). */
        public String getBody()       { return body; }

        /** True when status is in the 2xx range. */
        public boolean isSuccess()    { return statusCode >= 200 && statusCode < 300; }

        /**
         * Naive extraction of a top-level string/number value from the JSON body.
         * Suitable for simple single-value reads without pulling in a JSON library.
         *
         * @param key JSON key to look up
         * @return raw value string (without quotes) or {@code null} if not found
         */
        public String extractField(String key) {
            String pattern = "\"" + key + "\"";
            int idx = body.indexOf(pattern);
            if (idx < 0) return null;
            int colon = body.indexOf(':', idx + pattern.length());
            if (colon < 0) return null;
            int start = colon + 1;
            while (start < body.length() && body.charAt(start) == ' ') start++;
            if (start >= body.length()) return null;
            char first = body.charAt(start);
            if (first == '"') {
                int end = body.indexOf('"', start + 1);
                return end > start ? body.substring(start + 1, end) : null;
            }
            // Number / boolean / null
            int end = start;
            while (end < body.length() && ",}\n\r ".indexOf(body.charAt(end)) < 0) end++;
            return body.substring(start, end).trim();
        }

        @Override
        public String toString() {
            return "ApiResponse{status=" + statusCode + ", body='" + body + "'}";
        }
    }
}
