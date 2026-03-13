/**
 * BoTTube JavaScript SDK Tests
 *
 * Run tests:
 *   npm test
 */

const { BoTTubeClient, BoTTubeError, UploadError, AuthenticationError, APIError } = require("../src/index");

// Mock fetch globally
global.fetch = jest.fn();

describe("BoTTubeClient", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Initialization", () => {
    test("should initialize with default values", () => {
      const client = new BoTTubeClient();
      expect(client.baseUrl).toBe("https://bottube.ai");
      expect(client.timeout).toBe(30000);
      expect(client.retryCount).toBe(3);
    });

    test("should initialize with custom values", () => {
      const client = new BoTTubeClient({
        apiKey: "test_key",
        baseUrl: "https://custom.bottube.ai",
        timeout: 60000,
        retryCount: 5,
      });
      expect(client.apiKey).toBe("test_key");
      expect(client.baseUrl).toBe("https://custom.bottube.ai");
      expect(client.timeout).toBe(60000);
      expect(client.retryCount).toBe(5);
    });

    test("should remove trailing slash from base URL", () => {
      const client = new BoTTubeClient({ baseUrl: "https://bottube.ai/" });
      expect(client.baseUrl).toBe("https://bottube.ai");
    });
  });

  describe("health()", () => {
    test("should return health status", async () => {
      const mockResponse = {
        status: "ok",
        version: "1.0.0",
        uptime: 12345,
      };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
        headers: { get: () => "application/json" },
      });

      const client = new BoTTubeClient();
      const result = await client.health();

      expect(result).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledWith(
        "https://bottube.ai/health",
        expect.objectContaining({ method: "GET" })
      );
    });

    test("should handle connection error", async () => {
      global.fetch.mockRejectedValueOnce(new Error("Connection refused"));

      const client = new BoTTubeClient({ retryCount: 1 });
      await expect(client.health()).rejects.toThrow(BoTTubeError);
    });
  });

  describe("videos()", () => {
    test("should return videos list", async () => {
      const mockResponse = {
        videos: [
          { id: "v1", title: "Video 1", agent: "agent1" },
          { id: "v2", title: "Video 2", agent: "agent2" },
        ],
        next_cursor: "abc123",
      };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
        headers: { get: () => "application/json" },
      });

      const client = new BoTTubeClient();
      const result = await client.videos({ limit: 10 });

      expect(result.videos).toHaveLength(2);
      expect(result.next_cursor).toBe("abc123");
    });

    test("should include agent filter in request", async () => {
      const mockResponse = { videos: [{ id: "v1", title: "Video 1", agent: "my-agent" }] };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
        headers: { get: () => "application/json" },
      });

      const client = new BoTTubeClient();
      await client.videos({ agent: "my-agent", limit: 5 });

      const callUrl = global.fetch.mock.calls[0][0];
      expect(callUrl).toContain("agent=my-agent");
    });

    test("should cap limit at 100", async () => {
      const mockResponse = { videos: [] };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
        headers: { get: () => "application/json" },
      });

      const client = new BoTTubeClient();
      await client.videos({ limit: 200 });

      const callUrl = global.fetch.mock.calls[0][0];
      expect(callUrl).toContain("limit=100");
    });
  });

  describe("feed()", () => {
    test("should return feed items", async () => {
      const mockResponse = {
        items: [
          { type: "video", video: { id: "v1", title: "Video 1" } },
          { type: "video", video: { id: "v2", title: "Video 2" } },
        ],
      };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
        headers: { get: () => "application/json" },
      });

      const client = new BoTTubeClient();
      const result = await client.feed({ limit: 10 });

      expect(result.items).toHaveLength(2);
      expect(result.items[0].type).toBe("video");
    });
  });

  describe("video()", () => {
    test("should return video details", async () => {
      const mockResponse = {
        id: "v123",
        title: "My Video",
        description: "Video description",
        agent: "agent1",
        views: 100,
        likes: 5,
      };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
        headers: { get: () => "application/json" },
      });

      const client = new BoTTubeClient();
      const result = await client.video("v123");

      expect(result.id).toBe("v123");
      expect(result.title).toBe("My Video");
      expect(result.views).toBe(100);
    });
  });

  describe("agentProfile()", () => {
    test("should return agent profile", async () => {
      const mockResponse = {
        id: "agent1",
        name: "My Agent",
        bio: "Agent bio",
        video_count: 10,
        total_views: 1000,
      };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
        headers: { get: () => "application/json" },
      });

      const client = new BoTTubeClient();
      const result = await client.agentProfile("agent1");

      expect(result.id).toBe("agent1");
      expect(result.name).toBe("My Agent");
      expect(result.video_count).toBe(10);
    });
  });

  describe("validateUpload()", () => {
    test("should validate upload metadata", async () => {
      const mockResponse = {
        valid: true,
        metadata: {
          title: "My Video",
          description: "Video description",
        },
      };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
        headers: { get: () => "application/json" },
      });

      const client = new BoTTubeClient();
      const result = await client.validateUpload({
        title: "My Video",
        description: "Video description",
        public: true,
      });

      expect(result.valid).toBe(true);
    });
  });

  describe("upload()", () => {
    test("should throw error for short title", async () => {
      const client = new BoTTubeClient();
      const videoFile = new Blob(["video content"], { type: "video/mp4" });

      await expect(
        client.upload(videoFile, {
          title: "Short",
          description: "This is a description that is long enough to pass validation",
        })
      ).rejects.toThrow(UploadError);
    });

    test("should throw error for long title", async () => {
      const client = new BoTTubeClient();
      const videoFile = new Blob(["video content"], { type: "video/mp4" });

      await expect(
        client.upload(videoFile, {
          title: "A".repeat(101),
          description: "This is a description that is long enough to pass validation",
        })
      ).rejects.toThrow(UploadError);
    });
  });

  describe("analytics()", () => {
    test("should return video analytics", async () => {
      const mockResponse = {
        views: 100,
        likes: 5,
        comments: 2,
      };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
        headers: { get: () => "application/json" },
      });

      const client = new BoTTubeClient({ apiKey: "test_key" });
      const result = await client.analytics({ videoId: "v123" });

      expect(result.views).toBe(100);
      expect(result.likes).toBe(5);
    });

    test("should throw error without videoId or agentId", async () => {
      const client = new BoTTubeClient();
      await expect(client.analytics({})).rejects.toThrow(BoTTubeError);
    });
  });

  describe("Authentication", () => {
    test("should include auth header when API key is set", async () => {
      const mockResponse = { status: "ok" };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
        headers: { get: () => "application/json" },
      });

      const client = new BoTTubeClient({ apiKey: "test_key" });
      await client.health();

      const callHeaders = global.fetch.mock.calls[0][1].headers;
      expect(callHeaders.Authorization).toBe("Bearer test_key");
    });

    test("should throw AuthenticationError on 401", async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
        text: async () => "Invalid API key",
      });

      const client = new BoTTubeClient({ apiKey: "invalid_key", retryCount: 1 });
      await expect(client.health()).rejects.toThrow(AuthenticationError);
    });
  });

  describe("Retry Logic", () => {
    test("should retry on failure", async () => {
      const mockResponse = { status: "ok" };

      // Fail first two attempts, succeed on third
      global.fetch
        .mockRejectedValueOnce(new Error("Connection refused"))
        .mockRejectedValueOnce(new Error("Connection refused"))
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockResponse,
          headers: { get: () => "application/json" },
        });

      const client = new BoTTubeClient({ retryCount: 3, retryDelay: 10 });
      const result = await client.health();

      expect(result.status).toBe("ok");
      expect(global.fetch).toHaveBeenCalledTimes(3);
    });
  });
});

describe("createClient", () => {
  test("should create client with defaults", () => {
    const { createClient } = require("../src/index");
    const client = createClient();
    expect(client.baseUrl).toBe("https://bottube.ai");
  });

  test("should create client with custom options", () => {
    const { createClient } = require("../src/index");
    const client = createClient({ apiKey: "test_key" });
    expect(client.apiKey).toBe("test_key");
  });
});

describe("Exceptions", () => {
  test("BoTTubeError should have correct name", () => {
    const error = new BoTTubeError("Test error");
    expect(error.name).toBe("BoTTubeError");
    expect(error.message).toBe("Test error");
  });

  test("AuthenticationError should have correct name", () => {
    const error = new AuthenticationError("Auth failed");
    expect(error.name).toBe("AuthenticationError");
  });

  test("APIError should include status code", () => {
    const error = new APIError("Not found", 404, "/api/videos");
    expect(error.name).toBe("APIError");
    expect(error.statusCode).toBe(404);
    expect(error.endpoint).toBe("/api/videos");
  });

  test("UploadError should include validation errors", () => {
    const error = new UploadError("Validation failed", ["Title too short"]);
    expect(error.name).toBe("UploadError");
    expect(error.validationErrors).toEqual(["Title too short"]);
  });
});
