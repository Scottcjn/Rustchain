// Package agenteco provides a Go client for the RustChain RIP-302 Agent Economy APIs.
//
// The Agent Economy enables autonomous agents to participate in the RustChain network,
// earning rewards for completing tasks, providing services, and contributing to the ecosystem.
package agenteco

import (
	"time"
)

// Agent represents an autonomous agent in the RustChain network.
type Agent struct {
	// AgentID is the unique identifier for the agent.
	AgentID string `json:"agent_id"`
	// Owner is the wallet address of the agent owner.
	Owner string `json:"owner"`
	// Name is the human-readable name of the agent.
	Name string `json:"name"`
	// Description provides details about the agent's capabilities.
	Description string `json:"description"`
	// Type categorizes the agent (e.g., "validator", "oracle", "compute", "storage").
	Type AgentType `json:"type"`
	// Status indicates the current operational status.
	Status AgentStatus `json:"status"`
	// Reputation is the agent's trust score (0-100).
	Reputation int `json:"reputation"`
	// TotalEarnings is the cumulative rewards earned by the agent.
	TotalEarnings float64 `json:"total_earnings"`
	// ActiveTasks is the number of currently assigned tasks.
	ActiveTasks int `json:"active_tasks"`
	// CompletedTasks is the total number of tasks completed.
	CompletedTasks int `json:"completed_tasks"`
	// CreatedAt is the timestamp when the agent was registered.
	CreatedAt time.Time `json:"created_at"`
	// LastActiveAt is the timestamp of the last agent activity.
	LastActiveAt time.Time `json:"last_active_at"`
	// Metadata contains additional agent-specific information.
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// AgentType represents the category of an agent.
type AgentType string

const (
	// AgentTypeValidator performs block validation and consensus.
	AgentTypeValidator AgentType = "validator"
	// AgentTypeOracle provides external data feeds.
	AgentTypeOracle AgentType = "oracle"
	// AgentTypeCompute offers computational resources.
	AgentTypeCompute AgentType = "compute"
	// AgentTypeStorage provides data storage services.
	AgentTypeStorage AgentType = "storage"
	// AgentTypeService performs custom tasks.
	AgentTypeService AgentType = "service"
	// AgentTypeUnknown indicates an unspecified agent type.
	AgentTypeUnknown AgentType = "unknown"
)

// AgentStatus represents the operational status of an agent.
type AgentStatus string

const (
	// AgentStatusActive indicates the agent is operational.
	AgentStatusActive AgentStatus = "active"
	// AgentStatusIdle indicates the agent is available but not working.
	AgentStatusIdle AgentStatus = "idle"
	// AgentStatusBusy indicates the agent is currently processing tasks.
	AgentStatusBusy AgentStatus = "busy"
	// AgentStatusOffline indicates the agent is not reachable.
	AgentStatusOffline AgentStatus = "offline"
	// AgentStatusSuspended indicates the agent is temporarily disabled.
	AgentStatusSuspended AgentStatus = "suspended"
	// AgentStatusTerminated indicates the agent is permanently disabled.
	AgentStatusTerminated AgentStatus = "terminated"
)

// Task represents a work item assigned to an agent.
type Task struct {
	// TaskID is the unique identifier for the task.
	TaskID string `json:"task_id"`
	// AgentID is the agent assigned to this task.
	AgentID string `json:"agent_id"`
	// Requester is the wallet address of the task requester.
	Requester string `json:"requester"`
	// Title is a short description of the task.
	Title string `json:"title"`
	// Description provides detailed task requirements.
	Description string `json:"description"`
	// Type categorizes the task.
	Type TaskType `json:"type"`
	// Status indicates the current task state.
	Status TaskStatus `json:"status"`
	// Priority indicates task urgency (1-10, 10 being highest).
	Priority int `json:"priority"`
	// Reward is the payment for task completion.
	Reward float64 `json:"reward"`
	// Deadline is the timestamp by which the task must be completed.
	Deadline time.Time `json:"deadline"`
	// CreatedAt is the timestamp when the task was created.
	CreatedAt time.Time `json:"created_at"`
	// StartedAt is the timestamp when work began.
	StartedAt *time.Time `json:"started_at,omitempty"`
	// CompletedAt is the timestamp when the task was completed.
	CompletedAt *time.Time `json:"completed_at,omitempty"`
	// Result contains the task output upon completion.
	Result interface{} `json:"result,omitempty"`
	// ErrorMessage contains failure details if the task failed.
	ErrorMessage string `json:"error_message,omitempty"`
	// Metadata contains additional task-specific information.
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// TaskType represents the category of a task.
type TaskType string

const (
	// TaskTypeValidation involves block or transaction validation.
	TaskTypeValidation TaskType = "validation"
	// TaskTypeComputation involves computational work.
	TaskTypeComputation TaskType = "computation"
	// TaskTypeDataFetch involves retrieving external data.
	TaskTypeDataFetch TaskType = "data_fetch"
	// TaskTypeStorage involves storing or retrieving data.
	TaskTypeStorage TaskType = "storage"
	// TaskTypeCustom involves user-defined work.
	TaskTypeCustom TaskType = "custom"
)

// TaskStatus represents the state of a task.
type TaskStatus string

const (
	// TaskStatusPending indicates the task is awaiting assignment.
	TaskStatusPending TaskStatus = "pending"
	// TaskStatusAssigned indicates the task is assigned to an agent.
	TaskStatusAssigned TaskStatus = "assigned"
	// TaskStatusInProgress indicates the agent is working on the task.
	TaskStatusInProgress TaskStatus = "in_progress"
	// TaskStatusCompleted indicates the task finished successfully.
	TaskStatusCompleted TaskStatus = "completed"
	// TaskStatusFailed indicates the task encountered an error.
	TaskStatusFailed TaskStatus = "failed"
	// TaskStatusCancelled indicates the task was cancelled.
	TaskStatusCancelled TaskStatus = "cancelled"
	// TaskStatusExpired indicates the task passed its deadline.
	TaskStatusExpired TaskStatus = "expired"
)

// Reward represents a payment event in the agent economy.
type Reward struct {
	// RewardID is the unique identifier for the reward.
	RewardID string `json:"reward_id"`
	// AgentID is the agent that earned the reward.
	AgentID string `json:"agent_id"`
	// TaskID is the task that generated the reward (if applicable).
	TaskID string `json:"task_id,omitempty"`
	// Amount is the reward value in RTC.
	Amount float64 `json:"amount"`
	// Type categorizes the reward source.
	Type RewardType `json:"type"`
	// Status indicates the reward payment state.
	Status RewardStatus `json:"status"`
	// CreatedAt is the timestamp when the reward was issued.
	CreatedAt time.Time `json:"created_at"`
	// PaidAt is the timestamp when the reward was distributed.
	PaidAt *time.Time `json:"paid_at,omitempty"`
	// TransactionHash is the blockchain transaction ID (if paid).
	TransactionHash string `json:"transaction_hash,omitempty"`
	// Description provides details about the reward.
	Description string `json:"description,omitempty"`
}

// RewardType represents the source of a reward.
type RewardType string

const (
	// RewardTypeTaskCompletion is earned from completing tasks.
	RewardTypeTaskCompletion RewardType = "task_completion"
	// RewardTypeValidation is earned from validating blocks.
	RewardTypeValidation RewardType = "validation"
	// RewardTypeStaking is earned from staking tokens.
	RewardTypeStaking RewardType = "staking"
	// RewardTypeReferral is earned from referring new agents.
	RewardTypeReferral RewardType = "referral"
	// RewardTypeBonus is a special bonus reward.
	RewardTypeBonus RewardType = "bonus"
	// RewardTypeGovernance is earned from governance participation.
	RewardTypeGovernance RewardType = "governance"
)

// RewardStatus represents the payment state of a reward.
type RewardStatus string

const (
	// RewardStatusPending indicates the reward is awaiting payment.
	RewardStatusPending RewardStatus = "pending"
	// RewardStatusProcessing indicates the payment is being processed.
	RewardStatusProcessing RewardStatus = "processing"
	// RewardStatusPaid indicates the reward has been distributed.
	RewardStatusPaid RewardStatus = "paid"
	// RewardStatusFailed indicates the payment failed.
	RewardStatusFailed RewardStatus = "failed"
)

// MarketplaceListing represents an agent service available for hire.
type MarketplaceListing struct {
	// ListingID is the unique identifier for the listing.
	ListingID string `json:"listing_id"`
	// AgentID is the agent being offered.
	AgentID string `json:"agent_id"`
	// Owner is the wallet address of the listing owner.
	Owner string `json:"owner"`
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
	Currency string `json:"currency"`
	// Status indicates the listing state.
	Status ListingStatus `json:"status"`
	// TotalHires is the number of times the service has been hired.
	TotalHires int `json:"total_hires"`
	// AverageRating is the average customer rating (0-5).
	AverageRating float64 `json:"average_rating"`
	// CreatedAt is the timestamp when the listing was created.
	CreatedAt time.Time `json:"created_at"`
	// UpdatedAt is the timestamp of the last update.
	UpdatedAt time.Time `json:"updated_at"`
}

// PriceType represents the pricing model for a listing.
type PriceType string

const (
	// PriceTypeFixed indicates a fixed price per task.
	PriceTypeFixed PriceType = "fixed"
	// PriceTypeHourly indicates pricing per hour.
	PriceTypeHourly PriceType = "hourly"
	// PriceTypeAuction indicates price is determined by bidding.
	PriceTypeAuction PriceType = "auction"
	// PriceTypeDynamic indicates price varies based on demand.
	PriceTypeDynamic PriceType = "dynamic"
)

// ListingStatus represents the state of a marketplace listing.
type ListingStatus string

const (
	// ListingStatusActive indicates the listing is available.
	ListingStatusActive ListingStatus = "active"
	// ListingStatusInactive indicates the listing is hidden.
	ListingStatusInactive ListingStatus = "inactive"
	// ListingStatusSuspended indicates the listing is temporarily disabled.
	ListingStatusSuspended ListingStatus = "suspended"
	// ListingStatusDeleted indicates the listing is removed.
	ListingStatusDeleted ListingStatus = "deleted"
)

// EconomyStats provides aggregate statistics for the agent economy.
type EconomyStats struct {
	// TotalAgents is the number of registered agents.
	TotalAgents int `json:"total_agents"`
	// ActiveAgents is the number of currently active agents.
	ActiveAgents int `json:"active_agents"`
	// TotalTasks is the total number of tasks created.
	TotalTasks int `json:"total_tasks"`
	// PendingTasks is the number of tasks awaiting assignment.
	PendingTasks int `json:"pending_tasks"`
	// CompletedTasks is the number of successfully completed tasks.
	CompletedTasks int `json:"completed_tasks"`
	// TotalVolume is the total value transacted in the economy.
	TotalVolume float64 `json:"total_volume"`
	// TotalRewards is the cumulative rewards distributed.
	TotalRewards float64 `json:"total_rewards"`
	// AverageTaskReward is the mean reward per task.
	AverageTaskReward float64 `json:"average_task_reward"`
	// AverageCompletionTime is the mean task completion time in seconds.
	AverageCompletionTime float64 `json:"average_completion_time"`
	// Epoch is the current economy epoch.
	Epoch int `json:"epoch"`
	// LastUpdated is the timestamp of the last statistics update.
	LastUpdated time.Time `json:"last_updated"`
}

// AgentMetrics provides performance metrics for an agent.
type AgentMetrics struct {
	// AgentID is the agent being measured.
	AgentID string `json:"agent_id"`
	// Uptime is the percentage of time the agent was available.
	Uptime float64 `json:"uptime"`
	// SuccessRate is the percentage of tasks completed successfully.
	SuccessRate float64 `json:"success_rate"`
	// AverageResponseTime is the mean response time in milliseconds.
	AverageResponseTime float64 `json:"average_response_time"`
	// TasksCompleted is the number of tasks completed in the period.
	TasksCompleted int `json:"tasks_completed"`
	// TasksFailed is the number of tasks that failed in the period.
	TasksFailed int `json:"tasks_failed"`
	// TotalEarnings is the earnings in the period.
	TotalEarnings float64 `json:"total_earnings"`
	// PeriodStart is the start of the measurement period.
	PeriodStart time.Time `json:"period_start"`
	// PeriodEnd is the end of the measurement period.
	PeriodEnd time.Time `json:"period_end"`
}

// PaginationParams defines parameters for paginated requests.
type PaginationParams struct {
	// Page is the page number (1-indexed).
	Page int `json:"page"`
	// Limit is the number of items per page.
	Limit int `json:"limit"`
	// SortBy is the field to sort by.
	SortBy string `json:"sort_by"`
	// SortOrder is the sort direction ("asc" or "desc").
	SortOrder string `json:"sort_order"`
}

// PaginationMeta contains pagination metadata in responses.
type PaginationMeta struct {
	// CurrentPage is the current page number.
	CurrentPage int `json:"current_page"`
	// TotalPages is the total number of pages.
	TotalPages int `json:"total_pages"`
	// TotalItems is the total number of items.
	TotalItems int `json:"total_items"`
	// ItemsPerPage is the number of items per page.
	ItemsPerPage int `json:"items_per_page"`
	// HasNext indicates if there is a next page.
	HasNext bool `json:"has_next"`
	// HasPrev indicates if there is a previous page.
	HasPrev bool `json:"has_prev"`
}

// PaginatedResponse wraps a paginated response.
type PaginatedResponse struct {
	// Meta contains pagination metadata.
	Meta PaginationMeta `json:"meta"`
	// Data contains the paginated items.
	Data interface{} `json:"data"`
}
