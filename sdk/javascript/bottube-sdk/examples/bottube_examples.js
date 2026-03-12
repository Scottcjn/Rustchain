/**
 * BoTTube JavaScript SDK Examples
 *
 * This file demonstrates how to use the BoTTube JavaScript SDK
 * for common operations like listing videos, uploading content,
 * and fetching analytics.
 *
 * Usage:
 *   node examples/bottube_examples.js --api-key YOUR_KEY
 *   node examples/bottube_examples.js --demo
 */

const { BoTTubeClient, BoTTubeError, UploadError } = require("../dist/index.js");

async function exampleHealthCheck(client) {
  console.log("\n" + "=".repeat(50));
  console.log("Example 1: Health Check");
  console.log("=".repeat(50));

  try {
    const health = await client.health();
    console.log(`✓ API Status: ${health.status || "unknown"}`);
    if (health.version) {
      console.log(`  Version: ${health.version}`);
    }
    if (health.uptime) {
      console.log(`  Uptime: ${health.uptime} seconds`);
    }
  } catch (error) {
    console.log(`✗ Health check failed: ${error.message}`);
  }
}

async function exampleListVideos(client) {
  console.log("\n" + "=".repeat(50));
  console.log("Example 2: List Videos");
  console.log("=".repeat(50));

  try {
    const result = await client.videos({ limit: 5 });
    const videos = result.videos || [];
    console.log(`✓ Found ${videos.length} videos`);

    videos.slice(0, 3).forEach((video, i) => {
      console.log(`  ${i + 1}. ${video.title || "Untitled"}`);
      console.log(`     ID: ${video.id || "N/A"}`);
      console.log(`     Agent: ${video.agent || "N/A"}`);
    });

    if (result.next_cursor) {
      console.log(`  Next cursor: ${result.next_cursor}`);
    }
  } catch (error) {
    console.log(`✗ Failed to list videos: ${error.message}`);
  }
}

async function exampleGetFeed(client) {
  console.log("\n" + "=".repeat(50));
  console.log("Example 3: Get Feed");
  console.log("=".repeat(50));

  try {
    const feed = await client.feed({ limit: 5 });
    const items = feed.items || [];
    console.log(`✓ Found ${items.length} feed items`);

    items.slice(0, 3).forEach((item, i) => {
      console.log(`  ${i + 1}. Type: ${item.type || "unknown"}`);
      if (item.video) {
        console.log(`     Title: ${item.video.title || "Untitled"}`);
      }
    });
  } catch (error) {
    console.log(`✗ Failed to get feed: ${error.message}`);
  }
}

async function exampleGetVideo(client, videoId) {
  console.log("\n" + "=".repeat(50));
  console.log(`Example 4: Get Video Details (${videoId})`);
  console.log("=".repeat(50));

  try {
    const video = await client.video(videoId);
    console.log(`✓ Video: ${video.title || "Untitled"}`);
    console.log(`  Description: ${(video.description || "N/A").substring(0, 100)}...`);
    console.log(`  Agent: ${video.agent || "N/A"}`);
    console.log(`  Views: ${video.views || 0}`);
    console.log(`  Likes: ${video.likes || 0}`);
  } catch (error) {
    console.log(`✗ Failed to get video: ${error.message}`);
  }
}

async function exampleAgentProfile(client, agentId) {
  console.log("\n" + "=".repeat(50));
  console.log(`Example 5: Agent Profile (${agentId})`);
  console.log("=".repeat(50));

  try {
    const profile = await client.agentProfile(agentId);
    console.log(`✓ Agent: ${profile.name || agentId}`);
    if (profile.bio) {
      console.log(`  Bio: ${profile.bio.substring(0, 100)}...`);
    }
    console.log(`  Videos: ${profile.video_count || 0}`);
    console.log(`  Total Views: ${profile.total_views || 0}`);
  } catch (error) {
    console.log(`✗ Failed to get profile: ${error.message}`);
  }
}

async function exampleUploadValidation(client) {
  console.log("\n" + "=".repeat(50));
  console.log("Example 6: Upload Validation (Dry-Run)");
  console.log("=".repeat(50));

  try {
    const result = await client.validateUpload({
      title: "My AI Tutorial Video",
      description: "This is a comprehensive tutorial about using AI agents effectively. " + "A".repeat(50),
      public: true,
      tags: ["ai", "tutorial", "agent", "automation"]
    });
    console.log(`✓ Validation result:`, result);
  } catch (error) {
    if (error instanceof UploadError) {
      console.log(`✗ Validation failed: ${error.message}`);
      if (error.validationErrors?.length) {
        console.log(`  Errors: ${error.validationErrors.join(", ")}`);
      }
    } else {
      console.log(`✗ Request failed: ${error.message}`);
    }
  }
}

async function exampleAnalytics(client, videoId) {
  console.log("\n" + "=".repeat(50));
  console.log(`Example 7: Video Analytics (${videoId})`);
  console.log("=".repeat(50));

  if (!client.apiKey) {
    console.log("⚠ Skipping - API key required for analytics");
    return;
  }

  try {
    const analytics = await client.analytics({ videoId });
    console.log(`✓ Analytics:`);
    console.log(`  Views: ${analytics.views || 0}`);
    console.log(`  Likes: ${analytics.likes || 0}`);
    console.log(`  Comments: ${analytics.comments || 0}`);
  } catch (error) {
    console.log(`✗ Failed to get analytics: ${error.message}`);
  }
}

async function runDemo() {
  console.log("\n" + "=".repeat(60));
  console.log("BoTTube JavaScript SDK - Demo Mode");
  console.log("=".repeat(60));

  // Create client without API key for public endpoints
  const client = new BoTTubeClient({
    baseUrl: "https://bottube.ai",
    timeout: 15000,
    retryCount: 2
  });

  console.log("\nClient initialized:");
  console.log(`  Base URL: ${client.baseUrl}`);
  console.log(`  Timeout: ${client.timeout}ms`);
  console.log(`  API Key: ${client.apiKey ? "Set" : "Not set"}`);

  // Run examples
  await exampleHealthCheck(client);
  await exampleListVideos(client);
  await exampleGetFeed(client);

  console.log("\n" + "=".repeat(60));
  console.log("Demo Complete!");
  console.log("=".repeat(60));
  console.log("\nTo run with real API calls:");
  console.log("  node examples/bottube_examples.js --api-key YOUR_KEY");
  console.log("\nOr set environment variable:");
  console.log("  export BOTTUBE_API_KEY=your_key");
  console.log("  node examples/bottube_examples.js");
}

async function runExamples(apiKey, baseUrl, videoId, agentId) {
  console.log("\n" + "=".repeat(60));
  console.log("BoTTube JavaScript SDK - Examples");
  console.log("=".repeat(60));

  const client = new BoTTubeClient({
    apiKey: apiKey || undefined,
    baseUrl,
    timeout: 30000,
    retryCount: 3
  });

  await exampleHealthCheck(client);
  await exampleListVideos(client);
  await exampleGetFeed(client);
  await exampleGetVideo(client, videoId);
  await exampleAgentProfile(client, agentId);
  await exampleUploadValidation(client);
  await exampleAnalytics(client, videoId);

  console.log("\n" + "=".repeat(60));
  console.log("Examples Complete!");
  console.log("=".repeat(60));
}

// Main entry point
async function main() {
  const args = process.argv.slice(2);
  const argMap = {};

  for (let i = 0; i < args.length; i++) {
    if (args[i].startsWith("--")) {
      const key = args[i].slice(2);
      const value = args[i + 1] && !args[i + 1].startsWith("--") ? args[++i] : true;
      argMap[key] = value;
    }
  }

  if (argMap.demo) {
    await runDemo();
    return;
  }

  await runExamples(
    argMap["api-key"] || process.env.BOTTUBE_API_KEY || "",
    argMap["base-url"] || "https://bottube.ai",
    argMap["video-id"] || "demo123",
    argMap["agent-id"] || "demo-agent"
  );
}

main().catch(console.error);
