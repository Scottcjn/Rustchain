// Package rustchain provides a Go client for the RustChain API.
//
// The client covers all public and authenticated endpoints exposed by
// RustChain v2.2.1 nodes, including health checks, epoch/enrollment,
// wallet operations, attestation, beacon protocol, governance, and
// withdrawal management.
package rustchain

import (
	"bytes"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"time"
)

// Client is a RustChain API client.
type Client struct {
	BaseURL    string
	AdminKey   string
	HTTPClient *http.Client
}

// Option configures a Client.
type Option func(*Client)

// WithAdminKey sets the admin/API key used for privileged endpoints.
func WithAdminKey(key string) Option {
	return func(c *Client) { c.AdminKey = key }
}

// WithHTTPClient overrides the default HTTP client.
func WithHTTPClient(hc *http.Client) Option {
	return func(c *Client) { c.HTTPClient = hc }
}

// WithInsecureTLS disables TLS certificate verification (useful for
// self-signed certificates on RustChain nodes).
func WithInsecureTLS() Option {
	return func(c *Client) {
		c.HTTPClient.Transport = &http.Transport{
			TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
		}
	}
}

// NewClient creates a new RustChain API client.
func NewClient(baseURL string, opts ...Option) *Client {
	c := &Client{
		BaseURL: baseURL,
		HTTPClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
	for _, opt := range opts {
		opt(c)
	}
	return c
}

// ---- internal helpers ----

func (c *Client) doGet(path string, query url.Values, out interface{}) error {
	u := c.BaseURL + path
	if len(query) > 0 {
		u += "?" + query.Encode()
	}
	req, err := http.NewRequest(http.MethodGet, u, nil)
	if err != nil {
		return err
	}
	return c.do(req, out)
}

func (c *Client) doGetAdmin(path string, query url.Values, out interface{}) error {
	u := c.BaseURL + path
	if len(query) > 0 {
		u += "?" + query.Encode()
	}
	req, err := http.NewRequest(http.MethodGet, u, nil)
	if err != nil {
		return err
	}
	req.Header.Set("X-API-Key", c.AdminKey)
	return c.do(req, out)
}

func (c *Client) doGetAdminKey(path string, query url.Values, out interface{}) error {
	u := c.BaseURL + path
	if len(query) > 0 {
		u += "?" + query.Encode()
	}
	req, err := http.NewRequest(http.MethodGet, u, nil)
	if err != nil {
		return err
	}
	req.Header.Set("X-Admin-Key", c.AdminKey)
	return c.do(req, out)
}

func (c *Client) doPost(path string, body interface{}, out interface{}) error {
	data, err := json.Marshal(body)
	if err != nil {
		return err
	}
	req, err := http.NewRequest(http.MethodPost, c.BaseURL+path, bytes.NewReader(data))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	return c.do(req, out)
}

func (c *Client) doPostAdmin(path string, body interface{}, out interface{}) error {
	data, err := json.Marshal(body)
	if err != nil {
		return err
	}
	req, err := http.NewRequest(http.MethodPost, c.BaseURL+path, bytes.NewReader(data))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", c.AdminKey)
	return c.do(req, out)
}

func (c *Client) doPostAdminKey(path string, body interface{}, out interface{}) error {
	data, err := json.Marshal(body)
	if err != nil {
		return err
	}
	req, err := http.NewRequest(http.MethodPost, c.BaseURL+path, bytes.NewReader(data))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Admin-Key", c.AdminKey)
	return c.do(req, out)
}

func (c *Client) do(req *http.Request, out interface{}) error {
	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("reading response: %w", err)
	}

	if resp.StatusCode >= 400 {
		var apiErr ErrorResponse
		if json.Unmarshal(body, &apiErr) == nil && apiErr.Error != "" {
			return fmt.Errorf("api error %d: %s – %s", resp.StatusCode, apiErr.Error, apiErr.Message)
		}
		return fmt.Errorf("api error %d: %s", resp.StatusCode, string(body))
	}

	if out != nil {
		return json.Unmarshal(body, out)
	}
	return nil
}

// ---- Health & Status ----

// Health returns the node health status.
func (c *Client) Health() (*HealthResponse, error) {
	var out HealthResponse
	return &out, c.doGet("/health", nil, &out)
}

// Ready returns the node readiness status.
func (c *Client) Ready() (*ReadinessResponse, error) {
	var out ReadinessResponse
	return &out, c.doGet("/ready", nil, &out)
}

// Stats returns system-wide statistics.
func (c *Client) Stats() (*StatsResponse, error) {
	var out StatsResponse
	return &out, c.doGet("/api/stats", nil, &out)
}

// ---- Epochs & Enrollment ----

// Epoch returns the current epoch information.
func (c *Client) Epoch() (*EpochResponse, error) {
	var out EpochResponse
	return &out, c.doGet("/epoch", nil, &out)
}

// Enroll enrolls a miner in the current epoch.
func (c *Client) Enroll(req *EnrollRequest) (*EnrollResponse, error) {
	var out EnrollResponse
	return &out, c.doPost("/epoch/enroll", req, &out)
}

// LotteryEligibility checks round-robin eligibility for a miner.
func (c *Client) LotteryEligibility(minerID string) (*EligibilityResponse, error) {
	var out EligibilityResponse
	q := url.Values{"miner_id": {minerID}}
	return &out, c.doGet("/lottery/eligibility", q, &out)
}

// EpochRewards returns the reward distribution for a specific epoch.
func (c *Client) EpochRewards(epoch int) (*EpochRewardsResponse, error) {
	var out EpochRewardsResponse
	return &out, c.doGet(fmt.Sprintf("/rewards/epoch/%d", epoch), nil, &out)
}

// ---- Wallet & Balance ----

// Balance returns the balance for a miner public key.
func (c *Client) Balance(minerPK string) (*BalanceResponse, error) {
	var out BalanceResponse
	return &out, c.doGet("/balance/"+url.PathEscape(minerPK), nil, &out)
}

// WalletBalance returns the balance for a miner by ID.
func (c *Client) WalletBalance(minerID string) (*WalletBalanceResponse, error) {
	var out WalletBalanceResponse
	q := url.Values{"miner_id": {minerID}}
	return &out, c.doGet("/wallet/balance", q, &out)
}

// WalletHistory returns the public transfer history for a wallet.
func (c *Client) WalletHistory(minerID string, limit int) ([]TransferHistoryEntry, error) {
	var out []TransferHistoryEntry
	q := url.Values{
		"miner_id": {minerID},
		"limit":    {strconv.Itoa(limit)},
	}
	return out, c.doGet("/wallet/history", q, &out)
}

// SignedTransfer submits a signed RTC transfer.
func (c *Client) SignedTransfer(req *SignedTransferRequest) (*SignedTransferResponse, error) {
	var out SignedTransferResponse
	return &out, c.doPost("/wallet/transfer/signed", req, &out)
}

// ResolveWallet resolves a beacon address to its RTC wallet.
func (c *Client) ResolveWallet(address string) (*ResolveWalletResponse, error) {
	var out ResolveWalletResponse
	q := url.Values{"address": {address}}
	return &out, c.doGet("/wallet/resolve", q, &out)
}

// ---- Block Headers ----

// ChainTip returns the current chain tip.
func (c *Client) ChainTip() (*ChainTipResponse, error) {
	var out ChainTipResponse
	return &out, c.doGet("/headers/tip", nil, &out)
}

// ---- Attestation ----

// AttestChallenge requests a hardware attestation challenge nonce.
func (c *Client) AttestChallenge() (*AttestChallengeResponse, error) {
	var out AttestChallengeResponse
	return &out, c.doPost("/attest/challenge", nil, &out)
}

// AttestSubmit submits a hardware attestation.
func (c *Client) AttestSubmit(req *AttestSubmitRequest) (*AttestSubmitResponse, error) {
	var out AttestSubmitResponse
	return &out, c.doPost("/attest/submit", req, &out)
}

// ---- Miners & Network ----

// Miners returns the list of active miners.
func (c *Client) Miners() ([]Miner, error) {
	var out []Miner
	return out, c.doGet("/api/miners", nil, &out)
}

// Nodes returns the list of registered network nodes.
func (c *Client) Nodes() (*NodesResponse, error) {
	var out NodesResponse
	return &out, c.doGet("/api/nodes", nil, &out)
}

// MinerBadge returns a Shields.io badge for a miner.
func (c *Client) MinerBadge(minerID string) (*BadgeResponse, error) {
	var out BadgeResponse
	return &out, c.doGet("/api/badge/"+url.PathEscape(minerID), nil, &out)
}

// MinerDashboard returns aggregated dashboard data for a miner.
func (c *Client) MinerDashboard(minerID string) (*MinerDashboardResponse, error) {
	var out MinerDashboardResponse
	return &out, c.doGet("/api/miner_dashboard/"+url.PathEscape(minerID), nil, &out)
}

// BountyMultiplier returns the current bounty decay multiplier.
func (c *Client) BountyMultiplier() (*BountyMultiplierResponse, error) {
	var out BountyMultiplierResponse
	return &out, c.doGet("/api/bounty-multiplier", nil, &out)
}

// FeePool returns the fee pool statistics (RIP-301).
func (c *Client) FeePool() (*FeePoolResponse, error) {
	var out FeePoolResponse
	return &out, c.doGet("/api/fee_pool", nil, &out)
}

// ---- Beacon Protocol ----

// BeaconSubmit submits a beacon envelope for anchoring.
func (c *Client) BeaconSubmit(req *BeaconSubmitRequest) (*BeaconSubmitResponse, error) {
	var out BeaconSubmitResponse
	return &out, c.doPost("/beacon/submit", req, &out)
}

// BeaconDigest returns the current beacon digest.
func (c *Client) BeaconDigest() (*BeaconDigestResponse, error) {
	var out BeaconDigestResponse
	return &out, c.doGet("/beacon/digest", nil, &out)
}

// BeaconEnvelopes lists recent beacon envelopes with pagination.
func (c *Client) BeaconEnvelopes(limit, offset int) (*BeaconEnvelopesResponse, error) {
	var out BeaconEnvelopesResponse
	q := url.Values{
		"limit":  {strconv.Itoa(limit)},
		"offset": {strconv.Itoa(offset)},
	}
	return &out, c.doGet("/beacon/envelopes", q, &out)
}

// ---- Governance ----

// GovernanceProposals lists all governance proposals.
func (c *Client) GovernanceProposals() (*ProposalsResponse, error) {
	var out ProposalsResponse
	return &out, c.doGet("/governance/proposals", nil, &out)
}

// GovernanceProposal returns the detail of a governance proposal.
func (c *Client) GovernanceProposal(id int) (*ProposalDetailResponse, error) {
	var out ProposalDetailResponse
	return &out, c.doGet(fmt.Sprintf("/governance/proposal/%d", id), nil, &out)
}

// GovernancePropose creates a new governance proposal.
func (c *Client) GovernancePropose(req *ProposeRequest) (*ProposalDetailResponse, error) {
	var out ProposalDetailResponse
	return &out, c.doPost("/governance/propose", req, &out)
}

// GovernanceVote casts a vote on an active proposal.
func (c *Client) GovernanceVote(req *VoteRequest) (*VoteResponse, error) {
	var out VoteResponse
	return &out, c.doPost("/governance/vote", req, &out)
}

// ---- Withdrawals ----

// WithdrawRequest submits a withdrawal request.
func (c *Client) WithdrawRequest(req *WithdrawalRequest) (*WithdrawalResponse, error) {
	var out WithdrawalResponse
	return &out, c.doPost("/withdraw/request", req, &out)
}

// WithdrawStatus returns the status of a withdrawal.
func (c *Client) WithdrawStatus(withdrawalID string) (*WithdrawalStatus, error) {
	var out WithdrawalStatus
	return &out, c.doGet("/withdraw/status/"+url.PathEscape(withdrawalID), nil, &out)
}

// ---- P2P ----

// P2PStats returns P2P network statistics.
func (c *Client) P2PStats() (*P2PStatsResponse, error) {
	var out P2PStatsResponse
	return &out, c.doGet("/p2p/stats", nil, &out)
}
