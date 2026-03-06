package agent

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

// Client represents a RustChain Agent Economy API client
type Client struct {
	BaseURL string
	Client  *http.Client
}

// NewClient creates a new RustChain Agent Economy client
func NewClient(baseURL string) *Client {
	return &Client{
		BaseURL: baseURL,
		Client: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// MarketStats represents marketplace statistics
type MarketStats struct {
	TotalJobs       int            `json:"total_jobs"`
	OpenJobs        int            `json:"open_jobs"`
	CompletedJobs   int            `json:"completed_jobs"`
	TotalRTCLocked  float64        `json:"total_rtc_locked"`
	AverageReward   float64        `json:"average_reward"`
	TopCategories   []CategoryCount `json:"top_categories"`
}

// CategoryCount represents category statistics
type CategoryCount struct {
	Category string `json:"category"`
	Count    int    `json:"count"`
}

// Job represents a job in the marketplace
type Job struct {
	ID            string   `json:"id"`
	PosterWallet  string   `json:"poster_wallet"`
	Title         string   `json:"title"`
	Description   string   `json:"description"`
	Category      string   `json:"category"`
	RewardRTC     float64  `json:"reward_rtc"`
	Tags          []string `json:"tags"`
	Status        string   `json:"status"`
	CreatedAt     string   `json:"created_at"`
}

// Reputation represents an agent's reputation
type Reputation struct {
	Wallet         string  `json:"wallet"`
	TrustScore     int     `json:"trust_score"`
	TrustLevel     string  `json:"trust_level"`
	AvgRating      float64 `json:"avg_rating"`
	TotalJobs      int     `json:"total_jobs"`
	CompletedJobs  int     `json:"completed_jobs"`
	DisputedJobs   int     `json:"disputed_jobs"`
}

// PostJobRequest represents a request to post a new job
type PostJobRequest struct {
	PosterWallet string   `json:"poster_wallet"`
	Title        string   `json:"title"`
	Description  string   `json:"description"`
	Category     string   `json:"category"`
	RewardRTC    float64  `json:"reward_rtc"`
	Tags         []string `json:"tags,omitempty"`
}

// ClaimJobRequest represents a request to claim a job
type ClaimJobRequest struct {
	WorkerWallet string `json:"worker_wallet"`
}

// DeliverJobRequest represents a request to deliver work
type DeliverJobRequest struct {
	WorkerWallet    string `json:"worker_wallet"`
	DeliverableURL  string `json:"deliverable_url"`
	ResultSummary   string `json:"result_summary"`
}

// AcceptDeliveryRequest represents a request to accept delivery
type AcceptDeliveryRequest struct {
	PosterWallet string `json:"poster_wallet"`
}

// GetMarketStats retrieves marketplace statistics
func (c *Client) GetMarketStats() (*MarketStats, error) {
	resp, err := c.Client.Get(c.BaseURL + "/agent/stats")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API returned status %d", resp.StatusCode)
	}

	var stats MarketStats
	if err := json.NewDecoder(resp.Body).Decode(&stats); err != nil {
		return nil, err
	}

	return &stats, nil
}

// GetJobs retrieves open jobs, optionally filtered by category
func (c *Client) GetJobs(category string, limit int) ([]Job, error) {
	url := fmt.Sprintf("%s/agent/jobs?limit=%d", c.BaseURL, limit)
	if category != "" {
		url += "&category=" + category
	}

	resp, err := c.Client.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API returned status %d", resp.StatusCode)
	}

	var jobs []Job
	if err := json.NewDecoder(resp.Body).Decode(&jobs); err != nil {
		return nil, err
	}

	return jobs, nil
}

// GetJob retrieves details of a specific job
func (c *Client) GetJob(jobID string) (*Job, error) {
	resp, err := c.Client.Get(fmt.Sprintf("%s/agent/jobs/%s", c.BaseURL, jobID))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API returned status %d", resp.StatusCode)
	}

	var job Job
	if err := json.NewDecoder(resp.Body).Decode(&job); err != nil {
		return nil, err
	}

	return &job, nil
}

// PostJob creates a new job in the marketplace
func (c *Client) PostJob(req PostJobRequest) (*Job, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}

	resp, err := c.Client.Post(c.BaseURL+"/agent/jobs", "application/json", bytes.NewBuffer(body))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return nil, fmt.Errorf("API returned status %d", resp.StatusCode)
	}

	var job Job
	if err := json.NewDecoder(resp.Body).Decode(&job); err != nil {
		return nil, err
	}

	return &job, nil
}

// ClaimJob claims a job
func (c *Client) ClaimJob(jobID string, req ClaimJobRequest) error {
	body, err := json.Marshal(req)
	if err != nil {
		return err
	}

	resp, err := c.Client.Post(c.BaseURL+"/agent/jobs/"+jobID+"/claim", "application/json", bytes.NewBuffer(body))
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("API returned status %d", resp.StatusCode)
	}

	return nil
}

// DeliverJob submits delivery for a job
func (c *Client) DeliverJob(jobID string, req DeliverJobRequest) error {
	body, err := json.Marshal(req)
	if err != nil {
		return err
	}

	resp, err := c.Client.Post(c.BaseURL+"/agent/jobs/"+jobID+"/deliver", "application/json", bytes.NewBuffer(body))
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("API returned status %d", resp.StatusCode)
	}

	return nil
}

// AcceptDelivery accepts delivered work and releases escrow
func (c *Client) AcceptDelivery(jobID string, req AcceptDeliveryRequest) error {
	body, err := json.Marshal(req)
	if err != nil {
		return err
	}

	resp, err := c.Client.Post(c.BaseURL+"/agent/jobs/"+jobID+"/accept", "application/json", bytes.NewBuffer(body))
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("API returned status %d", resp.StatusCode)
	}

	return nil
}

// GetReputation retrieves reputation for a wallet
func (c *Client) GetReputation(wallet string) (*Reputation, error) {
	resp, err := c.Client.Get(c.BaseURL + "/agent/reputation/" + wallet)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API returned status %d", resp.StatusCode)
	}

	var rep Reputation
	if err := json.NewDecoder(resp.Body).Decode(&rep); err != nil {
		return nil, err
	}

	return &rep, nil
}
