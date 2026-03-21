/**
 * Unit tests for BoTTube MCP Server
 *
 * Tests mock the BoTTube API responses using axios mock adapter.
 * Run with: npm test
 */

import axios from 'axios';
import MockAdapter from 'axios-mock-adapter';
import { BoTTubeClient } from '../src/api.js';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createMockedClient(): {
  client: BoTTubeClient;
  mock: MockAdapter;
} {
  const client = new BoTTubeClient('test-api-key');
  const httpMock = new MockAdapter(client as any);
  return { client: client as any, mock: httpMock };
}

// ---------------------------------------------------------------------------
// API Tests: getTrending
// ---------------------------------------------------------------------------

test('getTrending returns video list with total', async () => {
  const { client, mock } = createMockedClient();

  const mockResponse = {
    videos: [
      {
        id: 'vid1',
        title: 'AI Music Video',
        description: 'A cool AI-generated music video',
        agent_name: 'musicbot',
        views: 10000,
        likes: 500,
        created_at: '2024-01-15T10:00:00Z',
        tags: ['music', 'ai'],
      },
      {
        id: 'vid2',
        title: 'Retro Game Review',
        description: 'AI reviews classic games',
        agent_name: 'gamebot',
        views: 5000,
        likes: 200,
        created_at: '2024-01-14T08:00:00Z',
        tags: ['gaming', 'retro'],
      },
    ],
    total: 2,
  };

  mock.onGet('/api/trending').reply(200, mockResponse);

  const result = await client.getTrending(10);

  expect(result.videos).toHaveLength(2);
  expect(result.total).toBe(2);
  expect(result.videos[0].title).toBe('AI Music Video');
  expect(result.videos[0].agent_name).toBe('musicbot');
});

// ---------------------------------------------------------------------------
// API Tests: searchVideos
// ---------------------------------------------------------------------------

test('searchVideos returns paginated results', async () => {
  const { client, mock } = createMockedClient();

  const mockResponse = {
    videos: [
      {
        id: 'vid3',
        title: 'Retro Synth Wave',
        description: 'AI-generated retro synth',
        agent_name: 'wavebot',
        views: 3000,
        likes: 150,
        created_at: '2024-01-13T12:00:00Z',
        tags: ['synth', 'retro'],
      },
    ],
    total: 1,
    page: 1,
    per_page: 10,
  };

  mock.onGet('/api/search').reply(200, mockResponse);

  const result = await client.searchVideos('retro', 1, 10, 'newest');

  expect(result.videos).toHaveLength(1);
  expect(result.total).toBe(1);
  expect(result.page).toBe(1);
  expect(result.per_page).toBe(10);
});

// ---------------------------------------------------------------------------
// API Tests: getVideo
// ---------------------------------------------------------------------------

test('getVideo returns video details and comments', async () => {
  const { client, mock } = createMockedClient();

  const mockResponse = {
    video: {
      id: 'vid1',
      title: 'AI Music Video',
      description: 'A cool AI-generated music video',
      agent_name: 'musicbot',
      views: 10000,
      likes: 500,
      comments_count: 12,
      shares: 30,
      created_at: '2024-01-15T10:00:00Z',
      tags: ['music', 'ai'],
    },
    comments: [
      {
        id: 'c1',
        video_id: 'vid1',
        agent_name: 'viewer1',
        content: 'Great video!',
        created_at: '2024-01-15T11:00:00Z',
        likes: 5,
      },
    ],
  };

  mock.onGet('/api/videos/vid1').reply(200, mockResponse);

  const result = await client.getVideo('vid1');

  expect(result.video.title).toBe('AI Music Video');
  expect(result.comments).toHaveLength(1);
  expect(result.comments[0].content).toBe('Great video!');
});

// ---------------------------------------------------------------------------
// API Tests: getAgent
// ---------------------------------------------------------------------------

test('getAgent returns agent profile and videos', async () => {
  const { client, mock } = createMockedClient();

  const mockResponse = {
    agent: {
      agent_name: 'musicbot',
      display_name: 'Music Bot',
      bio: 'Generates AI music videos',
      total_videos: 25,
      total_views: 50000,
      total_likes: 3000,
      registered_at: '2023-06-01T00:00:00Z',
    },
    videos: [
      {
        id: 'vid1',
        title: 'AI Music Video',
        description: 'A cool AI-generated music video',
        agent_name: 'musicbot',
        views: 10000,
        likes: 500,
        created_at: '2024-01-15T10:00:00Z',
        tags: ['music', 'ai'],
      },
    ],
  };

  mock.onGet('/api/agents/musicbot').reply(200, mockResponse);

  const result = await client.getAgent('musicbot');

  expect(result.agent.display_name).toBe('Music Bot');
  expect(result.agent.total_videos).toBe(25);
  expect(result.videos).toHaveLength(1);
});

// ---------------------------------------------------------------------------
// API Tests: getStats
// ---------------------------------------------------------------------------

test('getStats returns platform statistics', async () => {
  const { client, mock } = createMockedClient();

  const mockResponse = {
    videos: 1500,
    agents: 120,
    total_views: 5000000,
    total_likes: 250000,
    uptime_days: 365,
  };

  mock.onGet('/api/stats').reply(200, mockResponse);

  const result = await client.getStats();

  expect(result.videos).toBe(1500);
  expect(result.agents).toBe(120);
  expect(result.uptime_days).toBe(365);
});

// ---------------------------------------------------------------------------
// API Tests: postComment
// ---------------------------------------------------------------------------

test('postComment posts a comment and returns the comment object', async () => {
  const { client, mock } = createMockedClient();

  const mockResponse = {
    comment_id: 'c99',
    video_id: 'vid1',
    content: 'Amazing work!',
    created_at: '2024-01-16T09:00:00Z',
  };

  mock.onPost('/api/videos/vid1/comment').reply(200, mockResponse);

  const result = await client.postComment('vid1', 'Amazing work!');

  expect(result.comment_id).toBe('c99');
  expect(result.video_id).toBe('vid1');
  expect(result.content).toBe('Amazing work!');
});

// ---------------------------------------------------------------------------
// API Tests: postVote
// ---------------------------------------------------------------------------

test('postVote submits a vote and returns the new score', async () => {
  const { client, mock } = createMockedClient();

  const mockResponse = {
    video_id: 'vid1',
    vote: 1,
    new_score: 501,
  };

  mock.onPost('/api/videos/vid1/vote').reply(200, mockResponse);

  const result = await client.postVote('vid1', 1);

  expect(result.video_id).toBe('vid1');
  expect(result.vote).toBe(1);
  expect(result.new_score).toBe(501);
});

// ---------------------------------------------------------------------------
// API Tests: register
// ---------------------------------------------------------------------------

test('register registers a new agent', async () => {
  const { client, mock } = createMockedClient();

  const mockResponse = {
    agent_name: 'newbot',
    display_name: 'New Bot',
    registered_at: '2024-01-16T10:00:00Z',
  };

  mock.onPost('/api/register').reply(200, mockResponse);

  const result = await client.register('newbot', 'New Bot');

  expect(result.agent_name).toBe('newbot');
  expect(result.display_name).toBe('New Bot');
});

// ---------------------------------------------------------------------------
// API Tests: getVideoComments
// ---------------------------------------------------------------------------

test('getVideoComments returns comment list', async () => {
  const { client, mock } = createMockedClient();

  const mockResponse = [
    {
      id: 'c1',
      video_id: 'vid1',
      agent_name: 'viewer1',
      content: 'First!',
      created_at: '2024-01-15T11:00:00Z',
      likes: 10,
    },
    {
      id: 'c2',
      video_id: 'vid1',
      agent_name: 'viewer2',
      content: 'Loved it!',
      created_at: '2024-01-15T12:00:00Z',
      likes: 3,
    },
  ];

  mock.onGet('/api/videos/vid1/comments').reply(200, mockResponse);

  const result = await client.getVideoComments('vid1');

  expect(result).toHaveLength(2);
  expect(result[0].content).toBe('First!');
});

// ---------------------------------------------------------------------------
// API Tests: Auth Headers
// ---------------------------------------------------------------------------

test('API key is sent in X-API-Key header when set', async () => {
  const client = new BoTTubeClient('my-secret-key');
  const mock = new MockAdapter(client as any);

  const mockResponse = { videos: [], total: 0 };
  mock.onGet('/api/trending').reply(200, mockResponse);

  await client.getTrending(10);

  // Check the request headers were sent correctly
  const lastRequest = mock.history.get[0];
  expect(lastRequest.headers['X-API-Key']).toBe('my-secret-key');
});

test('No X-API-Key header when client has no API key', async () => {
  const clientWithoutKey = new BoTTubeClient();
  const mock = new MockAdapter(clientWithoutKey as any);

  const mockResponse = { videos: [], total: 0 };
  mock.onGet('/api/trending').reply(200, mockResponse);

  await clientWithoutKey.getTrending(10);

  const lastRequest = mock.history.get[0];
  expect(lastRequest.headers['X-API-Key']).toBeUndefined();
});
