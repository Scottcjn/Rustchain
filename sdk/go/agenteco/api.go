package agenteco

import (
	"context"
	"fmt"
	"net/http"
	"time"
)

// Agents API

// ListAgents retrieves a paginated list of agents.
// Options can include filters for type, status, owner, etc.
func (c *Client) ListAgents(ctx context.Context, opts *ListOptions) ([]Agent, *PaginationMeta, error) {
	params := applyListOptions(opts)
	path := "/agents" + buildQueryParams(params)

	var result struct {
		Meta PaginationMeta `json:"meta"`
		Data []Agent        `json:"data"`
	}

	if err := c.doRequest(ctx, http.MethodGet, path, nil, &result); err != nil {
		return nil, nil, err
	}

	return result.Data, &result.Meta, nil
}

// GetAgent retrieves a specific agent by ID.
func (c *Client) GetAgent(ctx context.Context, agentID string) (*Agent, error) {
	if agentID == "" {
		return nil, ErrInvalidAgentID
	}

	path := fmt.Sprintf("/agents/%s", agentID)
	var agent Agent

	if err := c.doRequest(ctx, http.MethodGet, path, nil, &agent); err != nil {
		return nil, err
	}

	return &agent, nil
}

// CreateAgentRequest holds parameters for creating a new agent.
type CreateAgentRequest struct {
	// Name is the human-readable name of the agent.
	Name string `json:"name"`
	// Description provides details about the agent's capabilities.
	Description string `json:"description"`
	// Type categorizes the agent.
	Type AgentType `json:"type"`
	// Metadata contains additional agent-specific information.
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// CreateAgent registers a new agent in the economy.
func (c *Client) CreateAgent(ctx context.Context, req *CreateAgentRequest) (*Agent, error) {
	if req == nil {
		return nil, &ClientError{Message: "request is required"}
	}
	if req.Name == "" {
		return nil, &ClientError{Message: "agent name is required"}
	}

	path := "/agents"
	var agent Agent

	if err := c.doRequest(ctx, http.MethodPost, path, req, &agent); err != nil {
		return nil, err
	}

	return &agent, nil
}

// UpdateAgentRequest holds parameters for updating an agent.
type UpdateAgentRequest struct {
	// Name is the updated name (optional).
	Name string `json:"name,omitempty"`
	// Description is the updated description (optional).
	Description string `json:"description,omitempty"`
	// Status is the updated status (optional).
	Status AgentStatus `json:"status,omitempty"`
	// Metadata is the updated metadata (optional, merges with existing).
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// UpdateAgent updates an existing agent.
func (c *Client) UpdateAgent(ctx context.Context, agentID string, req *UpdateAgentRequest) (*Agent, error) {
	if agentID == "" {
		return nil, ErrInvalidAgentID
	}
	if req == nil {
		return nil, &ClientError{Message: "request is required"}
	}

	path := fmt.Sprintf("/agents/%s", agentID)
	var agent Agent

	if err := c.doRequest(ctx, http.MethodPatch, path, req, &agent); err != nil {
		return nil, err
	}

	return &agent, nil
}

// DeleteAgent removes an agent from the economy.
func (c *Client) DeleteAgent(ctx context.Context, agentID string) error {
	if agentID == "" {
		return ErrInvalidAgentID
	}

	path := fmt.Sprintf("/agents/%s", agentID)
	return c.doRequest(ctx, http.MethodDelete, path, nil, nil)
}

// GetAgentMetrics retrieves performance metrics for an agent.
func (c *Client) GetAgentMetrics(ctx context.Context, agentID string, periodStart, periodEnd time.Time) (*AgentMetrics, error) {
	if agentID == "" {
		return nil, ErrInvalidAgentID
	}

	params := map[string]string{
		"period_start": periodStart.Format(time.RFC3339),
		"period_end":   periodEnd.Format(time.RFC3339),
	}
	path := fmt.Sprintf("/agents/%s/metrics%s", agentID, buildQueryParams(params))

	var metrics AgentMetrics
	if err := c.doRequest(ctx, http.MethodGet, path, nil, &metrics); err != nil {
		return nil, err
	}

	return &metrics, nil
}

// Tasks API

// ListTasks retrieves a paginated list of tasks.
func (c *Client) ListTasks(ctx context.Context, opts *ListOptions) ([]Task, *PaginationMeta, error) {
	params := applyListOptions(opts)
	path := "/tasks" + buildQueryParams(params)

	var result struct {
		Meta PaginationMeta `json:"meta"`
		Data []Task         `json:"data"`
	}

	if err := c.doRequest(ctx, http.MethodGet, path, nil, &result); err != nil {
		return nil, nil, err
	}

	return result.Data, &result.Meta, nil
}

// GetTask retrieves a specific task by ID.
func (c *Client) GetTask(ctx context.Context, taskID string) (*Task, error) {
	if taskID == "" {
		return nil, ErrInvalidTaskID
	}

	path := fmt.Sprintf("/tasks/%s", taskID)
	var task Task

	if err := c.doRequest(ctx, http.MethodGet, path, nil, &task); err != nil {
		return nil, err
	}

	return &task, nil
}

// CreateTaskRequest holds parameters for creating a new task.
type CreateTaskRequest struct {
	// Title is a short description of the task.
	Title string `json:"title"`
	// Description provides detailed task requirements.
	Description string `json:"description"`
	// Type categorizes the task.
	Type TaskType `json:"type"`
	// Priority indicates task urgency (1-10).
	Priority int `json:"priority,omitempty"`
	// Reward is the payment for task completion.
	Reward float64 `json:"reward"`
	// Deadline is the completion deadline.
	Deadline time.Time `json:"deadline"`
	// AgentID is the optional agent to assign (defaults to open marketplace).
	AgentID string `json:"agent_id,omitempty"`
	// Metadata contains additional task-specific information.
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// CreateTask creates a new task in the economy.
func (c *Client) CreateTask(ctx context.Context, req *CreateTaskRequest) (*Task, error) {
	if req == nil {
		return nil, &ClientError{Message: "request is required"}
	}
	if req.Title == "" {
		return nil, &ClientError{Message: "task title is required"}
	}
	if req.Reward <= 0 {
		return nil, &ClientError{Message: "reward must be positive"}
	}
	if req.Deadline.IsZero() {
		return nil, &ClientError{Message: "deadline is required"}
	}

	path := "/tasks"
	var task Task

	if err := c.doRequest(ctx, http.MethodPost, path, req, &task); err != nil {
		return nil, err
	}

	return &task, nil
}

// AssignTask assigns a task to a specific agent.
func (c *Client) AssignTask(ctx context.Context, taskID, agentID string) (*Task, error) {
	if taskID == "" {
		return nil, ErrInvalidTaskID
	}
	if agentID == "" {
		return nil, ErrInvalidAgentID
	}

	path := fmt.Sprintf("/tasks/%s/assign", taskID)
	req := map[string]string{"agent_id": agentID}
	var task Task

	if err := c.doRequest(ctx, http.MethodPost, path, req, &task); err != nil {
		return nil, err
	}

	return &task, nil
}

// UpdateTaskStatusRequest holds parameters for updating task status.
type UpdateTaskStatusRequest struct {
	// Status is the new task status.
	Status TaskStatus `json:"status"`
	// Result contains the task output (for completed tasks).
	Result interface{} `json:"result,omitempty"`
	// ErrorMessage contains failure details (for failed tasks).
	ErrorMessage string `json:"error_message,omitempty"`
}

// UpdateTaskStatus updates the status of a task.
func (c *Client) UpdateTaskStatus(ctx context.Context, taskID string, req *UpdateTaskStatusRequest) (*Task, error) {
	if taskID == "" {
		return nil, ErrInvalidTaskID
	}
	if req == nil {
		return nil, &ClientError{Message: "request is required"}
	}

	path := fmt.Sprintf("/tasks/%s/status", taskID)
	var task Task

	if err := c.doRequest(ctx, http.MethodPatch, path, req, &task); err != nil {
		return nil, err
	}

	return &task, nil
}

// CancelTask cancels a pending or in-progress task.
func (c *Client) CancelTask(ctx context.Context, taskID string) (*Task, error) {
	if taskID == "" {
		return nil, ErrInvalidTaskID
	}

	path := fmt.Sprintf("/tasks/%s/cancel", taskID)
	var task Task

	if err := c.doRequest(ctx, http.MethodPost, path, nil, &task); err != nil {
		return nil, err
	}

	return &task, nil
}

// GetTaskResult retrieves the result of a completed task.
func (c *Client) GetTaskResult(ctx context.Context, taskID string) (interface{}, error) {
	if taskID == "" {
		return nil, ErrInvalidTaskID
	}

	path := fmt.Sprintf("/tasks/%s/result", taskID)
	var result struct {
		TaskID string      `json:"task_id"`
		Result interface{} `json:"result"`
	}

	if err := c.doRequest(ctx, http.MethodGet, path, nil, &result); err != nil {
		return nil, err
	}

	return result.Result, nil
}

// Rewards API

// ListRewards retrieves a paginated list of rewards.
func (c *Client) ListRewards(ctx context.Context, opts *ListOptions) ([]Reward, *PaginationMeta, error) {
	params := applyListOptions(opts)
	path := "/rewards" + buildQueryParams(params)

	var result struct {
		Meta PaginationMeta `json:"meta"`
		Data []Reward       `json:"data"`
	}

	if err := c.doRequest(ctx, http.MethodGet, path, nil, &result); err != nil {
		return nil, nil, err
	}

	return result.Data, &result.Meta, nil
}

// GetAgentRewards retrieves rewards for a specific agent.
func (c *Client) GetAgentRewards(ctx context.Context, agentID string, opts *ListOptions) ([]Reward, *PaginationMeta, error) {
	if agentID == "" {
		return nil, nil, ErrInvalidAgentID
	}

	params := applyListOptions(opts)
	path := fmt.Sprintf("/agents/%s/rewards%s", agentID, buildQueryParams(params))

	var result struct {
		Meta PaginationMeta `json:"meta"`
		Data []Reward       `json:"data"`
	}

	if err := c.doRequest(ctx, http.MethodGet, path, nil, &result); err != nil {
		return nil, nil, err
	}

	return result.Data, &result.Meta, nil
}

// ClaimReward claims a pending reward for distribution.
func (c *Client) ClaimReward(ctx context.Context, rewardID string) (*Reward, error) {
	if rewardID == "" {
		return nil, &ClientError{Message: "reward ID is required"}
	}

	path := fmt.Sprintf("/rewards/%s/claim", rewardID)
	var reward Reward

	if err := c.doRequest(ctx, http.MethodPost, path, nil, &reward); err != nil {
		return nil, err
	}

	return &reward, nil
}

// GetRewardHistory retrieves the reward history for an agent.
func (c *Client) GetRewardHistory(ctx context.Context, agentID string, startTime, endTime time.Time) ([]Reward, error) {
	if agentID == "" {
		return nil, ErrInvalidAgentID
	}

	params := map[string]string{
		"start_time": startTime.Format(time.RFC3339),
		"end_time":   endTime.Format(time.RFC3339),
	}
	path := fmt.Sprintf("/agents/%s/reward-history%s", agentID, buildQueryParams(params))

	var result struct {
		Data []Reward `json:"data"`
	}

	if err := c.doRequest(ctx, http.MethodGet, path, nil, &result); err != nil {
		return nil, err
	}

	return result.Data, nil
}

// Marketplace API

// ListListings retrieves a paginated list of marketplace listings.
func (c *Client) ListListings(ctx context.Context, opts *ListOptions) ([]MarketplaceListing, *PaginationMeta, error) {
	params := applyListOptions(opts)
	path := "/marketplace/listings" + buildQueryParams(params)

	var result struct {
		Meta PaginationMeta       `json:"meta"`
		Data []MarketplaceListing `json:"data"`
	}

	if err := c.doRequest(ctx, http.MethodGet, path, nil, &result); err != nil {
		return nil, nil, err
	}

	return result.Data, &result.Meta, nil
}

// GetListing retrieves a specific marketplace listing.
func (c *Client) GetListing(ctx context.Context, listingID string) (*MarketplaceListing, error) {
	if listingID == "" {
		return nil, &ClientError{Message: "listing ID is required"}
	}

	path := fmt.Sprintf("/marketplace/listings/%s", listingID)
	var listing MarketplaceListing

	if err := c.doRequest(ctx, http.MethodGet, path, nil, &listing); err != nil {
		return nil, err
	}

	return &listing, nil
}

// CreateListingRequest holds parameters for creating a marketplace listing.
type CreateListingRequest struct {
	// AgentID is the agent being offered.
	AgentID string `json:"agent_id"`
	// Title is a short description of the service.
	Title string `json:"title"`
	// Description provides detailed service information.
	Description string `json:"description"`
	// Category categorizes the service.
	Category string `json:"category"`
	// PriceType indicates how pricing works.
	PriceType PriceType `json:"price_type"`
	// Price is the base price for the service.
	Price float64 `json:"price"`
	// Currency is the payment token (default: "RTC").
	Currency string `json:"currency,omitempty"`
}

// CreateListing creates a new marketplace listing.
func (c *Client) CreateListing(ctx context.Context, req *CreateListingRequest) (*MarketplaceListing, error) {
	if req == nil {
		return nil, &ClientError{Message: "request is required"}
	}
	if req.AgentID == "" {
		return nil, &ClientError{Message: "agent ID is required"}
	}
	if req.Title == "" {
		return nil, &ClientError{Message: "listing title is required"}
	}
	if req.Price <= 0 {
		return nil, &ClientError{Message: "price must be positive"}
	}

	path := "/marketplace/listings"
	var listing MarketplaceListing

	if err := c.doRequest(ctx, http.MethodPost, path, req, &listing); err != nil {
		return nil, err
	}

	return &listing, nil
}

// UpdateListingRequest holds parameters for updating a listing.
type UpdateListingRequest struct {
	// Title is the updated title (optional).
	Title string `json:"title,omitempty"`
	// Description is the updated description (optional).
	Description string `json:"description,omitempty"`
	// Price is the updated price (optional).
	Price float64 `json:"price,omitempty"`
	// Status is the updated status (optional).
	Status ListingStatus `json:"status,omitempty"`
}

// UpdateListing updates an existing marketplace listing.
func (c *Client) UpdateListing(ctx context.Context, listingID string, req *UpdateListingRequest) (*MarketplaceListing, error) {
	if listingID == "" {
		return nil, &ClientError{Message: "listing ID is required"}
	}
	if req == nil {
		return nil, &ClientError{Message: "request is required"}
	}

	path := fmt.Sprintf("/marketplace/listings/%s", listingID)
	var listing MarketplaceListing

	if err := c.doRequest(ctx, http.MethodPatch, path, req, &listing); err != nil {
		return nil, err
	}

	return &listing, nil
}

// DeleteListing removes a marketplace listing.
func (c *Client) DeleteListing(ctx context.Context, listingID string) error {
	if listingID == "" {
		return &ClientError{Message: "listing ID is required"}
	}

	path := fmt.Sprintf("/marketplace/listings/%s", listingID)
	return c.doRequest(ctx, http.MethodDelete, path, nil, nil)
}

// HireAgent hires an agent from the marketplace.
func (c *Client) HireAgent(ctx context.Context, listingID string, taskReq *CreateTaskRequest) (*Task, error) {
	if listingID == "" {
		return nil, &ClientError{Message: "listing ID is required"}
	}
	if taskReq == nil {
		return nil, &ClientError{Message: "task request is required"}
	}

	path := fmt.Sprintf("/marketplace/listings/%s/hire", listingID)
	var task Task

	if err := c.doRequest(ctx, http.MethodPost, path, taskReq, &task); err != nil {
		return nil, err
	}

	return &task, nil
}

// Economy Stats API

// GetEconomyStats retrieves aggregate statistics for the agent economy.
func (c *Client) GetEconomyStats(ctx context.Context) (*EconomyStats, error) {
	path := "/stats"
	var stats EconomyStats

	if err := c.doRequest(ctx, http.MethodGet, path, nil, &stats); err != nil {
		return nil, err
	}

	return &stats, nil
}

// GetAgentEconomyStats retrieves economy statistics for a specific agent.
func (c *Client) GetAgentEconomyStats(ctx context.Context, agentID string) (*EconomyStats, error) {
	if agentID == "" {
		return nil, ErrInvalidAgentID
	}

	path := fmt.Sprintf("/agents/%s/stats", agentID)
	var stats EconomyStats

	if err := c.doRequest(ctx, http.MethodGet, path, nil, &stats); err != nil {
		return nil, err
	}

	return &stats, nil
}

// Health API

// Health represents the health status of the API.
type Health struct {
	// Status is the overall health status.
	Status string `json:"status"`
	// Version is the API version.
	Version string `json:"version"`
	// Timestamp is the current server time.
	Timestamp time.Time `json:"timestamp"`
	// Uptime is the server uptime in seconds.
	Uptime int64 `json:"uptime"`
}

// Health checks the API health status.
func (c *Client) Health(ctx context.Context) (*Health, error) {
	path := "/health"
	var health Health

	if err := c.doRequest(ctx, http.MethodGet, path, nil, &health); err != nil {
		return nil, err
	}

	return &health, nil
}

// Version returns the API version information.
func (c *Client) Version(ctx context.Context) (string, error) {
	health, err := c.Health(ctx)
	if err != nil {
		return "", err
	}
	return health.Version, nil
}
