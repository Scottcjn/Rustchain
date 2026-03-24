package agenteco

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

const (
	// DefaultBaseURL is the default API endpoint.
	DefaultBaseURL = "https://rustchain.org/api/agent-economy"
	// DefaultTimeout is the default request timeout.
	DefaultTimeout = 30 * time.Second
	// DefaultMaxRetries is the default number of retry attempts.
	DefaultMaxRetries = 3
	// DefaultRetryWait is the initial wait time between retries.
	DefaultRetryWait = 100 * time.Millisecond
	// DefaultMaxRetryWait is the maximum wait time between retries.
	DefaultMaxRetryWait = 10 * time.Second
	// Version is the SDK version.
	Version = "1.0.0"
	// UserAgent is the HTTP user agent string.
	UserAgent = "rustchain-agenteco-sdk/" + Version
)

// ClientConfig holds configuration for the SDK client.
type ClientConfig struct {
	// BaseURL is the API base URL.
	BaseURL string
	// APIKey is the optional API key for authentication.
	APIKey string
	// Timeout is the request timeout.
	Timeout time.Duration
	// MaxRetries is the maximum number of retry attempts.
	MaxRetries int
	// RetryWait is the initial retry wait duration.
	RetryWait time.Duration
	// MaxRetryWait is the maximum retry wait duration.
	MaxRetryWait time.Duration
	// HTTPClient is an optional custom HTTP client.
	HTTPClient *http.Client
	// SkipTLSVerify disables TLS verification (for development only).
	SkipTLSVerify bool
	// Debug enables debug logging.
	Debug bool
}

// Client is the main client for interacting with the Agent Economy API.
type Client struct {
	config       ClientConfig
	baseURL      *url.URL
	httpClient   *http.Client
	retryWait    time.Duration
	maxRetryWait time.Duration
	maxRetries   int
}

// NewClient creates a new Agent Economy API client.
func NewClient(config *ClientConfig) (*Client, error) {
	if config == nil {
		config = &ClientConfig{}
	}

	// Apply defaults
	baseURL := config.BaseURL
	if baseURL == "" {
		baseURL = DefaultBaseURL
	}

	timeout := config.Timeout
	if timeout == 0 {
		timeout = DefaultTimeout
	}

	maxRetries := config.MaxRetries
	if maxRetries == 0 {
		maxRetries = DefaultMaxRetries
	}

	retryWait := config.RetryWait
	if retryWait == 0 {
		retryWait = DefaultRetryWait
	}

	maxRetryWait := config.MaxRetryWait
	if maxRetryWait == 0 {
		maxRetryWait = DefaultMaxRetryWait
	}

	// Parse base URL
	parsedURL, err := url.Parse(baseURL)
	if err != nil {
		return nil, &ClientError{Message: "invalid base URL", Cause: err}
	}

	// Create HTTP client
	httpClient := config.HTTPClient
	if httpClient == nil {
		transport := &http.Transport{
			MaxIdleConns:        100,
			MaxIdleConnsPerHost: 10,
			IdleConnTimeout:     90 * time.Second,
			TLSHandshakeTimeout: 10 * time.Second,
		}

		if config.SkipTLSVerify {
			transport.TLSClientConfig = &tls.Config{InsecureSkipVerify: true}
		}

		httpClient = &http.Client{
			Timeout:   timeout,
			Transport: transport,
		}
	}

	return &Client{
		config:       *config,
		baseURL:      parsedURL,
		httpClient:   httpClient,
		retryWait:    retryWait,
		maxRetryWait: maxRetryWait,
		maxRetries:   maxRetries,
	}, nil
}

// NewClientWithDefaults creates a client with default configuration.
func NewClientWithDefaults() (*Client, error) {
	return NewClient(&ClientConfig{})
}

// NewClientWithKey creates a client with API key authentication.
func NewClientWithKey(apiKey string) (*Client, error) {
	return NewClient(&ClientConfig{APIKey: apiKey})
}

// Close closes the client and releases resources.
func (c *Client) Close() {
	c.httpClient.CloseIdleConnections()
}

// doRequest performs an HTTP request with retries and error handling.
func (c *Client) doRequest(ctx context.Context, method, path string, body interface{}, result interface{}) error {
	var lastErr error

	for attempt := 0; attempt <= c.maxRetries; attempt++ {
		if attempt > 0 {
			select {
			case <-ctx.Done():
				return &TimeoutError{
					Message:  "request cancelled",
					Duration: c.retryWait,
					Cause:    ctx.Err(),
				}
			case <-time.After(c.calculateBackoff(attempt)):
			}
		}

		err := c.doRequestOnce(ctx, method, path, body, result)
		if err == nil {
			return nil
		}

		lastErr = err

		// Don't retry on non-retryable errors
		if !IsRetryable(err) {
			return err
		}

		// Check for retry-after header
		if retryAfter := GetRetryAfter(err); retryAfter > 0 {
			select {
			case <-ctx.Done():
				return &TimeoutError{
					Message:  "request cancelled during retry-after wait",
					Duration: retryAfter,
					Cause:    ctx.Err(),
				}
			case <-time.After(retryAfter):
			}
			continue
		}
	}

	return &ClientError{Message: "all retry attempts failed", Cause: lastErr}
}

// calculateBackoff calculates exponential backoff with jitter.
func (c *Client) calculateBackoff(attempt int) time.Duration {
	if attempt == 0 {
		return 0
	}

	// Exponential backoff: base * 2^(attempt-1)
	multiplier := 1 << uint(attempt-1)
	backoff := time.Duration(int64(c.retryWait) * int64(multiplier))

	// Cap at max retry wait
	if backoff > c.maxRetryWait {
		backoff = c.maxRetryWait
	}

	// Add jitter (±10%)
	jitter := time.Duration(int64(backoff) / 10)
	if jitter > 0 {
		backoff = backoff - jitter + time.Duration(int64(jitter)*int64(time.Now().UnixNano()%1000)/1000)
	}

	return time.Duration(backoff)
}

// doRequestOnce performs a single HTTP request attempt.
func (c *Client) doRequestOnce(ctx context.Context, method, path string, body interface{}, result interface{}) error {
	// Build URL
	reqURL, err := c.baseURL.Parse(path)
	if err != nil {
		return &ClientError{Message: "failed to parse URL", Cause: err}
	}

	// Create request body
	var reqBody io.Reader
	if body != nil {
		jsonData, err := json.Marshal(body)
		if err != nil {
			return &ClientError{Message: "failed to marshal request body", Cause: err}
		}
		reqBody = bytes.NewReader(jsonData)
	}

	// Create HTTP request
	req, err := http.NewRequestWithContext(ctx, method, reqURL.String(), reqBody)
	if err != nil {
		return &ClientError{Message: "failed to create request", Cause: err}
	}

	// Set headers
	req.Header.Set("User-Agent", UserAgent)
	req.Header.Set("Accept", "application/json")
	if reqBody != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if c.config.APIKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.config.APIKey)
	}

	// Execute request
	resp, err := c.httpClient.Do(req)
	if err != nil {
		if errors.Is(ctx.Err(), context.DeadlineExceeded) {
			return &TimeoutError{
				Message:  "request timeout",
				Duration: c.config.Timeout,
				Cause:    err,
			}
		}
		return &NetworkError{
			Message: "request failed",
			URL:     reqURL.String(),
			Cause:   err,
		}
	}
	defer resp.Body.Close()

	// Read response body
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return &ClientError{Message: "failed to read response body", Cause: err}
	}

	// Check for error status
	if resp.StatusCode >= 400 {
		return c.parseErrorResponse(resp.StatusCode, respBody)
	}

	// Parse successful response
	if result != nil {
		if err := json.Unmarshal(respBody, result); err != nil {
			return &ClientError{Message: "failed to parse response JSON", Cause: err}
		}
	}

	return nil
}

// parseErrorResponse parses an error response from the server.
func (c *Client) parseErrorResponse(statusCode int, body []byte) error {
	// Try to parse as API error
	var apiResp struct {
		Error struct {
			Code    string                 `json:"code"`
			Message string                 `json:"message"`
			Details map[string]interface{} `json:"details,omitempty"`
		} `json:"error"`
	}

	if err := json.Unmarshal(body, &apiResp); err == nil && apiResp.Error.Code != "" {
		apiErr := NewAPIError(
			statusCode,
			apiResp.Error.Code,
			apiResp.Error.Message,
			apiResp.Error.Details,
		)
		apiErr.Raw = apiResp
		apiErr.RetryAfter = c.parseRetryAfter(body)
		return apiErr
	}

	// Fallback to generic error
	return NewAPIError(statusCode, "", http.StatusText(statusCode), nil)
}

// parseRetryAfter extracts retry-after from error response.
func (c *Client) parseRetryAfter(body []byte) time.Duration {
	var resp struct {
		Error struct {
			RetryAfter int `json:"retry_after"`
		} `json:"error"`
	}
	if err := json.Unmarshal(body, &resp); err == nil && resp.Error.RetryAfter > 0 {
		return time.Duration(resp.Error.RetryAfter) * time.Second
	}
	return 0
}

// buildQueryParams builds a query string from parameters.
func buildQueryParams(params map[string]string) string {
	if len(params) == 0 {
		return ""
	}

	values := url.Values{}
	for k, v := range params {
		if v != "" {
			values.Set(k, v)
		}
	}

	query := values.Encode()
	if query != "" {
		return "?" + query
	}
	return ""
}

// Pagination helpers

// ListOptions holds common list query parameters.
type ListOptions struct {
	Page      int
	Limit     int
	SortBy    string
	SortOrder string
	Filter    map[string]string
}

// applyListOptions applies list options to query parameters.
func applyListOptions(opts *ListOptions) map[string]string {
	params := make(map[string]string)

	if opts == nil {
		return params
	}

	if opts.Page > 0 {
		params["page"] = strconv.Itoa(opts.Page)
	}
	if opts.Limit > 0 {
		params["limit"] = strconv.Itoa(opts.Limit)
	}
	if opts.SortBy != "" {
		params["sort_by"] = opts.SortBy
	}
	if opts.SortOrder != "" {
		params["sort_order"] = opts.SortOrder
	}

	for k, v := range opts.Filter {
		if v != "" {
			params[k] = v
		}
	}

	return params
}

// parsePaginationMeta extracts pagination metadata from response.
func parsePaginationMeta(headers http.Header) *PaginationMeta {
	meta := &PaginationMeta{}

	if page := headers.Get("X-Page"); page != "" {
		meta.CurrentPage, _ = strconv.Atoi(page)
	}
	if totalPages := headers.Get("X-Total-Pages"); totalPages != "" {
		meta.TotalPages, _ = strconv.Atoi(totalPages)
	}
	if totalItems := headers.Get("X-Total-Items"); totalItems != "" {
		meta.TotalItems, _ = strconv.Atoi(totalItems)
	}
	if perPage := headers.Get("X-Per-Page"); perPage != "" {
		meta.ItemsPerPage, _ = strconv.Atoi(perPage)
	}
	if hasNext := headers.Get("X-Has-Next"); hasNext != "" {
		meta.HasNext = strings.ToLower(hasNext) == "true"
	}
	if hasPrev := headers.Get("X-Has-Prev"); hasPrev != "" {
		meta.HasPrev = strings.ToLower(hasPrev) == "true"
	}

	return meta
}

// Iterator provides pagination iteration over list results.
type Iterator struct {
	client   *Client
	path     string
	opts     *ListOptions
	items    []interface{}
	current  int
	done     bool
	lastErr  error
	itemType reflectType
}

type reflectType interface{}

// NewIterator creates a new iterator for paginated results.
func NewIterator(client *Client, path string, opts *ListOptions) *Iterator {
	return &Iterator{
		client: client,
		path:   path,
		opts:   opts,
	}
}

// Next advances to the next item and returns true if available.
func (it *Iterator) Next(ctx context.Context) bool {
	if it.done {
		return false
	}

	if it.current < len(it.items) {
		it.current++
		return it.current < len(it.items)
	}

	// Load next page
	if it.opts == nil {
		it.opts = &ListOptions{}
	}
	it.opts.Page++

	var result struct {
		Meta PaginationMeta `json:"meta"`
		Data []interface{}  `json:"data"`
	}

	params := applyListOptions(it.opts)
	path := it.path + buildQueryParams(params)

	if err := it.client.doRequest(ctx, http.MethodGet, path, nil, &result); err != nil {
		it.lastErr = err
		it.done = true
		return false
	}

	it.items = result.Data
	it.current = 0

	if len(it.items) == 0 || !result.Meta.HasNext {
		it.done = true
	}

	return len(it.items) > 0
}

// Item returns the current item.
func (it *Iterator) Item() interface{} {
	if it.current < 0 || it.current >= len(it.items) {
		return nil
	}
	return it.items[it.current]
}

// Err returns the last error encountered.
func (it *Iterator) Err() error {
	return it.lastErr
}

// ForEach iterates over all items, calling fn for each.
func (c *Client) ForEach(ctx context.Context, path string, opts *ListOptions, fn func(interface{}) error) error {
	it := NewIterator(c, path, opts)

	for it.Next(ctx) {
		if err := fn(it.Item()); err != nil {
			return err
		}
	}

	return it.Err()
}
