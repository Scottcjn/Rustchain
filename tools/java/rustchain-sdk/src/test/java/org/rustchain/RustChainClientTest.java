package org.rustchain;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for {@link RustChainClient} — all tests are offline (no network).
 *
 * <p>Integration / live-node tests should be gated behind a system property or
 * environment variable and are <em>not</em> included here to keep CI fast.
 */
@DisplayName("RustChainClient")
class RustChainClientTest {

    // ── Constructor / configuration ───────────────────────────────────────────

    @Test
    @DisplayName("stores base URL, timeout and retry count")
    void testConstructorStoresConfig() {
        RustChainClient client = new RustChainClient("https://rustchain.org", 30, 5);
        assertEquals("https://rustchain.org", client.getBaseUrl());
        assertEquals(30, client.getTimeoutSeconds());
        assertEquals(5,  client.getMaxRetries());
    }

    @Test
    @DisplayName("strips trailing slash from base URL")
    void testBaseUrlTrailingSlashStripped() {
        RustChainClient client = new RustChainClient("https://rustchain.org///");
        assertEquals("https://rustchain.org", client.getBaseUrl());
    }

    @Test
    @DisplayName("default constructor uses sensible defaults")
    void testDefaultConstructor() {
        RustChainClient client = new RustChainClient("https://rustchain.org");
        assertEquals(RustChainClient.DEFAULT_TIMEOUT_SECONDS, client.getTimeoutSeconds());
        assertEquals(RustChainClient.DEFAULT_RETRIES,         client.getMaxRetries());
    }

    // ── JSON serialisation ────────────────────────────────────────────────────

    @Test
    @DisplayName("toJson serialises null correctly")
    void testToJsonNull() {
        assertEquals("null", RustChainClient.toJson(null));
    }

    @Test
    @DisplayName("toJson serialises booleans correctly")
    void testToJsonBoolean() {
        assertEquals("true",  RustChainClient.toJson(true));
        assertEquals("false", RustChainClient.toJson(false));
    }

    @Test
    @DisplayName("toJson serialises integers correctly")
    void testToJsonInteger() {
        assertEquals("42",   RustChainClient.toJson(42));
        assertEquals("-7",   RustChainClient.toJson(-7));
        assertEquals("3.14", RustChainClient.toJson(3.14));
    }

    @Test
    @DisplayName("toJson serialises strings with proper quoting")
    void testToJsonString() {
        assertEquals("\"hello\"", RustChainClient.toJson("hello"));
    }

    @Test
    @DisplayName("toJson escapes special characters in strings")
    void testToJsonStringEscaping() {
        String result = RustChainClient.toJson("say \"hi\"\nnewline");
        assertEquals("\"say \\\"hi\\\"\\nnewline\"", result);
    }

    @Test
    @DisplayName("toJson serialises a flat map")
    void testToJsonFlatMap() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("miner_id", "my-miner");
        m.put("cores",    4);
        m.put("ok",       true);
        String json = RustChainClient.toJson(m);
        assertEquals("{\"miner_id\":\"my-miner\",\"cores\":4,\"ok\":true}", json);
    }

    @Test
    @DisplayName("toJson serialises a nested map")
    void testToJsonNestedMap() {
        Map<String, Object> inner = new LinkedHashMap<>();
        inner.put("arch", "amd64");

        Map<String, Object> outer = new LinkedHashMap<>();
        outer.put("device", inner);

        String json = RustChainClient.toJson(outer);
        assertEquals("{\"device\":{\"arch\":\"amd64\"}}", json);
    }

    @Test
    @DisplayName("toJson serialises a list")
    void testToJsonList() {
        String json = RustChainClient.toJson(List.of("a", "b", 3));
        assertEquals("[\"a\",\"b\",3]", json);
    }

    // ── ApiResponse ───────────────────────────────────────────────────────────

    @Test
    @DisplayName("ApiResponse.isSuccess returns true for 2xx status codes")
    void testApiResponseIsSuccess() {
        assertTrue(new RustChainClient.ApiResponse(200, "{}").isSuccess());
        assertTrue(new RustChainClient.ApiResponse(201, "{}").isSuccess());
        assertTrue(new RustChainClient.ApiResponse(204, "")  .isSuccess());
    }

    @Test
    @DisplayName("ApiResponse.isSuccess returns false for 4xx/5xx")
    void testApiResponseIsNotSuccess() {
        assertFalse(new RustChainClient.ApiResponse(400, "{}").isSuccess());
        assertFalse(new RustChainClient.ApiResponse(404, "{}").isSuccess());
        assertFalse(new RustChainClient.ApiResponse(500, "{}").isSuccess());
        assertFalse(new RustChainClient.ApiResponse(-1,  "{}").isSuccess());
    }

    @Test
    @DisplayName("ApiResponse.extractField reads a string value")
    void testExtractFieldString() {
        RustChainClient.ApiResponse resp =
                new RustChainClient.ApiResponse(200, "{\"version\":\"2.2.1-rip200\",\"ok\":true}");
        assertEquals("2.2.1-rip200", resp.extractField("version"));
    }

    @Test
    @DisplayName("ApiResponse.extractField reads a numeric value")
    void testExtractFieldNumber() {
        RustChainClient.ApiResponse resp =
                new RustChainClient.ApiResponse(200, "{\"epoch\":95,\"slot\":12345}");
        assertEquals("95", resp.extractField("epoch"));
    }

    @Test
    @DisplayName("ApiResponse.extractField returns null for missing key")
    void testExtractFieldMissingKey() {
        RustChainClient.ApiResponse resp =
                new RustChainClient.ApiResponse(200, "{\"ok\":true}");
        assertNull(resp.extractField("nonexistent"));
    }

    @Test
    @DisplayName("ApiResponse body is never null")
    void testApiResponseBodyNeverNull() {
        assertNotNull(new RustChainClient.ApiResponse(200, null).getBody());
    }
}
