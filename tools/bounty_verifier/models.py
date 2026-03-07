"""
Data models for bounty verification.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class VerificationStatus(Enum):
    """Status of a verification check."""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class ClaimStatus(Enum):
    """Status of a bounty claim."""
    NEW = "new"
    VERIFIED = "verified"
    REJECTED = "rejected"
    PAID = "paid"
    DUPLICATE = "duplicate"


@dataclass
class ClaimComment:
    """Represents a bounty claim comment from GitHub."""
    id: int
    user_login: str
    user_id: int
    body: str
    created_at: datetime
    updated_at: datetime
    issue_number: int
    html_url: str
    
    # Parsed claim data
    wallet_address: Optional[str] = None
    follow_proof_url: Optional[str] = None
    star_proof_url: Optional[str] = None
    additional_urls: List[str] = field(default_factory=list)
    
    @classmethod
    def from_github_api(cls, data: Dict[str, Any], issue_number: int) -> "ClaimComment":
        """Create ClaimComment from GitHub API response."""
        return cls(
            id=data["id"],
            user_login=data["user"]["login"],
            user_id=data["user"]["id"],
            body=data["body"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            issue_number=issue_number,
            html_url=data["html_url"],
        )


@dataclass
class VerificationCriteria:
    """Criteria for bounty verification."""
    require_follow: bool = True
    require_stars: bool = True
    min_star_count: int = 3
    require_wallet: bool = True
    require_url_liveness: bool = False
    check_duplicates: bool = True
    wallet_balance_min: float = 0.0


@dataclass
class VerificationCheck:
    """Result of a single verification check."""
    name: str
    status: VerificationStatus
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class VerificationResult:
    """Complete verification result for a bounty claim."""
    claim: ClaimComment
    overall_status: VerificationStatus
    checks: List[VerificationCheck] = field(default_factory=list)
    payout_amount: float = 0.0
    payout_coefficient: float = 1.0
    notes: List[str] = field(default_factory=list)
    verified_at: datetime = field(default_factory=datetime.utcnow)
    
    def add_check(self, check: VerificationCheck) -> None:
        """Add a verification check result."""
        self.checks.append(check)
        if check.status == VerificationStatus.FAILED:
            self.overall_status = VerificationStatus.FAILED
        elif check.status == VerificationStatus.ERROR and self.overall_status != VerificationStatus.FAILED:
            self.overall_status = VerificationStatus.ERROR
        elif check.status == VerificationStatus.PASSED and self.overall_status == VerificationStatus.PENDING:
            # If this is the first passing check and we're still pending, update to passed
            # (will be overridden if any subsequent check fails)
            all_passed = all(c.status == VerificationStatus.PASSED for c in self.checks)
            if all_passed:
                self.overall_status = VerificationStatus.PASSED
    
    def to_comment_body(self) -> str:
        """Generate a structured comment body for GitHub."""
        lines = [
            "## 🤖 Bounty Verification Report",
            "",
            f"**Claim by:** @{self.claim.user_login}",
            f"**Wallet:** `{self.claim.wallet_address or 'N/A'}`",
            f"**Status:** `{self.overall_status.value.upper()}`",
            "",
            "### Verification Checks",
            "",
        ]
        
        status_icons = {
            VerificationStatus.PASSED: "✅",
            VerificationStatus.FAILED: "❌",
            VerificationStatus.SKIPPED: "⏭️",
            VerificationStatus.ERROR: "⚠️",
            VerificationStatus.PENDING: "⏳",
        }
        
        for check in self.checks:
            icon = status_icons.get(check.status, "❓")
            lines.append(f"- {icon} **{check.name}**: {check.message}")
        
        if self.payout_amount > 0:
            lines.extend([
                "",
                "### Payout Details",
                "",
                f"- **Base Amount:** Configured per bounty",
                f"- **Coefficient:** {self.payout_coefficient:.2f}",
                f"- **Final Amount:** {self.payout_amount:.2f} WRTC",
            ])
        
        if self.notes:
            lines.extend([
                "",
                "### Notes",
                "",
            ])
            for note in self.notes:
                lines.append(f"- {note}")
        
        lines.extend([
            "",
            "---",
            f"*Verified at: {self.verified_at.isoformat()}*",
            "*Bounty Verifier v1.0.0*",
        ])

        return "\n".join(lines)
