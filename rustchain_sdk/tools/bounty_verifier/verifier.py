"""
Main bounty verification logic.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import URLError
from urllib.request import Request, urlopen

from .config import Config
from .github_client import GitHubClient, RateLimitExceeded
from .models import (
    ClaimComment,
    ClaimStatus,
    VerificationCheck,
    VerificationResult,
    VerificationStatus,
)


logger = logging.getLogger(__name__)


class WalletCheckError(Exception):
    """Error during wallet balance check."""
    pass


class UrlLivenessError(Exception):
    """Error during URL liveness check."""
    pass


class BountyVerifier:
    """
    Bounty claim verification bot.
    
    Verifies:
    - GitHub follow status
    - Star count on owner's repos
    - Wallet existence/balance (optional)
    - URL liveness (optional)
    - Duplicate claim detection
    """
    
    # Regex patterns for parsing claim comments
    WALLET_PATTERNS = [
        r"(?<![A-Za-z0-9])(RTC[A-Za-z0-9]{38,40})(?![A-Za-z0-9])",  # RustChain address format
        r"(?i)wallet[:\s]+([A-Za-z0-9]{34,44})",
        r"(?i)address[:\s]+([A-Za-z0-9]{34,44})",
    ]
    
    URL_PATTERN = r"https?://[^\s<>\[\]\"']+"
    
    # Keywords indicating a claim
    CLAIM_KEYWORDS = [
        "claim",
        "claiming",
        "i claim",
        "submitting claim",
        "bounty claim",
        "claiming bounty",
    ]
    
    # Keywords indicating payment status
    PAID_KEYWORDS = ["PAID", "paid", "Payment sent", "payment sent", "Payout complete"]
    
    def __init__(self, config: Config):
        self.config = config
        self.github: Optional[GitHubClient] = None
        
        if config.github.token:
            self.github = GitHubClient(
                token=config.github.token,
                owner=config.github.owner,
                repo=config.github.repo,
                rate_limit_buffer=config.github.rate_limit_buffer,
            )
    
    def is_claim_comment(self, comment: ClaimComment) -> bool:
        """Check if a comment is a bounty claim."""
        body_lower = comment.body.lower()
        
        # Check for claim keywords
        for keyword in self.CLAIM_KEYWORDS:
            if keyword in body_lower:
                return True
        
        # Check for wallet address (strong indicator of claim)
        if self._extract_wallet(comment.body):
            return True
        
        return False
    
    def is_paid_comment(self, comment: ClaimComment) -> bool:
        """Check if a comment indicates payment was made."""
        for keyword in self.PAID_KEYWORDS:
            if keyword in comment.body:
                return True
        return False
    
    def _extract_wallet(self, text: str) -> Optional[str]:
        """Extract wallet address from text."""
        for pattern in self.WALLET_PATTERNS:
            match = re.search(pattern, text)
            if match:
                # Get the matched group (either group 0 or group 1)
                wallet = match.group(1) if len(match.groups()) > 0 else match.group(0)
                wallet = wallet.strip().rstrip(",.")
                
                # Ensure wallet starts with RTC
                if not wallet.startswith("RTC"):
                    wallet = f"RTC{wallet}"
                
                return wallet
        return None
    
    def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text."""
        return re.findall(self.URL_PATTERN, text)
    
    def parse_claim_comment(self, comment: ClaimComment) -> ClaimComment:
        """Parse a claim comment to extract relevant data."""
        # Extract wallet
        comment.wallet_address = self._extract_wallet(comment.body)
        
        # Extract URLs
        urls = self._extract_urls(comment.body)
        comment.additional_urls = urls
        
        # Try to identify proof URLs
        for url in urls:
            url_lower = url.lower()
            if "github.com" in url_lower and "/following" in url_lower:
                comment.follow_proof_url = url
            elif "github.com" in url_lower and "/stars" in url_lower:
                comment.star_proof_url = url
        
        return comment
    
    def verify_follow(self, username: str) -> VerificationCheck:
        """Verify user is following Scottcjn."""
        if not self.github:
            return VerificationCheck(
                name="GitHub Follow",
                status=VerificationStatus.SKIPPED,
                message="GitHub API not configured",
            )
        
        try:
            is_following = self.github.check_following(
                username,
                self.config.github.target_user,
            )
            
            if is_following:
                return VerificationCheck(
                    name="GitHub Follow",
                    status=VerificationStatus.PASSED,
                    message=f"@{username} is following @{self.config.github.target_user}",
                )
            else:
                return VerificationCheck(
                    name="GitHub Follow",
                    status=VerificationStatus.FAILED,
                    message=f"@{username} is NOT following @{self.config.github.target_user}",
                )
        except RateLimitExceeded as e:
            return VerificationCheck(
                name="GitHub Follow",
                status=VerificationStatus.ERROR,
                message=f"Rate limit: {e}",
            )
        except Exception as e:
            return VerificationCheck(
                name="GitHub Follow",
                status=VerificationStatus.ERROR,
                message=f"Error checking follow: {e}",
            )
    
    def verify_stars(self, username: str) -> VerificationCheck:
        """Verify user has starred minimum repos."""
        if not self.github:
            return VerificationCheck(
                name="GitHub Stars",
                status=VerificationStatus.SKIPPED,
                message="GitHub API not configured",
            )
        
        try:
            star_count = self.github.get_starred_repos_count(
                username,
                self.config.github.owner,
            )
            
            passed = star_count >= self.config.min_star_count
            
            return VerificationCheck(
                name="GitHub Stars",
                status=VerificationStatus.PASSED if passed else VerificationStatus.FAILED,
                message=f"@{username} has starred {star_count}/{self.config.min_star_count} required repos",
                details={"star_count": star_count, "required": self.config.min_star_count},
            )
        except RateLimitExceeded as e:
            return VerificationCheck(
                name="GitHub Stars",
                status=VerificationStatus.ERROR,
                message=f"Rate limit: {e}",
            )
        except Exception as e:
            return VerificationCheck(
                name="GitHub Stars",
                status=VerificationStatus.ERROR,
                message=f"Error checking stars: {e}",
            )
    
    def verify_wallet(self, wallet_address: str) -> VerificationCheck:
        """Verify wallet exists and has minimum balance."""
        if not self.config.rustchain.enabled:
            return VerificationCheck(
                name="Wallet Check",
                status=VerificationStatus.SKIPPED,
                message="RustChain node check disabled",
            )
        
        if not wallet_address:
            return VerificationCheck(
                name="Wallet Check",
                status=VerificationStatus.FAILED,
                message="No wallet address provided",
            )
        
        try:
            balance = self._check_wallet_balance(wallet_address)
            
            if balance >= self.config.rustchain.min_balance:
                return VerificationCheck(
                    name="Wallet Check",
                    status=VerificationStatus.PASSED,
                    message=f"Wallet {wallet_address[:10]}... has balance {balance:.2f} WRTC",
                    details={"balance": balance, "min_required": self.config.rustchain.min_balance},
                )
            else:
                return VerificationCheck(
                    name="Wallet Check",
                    status=VerificationStatus.FAILED,
                    message=f"Wallet balance {balance:.2f} below minimum {self.config.rustchain.min_balance}",
                    details={"balance": balance, "min_required": self.config.rustchain.min_balance},
                )
        except WalletCheckError as e:
            return VerificationCheck(
                name="Wallet Check",
                status=VerificationStatus.ERROR,
                message=f"Wallet check error: {e}",
            )
        except Exception as e:
            return VerificationCheck(
                name="Wallet Check",
                status=VerificationStatus.ERROR,
                message=f"Unexpected error: {e}",
            )
    
    def _check_wallet_balance(self, wallet_address: str) -> float:
        """Check wallet balance via RustChain node API."""
        url = f"{self.config.rustchain.node_url}/wallet/balance"
        
        try:
            req = Request(
                f"{url}?miner_id={wallet_address}",
                headers={
                    "Accept": "application/json",
                    "User-Agent": "rustchain-bounty-verifier/1.0.0",
                },
            )
            
            with urlopen(req, timeout=self.config.rustchain.wallet_check_timeout) as resp:
                data = resp.read()
                result = data.json() if hasattr(data, 'json') else __import__('json').loads(data.decode())
                
                if isinstance(result, dict):
                    return float(result.get("amount_i64", 0) / 1e6)  # Convert from micro units
                return 0.0
                
        except URLError as e:
            raise WalletCheckError(f"Failed to connect to node: {e}")
        except Exception as e:
            raise WalletCheckError(f"Balance check failed: {e}")
    
    def verify_url_liveness(self, urls: List[str]) -> List[VerificationCheck]:
        """Check if provided URLs are live."""
        checks = []
        
        if not self.config.url_check.enabled:
            checks.append(VerificationCheck(
                name="URL Liveness",
                status=VerificationStatus.SKIPPED,
                message="URL liveness check disabled",
            ))
            return checks
        
        for url in urls:
            try:
                # Check HTTPS requirement
                if self.config.url_check.require_https and not url.startswith("https://"):
                    checks.append(VerificationCheck(
                        name=f"URL: {url[:50]}",
                        status=VerificationStatus.FAILED,
                        message="URL must use HTTPS",
                    ))
                    continue
                
                # Check domain allowlist
                from urllib.parse import urlparse
                parsed = urlparse(url)
                if self.config.url_check.allowed_domains:
                    if not any(d in parsed.netloc for d in self.config.url_check.allowed_domains):
                        checks.append(VerificationCheck(
                            name=f"URL: {url[:50]}",
                            status=VerificationStatus.FAILED,
                            message=f"Domain not in allowlist: {parsed.netloc}",
                        ))
                        continue
                
                # Check liveness
                req = Request(
                    url,
                    headers={"User-Agent": "rustchain-bounty-verifier/1.0.0"},
                    method="HEAD",
                )
                
                with urlopen(req, timeout=self.config.url_check.timeout) as resp:
                    if resp.status < 400:
                        checks.append(VerificationCheck(
                            name=f"URL: {url[:50]}",
                            status=VerificationStatus.PASSED,
                            message=f"URL is live (status {resp.status})",
                        ))
                    else:
                        checks.append(VerificationCheck(
                            name=f"URL: {url[:50]}",
                            status=VerificationStatus.FAILED,
                            message=f"URL returned status {resp.status}",
                        ))
                        
            except URLError as e:
                checks.append(VerificationCheck(
                    name=f"URL: {url[:50]}",
                    status=VerificationStatus.FAILED,
                    message=f"URL unreachable: {e}",
                ))
            except Exception as e:
                checks.append(VerificationCheck(
                    name=f"URL: {url[:50]}",
                    status=VerificationStatus.ERROR,
                    message=f"Error checking URL: {e}",
                ))
        
        return checks
    
    def check_duplicates(
        self,
        claim: ClaimComment,
        all_comments: List[ClaimComment],
    ) -> VerificationCheck:
        """Check for duplicate claims from the same user."""
        if not self.config.check_duplicates:
            return VerificationCheck(
                name="Duplicate Check",
                status=VerificationStatus.SKIPPED,
                message="Duplicate check disabled",
            )
        
        # Find previous claims from same user
        previous_claims = []
        for comment in all_comments:
            if comment.id >= claim.id:
                continue  # Skip current and future comments
            if comment.user_id != claim.user_id:
                continue
            
            # Check if this was a claim
            if self.is_claim_comment(comment):
                # Check if it was already paid
                is_paid = self.is_paid_comment(comment)
                previous_claims.append((comment, is_paid))
        
        if not previous_claims:
            return VerificationCheck(
                name="Duplicate Check",
                status=VerificationStatus.PASSED,
                message="No previous claims found",
            )
        
        # Check if any previous claim was paid
        for prev_claim, was_paid in previous_claims:
            if was_paid:
                return VerificationCheck(
                    name="Duplicate Check",
                    status=VerificationStatus.FAILED,
                    message=f"User already has a paid claim (#{prev_claim.id})",
                    details={"previous_claim_id": prev_claim.id, "previous_claim_url": prev_claim.html_url},
                )
        
        return VerificationCheck(
            name="Duplicate Check",
            status=VerificationStatus.PASSED,
            message=f"Found {len(previous_claims)} unpaid previous claim(s)",
            details={"previous_claims": len(previous_claims)},
        )
    
    def calculate_payout(
        self,
        result: VerificationResult,
        star_count: int = 0,
        has_vintage_cpu: bool = False,
        is_node_operator: bool = False,
    ) -> float:
        """Calculate payout amount based on verification results and coefficients."""
        base = self.config.payout.base_amount
        coefficient = self.config.payout.follow_multiplier
        
        # Star bonus
        if star_count > 0:
            star_bonus = min(
                star_count * self.config.payout.star_multiplier,
                self.config.payout.max_stars_bonus,
            )
            coefficient += star_bonus
        
        # Vintage CPU bonus
        if has_vintage_cpu:
            coefficient += self.config.payout.vintage_cpu_bonus
        
        # Node operator bonus
        if is_node_operator:
            coefficient += self.config.payout.node_operator_bonus
        
        result.payout_coefficient = coefficient
        result.payout_amount = base * coefficient
        
        return result.payout_amount
    
    def verify_claim(
        self,
        claim: ClaimComment,
        all_comments: Optional[List[ClaimComment]] = None,
    ) -> VerificationResult:
        """
        Perform complete verification of a bounty claim.
        
        Args:
            claim: The claim comment to verify
            all_comments: All comments on the issue (for duplicate detection)
        
        Returns:
            VerificationResult with all checks and overall status
        """
        # Parse the claim
        claim = self.parse_claim_comment(claim)
        
        # Initialize result
        result = VerificationResult(
            claim=claim,
            overall_status=VerificationStatus.PENDING,
        )
        
        # Run verification checks
        # 1. Follow check
        if self.config.require_follow:
            result.add_check(self.verify_follow(claim.user_login))
        
        # 2. Star check
        if self.config.require_stars:
            result.add_check(self.verify_stars(claim.user_login))
        
        # 3. Wallet check
        if self.config.require_wallet and claim.wallet_address:
            result.add_check(self.verify_wallet(claim.wallet_address))
        elif self.config.require_wallet:
            result.add_check(VerificationCheck(
                name="Wallet Check",
                status=VerificationStatus.FAILED,
                message="No wallet address provided in claim",
            ))
        
        # 4. URL liveness check
        if self.config.require_url_liveness and claim.additional_urls:
            for check in self.verify_url_liveness(claim.additional_urls):
                result.add_check(check)
        
        # 5. Duplicate check
        if all_comments:
            result.add_check(self.check_duplicates(claim, all_comments))
        
        # Calculate payout if all checks passed
        if result.overall_status == VerificationStatus.PASSED:
            star_count = 0
            for check in result.checks:
                if check.name == "GitHub Stars" and check.details:
                    star_count = check.details.get("star_count", 0)
            
            self.calculate_payout(result, star_count=star_count)
        
        return result
    
    def verify_issue_claims(
        self,
        issue_number: int,
    ) -> List[VerificationResult]:
        """
        Verify all claims on a bounty issue.
        
        Args:
            issue_number: The GitHub issue number
        
        Returns:
            List of VerificationResult for each claim
        """
        if not self.github:
            raise RuntimeError("GitHub client not configured")
        
        # Get all comments
        comments = self.github.get_issue_comments(issue_number)
        
        # Find all claims
        claims = [c for c in comments if self.is_claim_comment(c)]
        
        # Verify each claim
        results = []
        for claim in claims:
            result = self.verify_claim(claim, all_comments=comments)
            results.append(result)
        
        return results
    
    def post_verification_comment(
        self,
        issue_number: int,
        result: VerificationResult,
    ) -> Optional[str]:
        """
        Post verification result as a comment.
        
        Args:
            issue_number: The GitHub issue number
            result: The verification result
        
        Returns:
            URL of the posted comment, or None if dry-run
        """
        if self.config.dry_run:
            logger.info(f"[DRY-RUN] Would post comment to issue #{issue_number}:")
            logger.info(result.to_comment_body())
            return None
        
        if not self.github:
            raise RuntimeError("GitHub client not configured")
        
        body = result.to_comment_body()
        response = self.github.post_comment(issue_number, body)
        
        if response:
            return response.get("html_url")
        return None
