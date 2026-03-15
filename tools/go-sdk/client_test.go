package rustchain

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

// helper: create a test server that returns the given JSON body for a path.
func newTestServer(t *testing.T, handlers map[string]interface{}) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	for path, resp := range handlers {
		body, err := json.Marshal(resp)
		if err != nil {
			t.Fatal(err)
		}
		mux.HandleFunc(path, func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			w.Write(body)
		})
	}
	return httptest.NewServer(mux)
}

func TestHealth(t *testing.T) {
	srv := newTestServer(t, map[string]interface{}{
		"/health": HealthResponse{
			OK:            true,
			Version:       "2.2.1-security-hardened",
			UptimeSeconds: 86400,
			DBRW:          true,
		},
	})
	defer srv.Close()

	c := NewClient(srv.URL)
	resp, err := c.Health()
	if err != nil {
		t.Fatal(err)
	}
	if !resp.OK {
		t.Error("expected ok=true")
	}
	if resp.Version != "2.2.1-security-hardened" {
		t.Errorf("unexpected version %q", resp.Version)
	}
	if resp.UptimeSeconds != 86400 {
		t.Errorf("unexpected uptime %f", resp.UptimeSeconds)
	}
}

func TestReady(t *testing.T) {
	srv := newTestServer(t, map[string]interface{}{
		"/ready": ReadinessResponse{Ready: true, Version: "2.2.1"},
	})
	defer srv.Close()

	c := NewClient(srv.URL)
	resp, err := c.Ready()
	if err != nil {
		t.Fatal(err)
	}
	if !resp.Ready {
		t.Error("expected ready=true")
	}
}

func TestStats(t *testing.T) {
	srv := newTestServer(t, map[string]interface{}{
		"/api/stats": StatsResponse{
			Version:     "2.2.1",
			ChainID:     "rustchain-mainnet-candidate",
			Epoch:       42,
			TotalMiners: 150,
		},
	})
	defer srv.Close()

	c := NewClient(srv.URL)
	resp, err := c.Stats()
	if err != nil {
		t.Fatal(err)
	}
	if resp.Epoch != 42 {
		t.Errorf("expected epoch 42, got %d", resp.Epoch)
	}
	if resp.TotalMiners != 150 {
		t.Errorf("expected 150 miners, got %d", resp.TotalMiners)
	}
}

func TestEpoch(t *testing.T) {
	srv := newTestServer(t, map[string]interface{}{
		"/epoch": EpochResponse{
			Epoch:          42,
			Slot:           25200,
			EpochPot:       1.5,
			EnrolledMiners: 12,
			BlocksPerEpoch: 600,
			TotalSupplyRTC: 21000000,
		},
	})
	defer srv.Close()

	c := NewClient(srv.URL)
	resp, err := c.Epoch()
	if err != nil {
		t.Fatal(err)
	}
	if resp.Epoch != 42 {
		t.Errorf("expected epoch 42, got %d", resp.Epoch)
	}
	if resp.EnrolledMiners != 12 {
		t.Errorf("expected 12 enrolled miners, got %d", resp.EnrolledMiners)
	}
}

func TestWalletBalance(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/wallet/balance", func(w http.ResponseWriter, r *http.Request) {
		minerID := r.URL.Query().Get("miner_id")
		resp := WalletBalanceResponse{
			MinerID:   minerID,
			AmountI64: 42500000,
			AmountRTC: 42.5,
		}
		json.NewEncoder(w).Encode(resp)
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	c := NewClient(srv.URL)
	resp, err := c.WalletBalance("g4-powerbook-01")
	if err != nil {
		t.Fatal(err)
	}
	if resp.MinerID != "g4-powerbook-01" {
		t.Errorf("unexpected miner_id %q", resp.MinerID)
	}
	if resp.AmountRTC != 42.5 {
		t.Errorf("expected 42.5 RTC, got %f", resp.AmountRTC)
	}
}

func TestBalance(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/balance/RTCabc123", func(w http.ResponseWriter, r *http.Request) {
		resp := BalanceResponse{
			MinerPK:    "RTCabc123",
			BalanceRTC: 10.0,
			AmountI64:  10000000,
		}
		json.NewEncoder(w).Encode(resp)
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	c := NewClient(srv.URL)
	resp, err := c.Balance("RTCabc123")
	if err != nil {
		t.Fatal(err)
	}
	if resp.BalanceRTC != 10.0 {
		t.Errorf("expected 10.0 RTC, got %f", resp.BalanceRTC)
	}
}

func TestSignedTransfer(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/wallet/transfer/signed", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", 405)
			return
		}
		var req SignedTransferRequest
		json.NewDecoder(r.Body).Decode(&req)
		resp := SignedTransferResponse{
			OK:          true,
			Verified:    true,
			Phase:       "pending",
			PendingID:   42,
			TxHash:      "abc123def456",
			FromAddress: req.FromAddress,
			ToAddress:   req.ToAddress,
			AmountRTC:   req.AmountRTC,
		}
		json.NewEncoder(w).Encode(resp)
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	c := NewClient(srv.URL)
	resp, err := c.SignedTransfer(&SignedTransferRequest{
		FromAddress: "RTCsender",
		ToAddress:   "RTCreceiver",
		AmountRTC:   10.0,
		Nonce:       "12345",
		Signature:   "aabbccdd",
		PublicKey:   "eeff0011",
	})
	if err != nil {
		t.Fatal(err)
	}
	if !resp.OK {
		t.Error("expected ok=true")
	}
	if resp.PendingID != 42 {
		t.Errorf("expected pending_id 42, got %d", resp.PendingID)
	}
}

func TestChainTip(t *testing.T) {
	srv := newTestServer(t, map[string]interface{}{
		"/headers/tip": ChainTipResponse{
			Slot:            25200,
			Miner:           "g4-powerbook-01",
			TipAge:          120,
			SignaturePrefix: "a1b2c3d4",
		},
	})
	defer srv.Close()

	c := NewClient(srv.URL)
	resp, err := c.ChainTip()
	if err != nil {
		t.Fatal(err)
	}
	if resp.Slot != 25200 {
		t.Errorf("expected slot 25200, got %d", resp.Slot)
	}
	if resp.Miner != "g4-powerbook-01" {
		t.Errorf("unexpected miner %q", resp.Miner)
	}
}

func TestMiners(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/miners", func(w http.ResponseWriter, r *http.Request) {
		miners := []Miner{
			{
				MinerID:             "g4-powerbook-01",
				DeviceFamily:        "powerpc",
				DeviceArch:          "g4",
				EntropyScore:        0.85,
				AntiquityMultiplier: 2.0,
			},
		}
		json.NewEncoder(w).Encode(miners)
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	c := NewClient(srv.URL)
	miners, err := c.Miners()
	if err != nil {
		t.Fatal(err)
	}
	if len(miners) != 1 {
		t.Fatalf("expected 1 miner, got %d", len(miners))
	}
	if miners[0].MinerID != "g4-powerbook-01" {
		t.Errorf("unexpected miner id %q", miners[0].MinerID)
	}
}

func TestBeaconSubmit(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/beacon/submit", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(201)
		json.NewEncoder(w).Encode(BeaconSubmitResponse{OK: true, EnvelopeID: 42})
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	c := NewClient(srv.URL)
	resp, err := c.BeaconSubmit(&BeaconSubmitRequest{
		AgentID: "bcn_agent123",
		Kind:    "heartbeat",
		Nonce:   "nonce123",
		Sig:     "aabbccdd",
		Pubkey:  "eeff0011",
	})
	if err != nil {
		t.Fatal(err)
	}
	if resp.EnvelopeID != 42 {
		t.Errorf("expected envelope_id 42, got %d", resp.EnvelopeID)
	}
}

func TestBeaconDigest(t *testing.T) {
	srv := newTestServer(t, map[string]interface{}{
		"/beacon/digest": BeaconDigestResponse{
			OK:     true,
			Digest: "sha256abc",
			Count:  1000,
		},
	})
	defer srv.Close()

	c := NewClient(srv.URL)
	resp, err := c.BeaconDigest()
	if err != nil {
		t.Fatal(err)
	}
	if resp.Count != 1000 {
		t.Errorf("expected count 1000, got %d", resp.Count)
	}
}

func TestGovernanceProposals(t *testing.T) {
	srv := newTestServer(t, map[string]interface{}{
		"/governance/proposals": ProposalsResponse{
			OK:    true,
			Count: 1,
			Proposals: []GovernanceProposal{
				{ID: 1, Title: "Test Proposal", Status: "active"},
			},
		},
	})
	defer srv.Close()

	c := NewClient(srv.URL)
	resp, err := c.GovernanceProposals()
	if err != nil {
		t.Fatal(err)
	}
	if resp.Count != 1 {
		t.Errorf("expected 1 proposal, got %d", resp.Count)
	}
}

func TestMinerDashboard(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/miner_dashboard/g4-powerbook-01", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(MinerDashboardResponse{
			OK:         true,
			MinerID:    "g4-powerbook-01",
			BalanceRTC: 42.5,
		})
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	c := NewClient(srv.URL)
	resp, err := c.MinerDashboard("g4-powerbook-01")
	if err != nil {
		t.Fatal(err)
	}
	if resp.BalanceRTC != 42.5 {
		t.Errorf("expected 42.5 RTC, got %f", resp.BalanceRTC)
	}
}

func TestErrorResponse(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(500)
		json.NewEncoder(w).Encode(ErrorResponse{
			OK:      false,
			Error:   "internal_error",
			Message: "something went wrong",
		})
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	c := NewClient(srv.URL)
	_, err := c.Health()
	if err == nil {
		t.Fatal("expected error for 500 status")
	}
}

func TestWithAdminKey(t *testing.T) {
	c := NewClient("http://localhost", WithAdminKey("secret"))
	if c.AdminKey != "secret" {
		t.Errorf("expected admin key 'secret', got %q", c.AdminKey)
	}
}

func TestWithHTTPClient(t *testing.T) {
	custom := &http.Client{Timeout: 5}
	c := NewClient("http://localhost", WithHTTPClient(custom))
	if c.HTTPClient != custom {
		t.Error("expected custom HTTP client")
	}
}

func TestLotteryEligibility(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/lottery/eligibility", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(EligibilityResponse{
			Eligible: true,
			MinerID:  r.URL.Query().Get("miner_id"),
			Slot:     25200,
			Reason:   "round_robin_selected",
		})
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	c := NewClient(srv.URL)
	resp, err := c.LotteryEligibility("g4-powerbook-01")
	if err != nil {
		t.Fatal(err)
	}
	if !resp.Eligible {
		t.Error("expected eligible=true")
	}
}

func TestFeePool(t *testing.T) {
	srv := newTestServer(t, map[string]interface{}{
		"/api/fee_pool": FeePoolResponse{
			RIP:                   301,
			TotalFeesCollectedRTC: 1.5,
			TotalFeeEvents:        150,
		},
	})
	defer srv.Close()

	c := NewClient(srv.URL)
	resp, err := c.FeePool()
	if err != nil {
		t.Fatal(err)
	}
	if resp.RIP != 301 {
		t.Errorf("expected RIP 301, got %d", resp.RIP)
	}
}

func TestWithdrawStatus(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/withdraw/status/WD_123", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(WithdrawalStatus{
			WithdrawalID: "WD_123",
			Status:       "pending",
			Amount:       10.0,
			Fee:          0.01,
		})
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	c := NewClient(srv.URL)
	resp, err := c.WithdrawStatus("WD_123")
	if err != nil {
		t.Fatal(err)
	}
	if resp.Status != "pending" {
		t.Errorf("expected pending, got %q", resp.Status)
	}
}

func TestResolveWallet(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/wallet/resolve", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(ResolveWalletResponse{
			OK:       true,
			BeaconID: r.URL.Query().Get("address"),
			RTCAddr:  "RTCabc",
			Status:   "active",
		})
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	c := NewClient(srv.URL)
	resp, err := c.ResolveWallet("bcn_agent123")
	if err != nil {
		t.Fatal(err)
	}
	if resp.BeaconID != "bcn_agent123" {
		t.Errorf("unexpected beacon id %q", resp.BeaconID)
	}
}

func TestBountyMultiplier(t *testing.T) {
	srv := newTestServer(t, map[string]interface{}{
		"/api/bounty-multiplier": BountyMultiplierResponse{
			OK:                true,
			DecayModel:        "half-life",
			CurrentMultiplier: 0.87,
		},
	})
	defer srv.Close()

	c := NewClient(srv.URL)
	resp, err := c.BountyMultiplier()
	if err != nil {
		t.Fatal(err)
	}
	if resp.CurrentMultiplier != 0.87 {
		t.Errorf("expected 0.87, got %f", resp.CurrentMultiplier)
	}
}
