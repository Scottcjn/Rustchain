package agenteco

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// Test helpers

func newTestServer(handler http.HandlerFunc) (*httptest.Server, *Client, error) {
	server := httptest.NewServer(handler)

	client, err := NewClient(&ClientConfig{
		BaseURL: server.URL,
		Timeout: 5 * time.Second,
	})
	if err != nil {
		server.Close()
		return nil, nil, err
	}

	return server, client, nil
}

func mustMarshal(t *testing.T, v interface{}) []byte {
	t.Helper()
	data, err := json.Marshal(v)
	if err != nil {
		t.Fatalf("Failed to marshal: %v", err)
	}
	return data
}

// Test Client Creation

func TestNewClient(t *testing.T) {
	t.Run("DefaultConfig", func(t *testing.T) {
		client, err := NewClientWithDefaults()
		if err != nil {
			t.Fatalf("Failed to create client: %v", err)
		}
		defer client.Close()

		if client.baseURL.String() != DefaultBaseURL {
			t.Errorf("Expected baseURL %s, got %s", DefaultBaseURL, client.baseURL.String())
		}
		if client.maxRetries != DefaultMaxRetries {
			t.Errorf("Expected maxRetries %d, got %d", DefaultMaxRetries, client.maxRetries)
		}
	})

	t.Run("WithAPIKey", func(t *testing.T) {
		client, err := NewClientWithKey("test-key")
		if err != nil {
			t.Fatalf("Failed to create client: %v", err)
		}
		defer client.Close()

		if client.config.APIKey != "test-key" {
			t.Errorf("Expected APIKey test-key, got %s", client.config.APIKey)
		}
	})

	t.Run("InvalidURL", func(t *testing.T) {
		_, err := NewClient(&ClientConfig{
			BaseURL: "://invalid-url",
		})
		if err == nil {
			t.Error("Expected error for invalid URL")
		}
	})

	t.Run("CustomConfig", func(t *testing.T) {
		client, err := NewClient(&ClientConfig{
			BaseURL:    "http://localhost:8080",
			APIKey:     "test",
			Timeout:    60 * time.Second,
			MaxRetries: 5,
		})
		if err != nil {
			t.Fatalf("Failed to create client: %v", err)
		}
		defer client.Close()

		if client.config.Timeout != 60*time.Second {
			t.Errorf("Expected timeout 60s, got %v", client.config.Timeout)
		}
	})
}

// Test Health Endpoint

func TestHealth(t *testing.T) {
	expectedHealth := &Health{
		Status:    "healthy",
		Version:   "1.0.0",
		Timestamp: time.Now(),
		Uptime:    3600,
	}

	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			t.Errorf("Expected GET, got %s", r.Method)
		}
		if r.URL.Path != "/health" {
			t.Errorf("Expected path /health, got %s", r.URL.Path)
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(expectedHealth)
	})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx := context.Background()
	health, err := client.Health(ctx)
	if err != nil {
		t.Fatalf("Health check failed: %v", err)
	}

	if health.Status != expectedHealth.Status {
		t.Errorf("Expected status %s, got %s", expectedHealth.Status, health.Status)
	}
	if health.Version != expectedHealth.Version {
		t.Errorf("Expected version %s, got %s", expectedHealth.Version, health.Version)
	}
}

// Test Agent Operations

func TestListAgents(t *testing.T) {
	expectedAgents := []Agent{
		{AgentID: "agent-1", Name: "Agent One", Type: AgentTypeCompute, Status: AgentStatusActive},
		{AgentID: "agent-2", Name: "Agent Two", Type: AgentTypeValidator, Status: AgentStatusIdle},
	}

	expectedMeta := PaginationMeta{
		CurrentPage:  1,
		TotalPages:   5,
		TotalItems:   50,
		ItemsPerPage: 10,
		HasNext:      true,
		HasPrev:      false,
	}

	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			t.Errorf("Expected GET, got %s", r.Method)
		}
		if r.URL.Path != "/agents" {
			t.Errorf("Expected path /agents, got %s", r.URL.Path)
		}

		response := map[string]interface{}{
			"meta": expectedMeta,
			"data": expectedAgents,
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx := context.Background()
	opts := &ListOptions{Page: 1, Limit: 10}

	agents, meta, err := client.ListAgents(ctx, opts)
	if err != nil {
		t.Fatalf("ListAgents failed: %v", err)
	}

	if len(agents) != 2 {
		t.Errorf("Expected 2 agents, got %d", len(agents))
	}

	if meta.CurrentPage != expectedMeta.CurrentPage {
		t.Errorf("Expected page %d, got %d", expectedMeta.CurrentPage, meta.CurrentPage)
	}

	if !meta.HasNext {
		t.Error("Expected HasNext to be true")
	}
}

func TestGetAgent(t *testing.T) {
	expectedAgent := &Agent{
		AgentID:       "agent-123",
		Name:          "Test Agent",
		Type:          AgentTypeCompute,
		Status:        AgentStatusActive,
		Reputation:    85,
		TotalEarnings: 150.5,
	}

	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/agents/agent-123" {
			t.Errorf("Expected path /agents/agent-123, got %s", r.URL.Path)
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(expectedAgent)
	})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx := context.Background()
	agent, err := client.GetAgent(ctx, "agent-123")
	if err != nil {
		t.Fatalf("GetAgent failed: %v", err)
	}

	if agent.AgentID != expectedAgent.AgentID {
		t.Errorf("Expected AgentID %s, got %s", expectedAgent.AgentID, agent.AgentID)
	}
	if agent.Name != expectedAgent.Name {
		t.Errorf("Expected Name %s, got %s", expectedAgent.Name, agent.Name)
	}
}

func TestGetAgentNotFound(t *testing.T) {
	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"error": map[string]interface{}{
				"code":    "AGENT_NOT_FOUND",
				"message": "Agent not found",
			},
		})
	})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx := context.Background()
	_, err = client.GetAgent(ctx, "non-existent")

	if err == nil {
		t.Error("Expected error for non-existent agent")
	}

	if !IsNotFound(err) {
		t.Error("Expected IsNotFound to return true")
	}
}

func TestCreateAgent(t *testing.T) {
	createReq := &CreateAgentRequest{
		Name:        "New Agent",
		Description: "Test agent",
		Type:        AgentTypeCompute,
	}

	expectedAgent := &Agent{
		AgentID: "new-agent-id",
		Name:    createReq.Name,
		Type:    createReq.Type,
		Status:  AgentStatusIdle,
	}

	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("Expected POST, got %s", r.Method)
		}
		if r.URL.Path != "/agents" {
			t.Errorf("Expected path /agents, got %s", r.URL.Path)
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(expectedAgent)
	})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx := context.Background()
	agent, err := client.CreateAgent(ctx, createReq)
	if err != nil {
		t.Fatalf("CreateAgent failed: %v", err)
	}

	if agent.AgentID != expectedAgent.AgentID {
		t.Errorf("Expected AgentID %s, got %s", expectedAgent.AgentID, agent.AgentID)
	}
}

func TestCreateAgentValidation(t *testing.T) {
	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx := context.Background()

	// Test nil request
	_, err = client.CreateAgent(ctx, nil)
	if err == nil {
		t.Error("Expected error for nil request")
	}

	// Test empty name
	_, err = client.CreateAgent(ctx, &CreateAgentRequest{Name: ""})
	if err == nil {
		t.Error("Expected error for empty name")
	}
}

func TestUpdateAgent(t *testing.T) {
	updateReq := &UpdateAgentRequest{
		Status: AgentStatusBusy,
	}

	expectedAgent := &Agent{
		AgentID: "agent-123",
		Name:    "Updated Agent",
		Status:  AgentStatusBusy,
	}

	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPatch {
			t.Errorf("Expected PATCH, got %s", r.Method)
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(expectedAgent)
	})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx := context.Background()
	agent, err := client.UpdateAgent(ctx, "agent-123", updateReq)
	if err != nil {
		t.Fatalf("UpdateAgent failed: %v", err)
	}

	if agent.Status != AgentStatusBusy {
		t.Errorf("Expected status Busy, got %s", agent.Status)
	}
}

func TestDeleteAgent(t *testing.T) {
	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodDelete {
			t.Errorf("Expected DELETE, got %s", r.Method)
		}
		w.WriteHeader(http.StatusNoContent)
	})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx := context.Background()
	err = client.DeleteAgent(ctx, "agent-123")
	if err != nil {
		t.Fatalf("DeleteAgent failed: %v", err)
	}
}

// Test Task Operations

func TestListTasks(t *testing.T) {
	expectedTasks := []Task{
		{TaskID: "task-1", Title: "Task One", Status: TaskStatusPending, Reward: 10.0},
		{TaskID: "task-2", Title: "Task Two", Status: TaskStatusCompleted, Reward: 20.0},
	}

	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		response := map[string]interface{}{
			"meta": PaginationMeta{CurrentPage: 1, TotalItems: 2},
			"data": expectedTasks,
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx := context.Background()
	tasks, _, err := client.ListTasks(ctx, &ListOptions{})
	if err != nil {
		t.Fatalf("ListTasks failed: %v", err)
	}

	if len(tasks) != 2 {
		t.Errorf("Expected 2 tasks, got %d", len(tasks))
	}
}

func TestCreateTask(t *testing.T) {
	createReq := &CreateTaskRequest{
		Title:    "Test Task",
		Type:     TaskTypeValidation,
		Reward:   15.0,
		Deadline: time.Now().Add(24 * time.Hour),
	}

	expectedTask := &Task{
		TaskID: "new-task-id",
		Title:  createReq.Title,
		Status: TaskStatusPending,
	}

	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(expectedTask)
	})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx := context.Background()
	task, err := client.CreateTask(ctx, createReq)
	if err != nil {
		t.Fatalf("CreateTask failed: %v", err)
	}

	if task.TaskID != expectedTask.TaskID {
		t.Errorf("Expected TaskID %s, got %s", expectedTask.TaskID, task.TaskID)
	}
}

func TestCreateTaskValidation(t *testing.T) {
	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx := context.Background()

	// Test nil request
	_, err = client.CreateTask(ctx, nil)
	if err == nil {
		t.Error("Expected error for nil request")
	}

	// Test empty title
	_, err = client.CreateTask(ctx, &CreateTaskRequest{Title: ""})
	if err == nil {
		t.Error("Expected error for empty title")
	}

	// Test zero reward
	_, err = client.CreateTask(ctx, &CreateTaskRequest{
		Title:    "Test",
		Reward:   0,
		Deadline: time.Now(),
	})
	if err == nil {
		t.Error("Expected error for zero reward")
	}
}

func TestAssignTask(t *testing.T) {
	expectedTask := &Task{
		TaskID:  "task-123",
		AgentID: "agent-456",
		Status:  TaskStatusAssigned,
	}

	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(expectedTask)
	})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx := context.Background()
	task, err := client.AssignTask(ctx, "task-123", "agent-456")
	if err != nil {
		t.Fatalf("AssignTask failed: %v", err)
	}

	if task.AgentID != expectedTask.AgentID {
		t.Errorf("Expected AgentID %s, got %s", expectedTask.AgentID, task.AgentID)
	}
}

// Test Reward Operations

func TestListRewards(t *testing.T) {
	expectedRewards := []Reward{
		{RewardID: "reward-1", Amount: 10.0, Type: RewardTypeTaskCompletion, Status: RewardStatusPaid},
		{RewardID: "reward-2", Amount: 20.0, Type: RewardTypeValidation, Status: RewardStatusPending},
	}

	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		response := map[string]interface{}{
			"meta": PaginationMeta{CurrentPage: 1},
			"data": expectedRewards,
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx := context.Background()
	rewards, _, err := client.ListRewards(ctx, &ListOptions{})
	if err != nil {
		t.Fatalf("ListRewards failed: %v", err)
	}

	if len(rewards) != 2 {
		t.Errorf("Expected 2 rewards, got %d", len(rewards))
	}
}

func TestClaimReward(t *testing.T) {
	expectedReward := &Reward{
		RewardID: "reward-123",
		Amount:   50.0,
		Status:   RewardStatusProcessing,
	}

	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(expectedReward)
	})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx := context.Background()
	reward, err := client.ClaimReward(ctx, "reward-123")
	if err != nil {
		t.Fatalf("ClaimReward failed: %v", err)
	}

	if reward.Amount != expectedReward.Amount {
		t.Errorf("Expected amount %.2f, got %.2f", expectedReward.Amount, reward.Amount)
	}
}

// Test Economy Stats

func TestGetEconomyStats(t *testing.T) {
	expectedStats := &EconomyStats{
		TotalAgents:       100,
		ActiveAgents:      75,
		TotalTasks:        500,
		CompletedTasks:    450,
		TotalVolume:       10000.0,
		TotalRewards:      5000.0,
		AverageTaskReward: 10.0,
	}

	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(expectedStats)
	})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx := context.Background()
	stats, err := client.GetEconomyStats(ctx)
	if err != nil {
		t.Fatalf("GetEconomyStats failed: %v", err)
	}

	if stats.TotalAgents != expectedStats.TotalAgents {
		t.Errorf("Expected TotalAgents %d, got %d", expectedStats.TotalAgents, stats.TotalAgents)
	}
	if stats.TotalVolume != expectedStats.TotalVolume {
		t.Errorf("Expected TotalVolume %.2f, got %.2f", expectedStats.TotalVolume, stats.TotalVolume)
	}
}

// Test Error Handling

func TestAPIError(t *testing.T) {
	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"error": map[string]interface{}{
				"code":    "VALIDATION_ERROR",
				"message": "Invalid input",
				"details": map[string]interface{}{
					"field":  "name",
					"reason": "required",
				},
			},
		})
	})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx := context.Background()
	_, err = client.GetAgent(ctx, "invalid")

	if err == nil {
		t.Fatal("Expected error")
	}

	var apiErr *APIError
	if !errors.As(err, &apiErr) {
		t.Fatal("Expected APIError")
	}

	if apiErr.StatusCode != http.StatusBadRequest {
		t.Errorf("Expected status 400, got %d", apiErr.StatusCode)
	}
	if apiErr.Code != "VALIDATION_ERROR" {
		t.Errorf("Expected code VALIDATION_ERROR, got %s", apiErr.Code)
	}
}

func TestRateLimitError(t *testing.T) {
	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Retry-After", "60")
		w.WriteHeader(http.StatusTooManyRequests)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"error": map[string]interface{}{
				"code":    "RATE_LIMITED",
				"message": "Too many requests",
			},
		})
	})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx := context.Background()
	_, err = client.Health(ctx)

	if err == nil {
		t.Fatal("Expected error")
	}

	if !IsRateLimited(err) {
		t.Error("Expected IsRateLimited to return true")
	}
}

func TestRetryExhausted(t *testing.T) {
	attempts := 0
	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		w.WriteHeader(http.StatusServiceUnavailable)
	})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()

	// Configure client with minimal retries
	client.maxRetries = 2
	client.retryWait = 10 * time.Millisecond
	client.maxRetryWait = 50 * time.Millisecond

	ctx := context.Background()
	_, err = client.Health(ctx)

	if err == nil {
		t.Fatal("Expected error")
	}

	// Should have tried 3 times (1 initial + 2 retries)
	if attempts != 3 {
		t.Errorf("Expected 3 attempts, got %d", attempts)
	}
}

// Test Context Cancellation

func TestContextCancellation(t *testing.T) {
	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(100 * time.Millisecond)
	})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx, cancel := context.WithCancel(context.Background())
	cancel() // Cancel immediately

	_, err = client.Health(ctx)
	if err == nil {
		t.Error("Expected error from cancelled context")
	}
}

func TestContextTimeout(t *testing.T) {
	server, client, err := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(200 * time.Millisecond)
	})
	if err != nil {
		t.Fatalf("Failed to create test server: %v", err)
	}
	defer server.Close()
	defer client.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()

	_, err = client.Health(ctx)
	if err == nil {
		t.Error("Expected error from timed out context")
	}

	if !IsTimeout(err) {
		t.Error("Expected IsTimeout to return true")
	}
}

// Test Pagination Helpers

func TestBuildQueryParams(t *testing.T) {
	tests := []struct {
		name     string
		params   map[string]string
		want     string
		wantBoth []string // For order-independent checks
	}{
		{"Empty", map[string]string{}, "", nil},
		{"Single", map[string]string{"page": "1"}, "?page=1", nil},
		{"Multiple", map[string]string{"page": "1", "limit": "10"}, "", []string{"page=1", "limit=10"}},
		{"WithEmpty", map[string]string{"page": "1", "empty": ""}, "?page=1", nil},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := buildQueryParams(tt.params)
			if tt.wantBoth != nil {
				// Order-independent check
				for _, want := range tt.wantBoth {
					if !containsParam(got, want) {
						t.Errorf("buildQueryParams() = %v, should contain %v", got, want)
					}
				}
			} else if got != tt.want {
				t.Errorf("buildQueryParams() = %v, want %v", got, tt.want)
			}
		})
	}
}

// containsParam checks if a query string contains a specific parameter.
func containsParam(query, param string) bool {
	return len(query) > 1 && contains(query[1:], param)
}

// contains checks if a string contains a substring (simple implementation).
func contains(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

func TestApplyListOptions(t *testing.T) {
	opts := &ListOptions{
		Page:      1,
		Limit:     20,
		SortBy:    "created_at",
		SortOrder: "desc",
		Filter: map[string]string{
			"status": "active",
			"type":   "compute",
		},
	}

	params := applyListOptions(opts)

	if params["page"] != "1" {
		t.Errorf("Expected page=1, got %s", params["page"])
	}
	if params["limit"] != "20" {
		t.Errorf("Expected limit=20, got %s", params["limit"])
	}
	if params["sort_by"] != "created_at" {
		t.Errorf("Expected sort_by=created_at, got %s", params["sort_by"])
	}
	if params["sort_order"] != "desc" {
		t.Errorf("Expected sort_order=desc, got %s", params["sort_order"])
	}
	if params["status"] != "active" {
		t.Errorf("Expected status=active, got %s", params["status"])
	}
}

func TestNilListOptions(t *testing.T) {
	params := applyListOptions(nil)
	if len(params) != 0 {
		t.Errorf("Expected empty params for nil options, got %v", params)
	}
}

// Test Error Type Checks

func TestIsNotFound(t *testing.T) {
	tests := []struct {
		name string
		err  error
		want bool
	}{
		{"NilError", nil, false},
		{"ErrAgentNotFound", ErrAgentNotFound, true},
		{"ErrTaskNotFound", ErrTaskNotFound, true},
		{"APIError404", &APIError{StatusCode: 404}, true},
		{"APIError500", &APIError{StatusCode: 500}, false},
		{"GenericError", errors.New("generic"), false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := IsNotFound(tt.err); got != tt.want {
				t.Errorf("IsNotFound() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestIsRateLimited(t *testing.T) {
	tests := []struct {
		name string
		err  error
		want bool
	}{
		{"NilError", nil, false},
		{"ErrRateLimited", ErrRateLimited, true},
		{"APIError429", &APIError{StatusCode: 429}, true},
		{"APIError400", &APIError{StatusCode: 400}, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := IsRateLimited(tt.err); got != tt.want {
				t.Errorf("IsRateLimited() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestIsRetryable(t *testing.T) {
	tests := []struct {
		name string
		err  error
		want bool
	}{
		{"TimeoutError", &TimeoutError{Message: "test"}, true},
		{"RateLimited", ErrRateLimited, true},
		{"APIError503", &APIError{StatusCode: 503, Category: ErrorCategoryServer}, true},
		{"APIError400", &APIError{StatusCode: 400}, false},
		{"NetworkError", &NetworkError{Message: "test"}, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := IsRetryable(tt.err); got != tt.want {
				t.Errorf("IsRetryable() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestGetRetryAfter(t *testing.T) {
	tests := []struct {
		name string
		err  error
		want time.Duration
	}{
		{"NilError", nil, 0},
		{"NoRetryAfter", &APIError{}, 0},
		{"WithRetryAfter", &APIError{RetryAfter: 60 * time.Second}, 60 * time.Second},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := GetRetryAfter(tt.err); got != tt.want {
				t.Errorf("GetRetryAfter() = %v, want %v", got, tt.want)
			}
		})
	}
}

// Test APIError Methods

func TestAPIErrorError(t *testing.T) {
	err := &APIError{
		StatusCode: 400,
		Code:       "TEST_ERROR",
		Message:    "Test message",
	}

	expected := "agenteco: TEST_ERROR (HTTP 400): Test message"
	if err.Error() != expected {
		t.Errorf("Expected %s, got %s", expected, err.Error())
	}
}

func TestAPIErrorTemporary(t *testing.T) {
	tests := []struct {
		name     string
		category ErrorCategory
		status   int
		want     bool
	}{
		{"Network", ErrorCategoryNetwork, 0, true},
		{"Timeout", ErrorCategoryTimeout, 0, true},
		{"RateLimit", ErrorCategoryRateLimit, 429, true},
		{"Server503", ErrorCategoryServer, 503, true},
		{"Server502", ErrorCategoryServer, 502, true},
		{"Server504", ErrorCategoryServer, 504, true},
		{"Server500", ErrorCategoryServer, 500, false},
		{"Client", ErrorCategoryClient, 400, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := &APIError{
				Category:   tt.category,
				StatusCode: tt.status,
			}
			if got := err.Temporary(); got != tt.want {
				t.Errorf("Temporary() = %v, want %v", got, tt.want)
			}
		})
	}
}
