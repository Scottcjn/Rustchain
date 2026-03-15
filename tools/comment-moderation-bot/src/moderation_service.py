"""
Moderation Service.

Main orchestrator that coordinates comment analysis and moderation actions.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from .audit_logger import AuditLogger
from .config import BotConfig
from .feature_extractor import CommentFeatures, FeatureExtractor
from .github_client import CommentData, GitHubClient, IssueData
from .github_auth import GitHubAuth
from .idempotency import DeliveryCache, IdempotencyHandler
from .scorer import HybridScorer, ScoreBreakdown
from .whitelist import WhitelistChecker, WhitelistCheckResult


@dataclass
class ModerationDecision:
    """Result of moderation analysis."""

    action: str  # "allow", "flag", "delete"
    risk_score: float
    breakdown: ScoreBreakdown
    is_exempt: bool
    exemption_reason: Optional[str] = None
    dry_run: bool = True


@dataclass
class ModerationContext:
    """Context data for moderation decision."""

    comment: CommentData
    issue: IssueData
    delivery_id: str
    event_type: str
    repo: str
    installation_id: int


class ModerationService:
    """
    Main moderation service that orchestrates comment analysis
    and enforcement actions.
    """

    def __init__(
        self,
        config: BotConfig,
        github_auth: GitHubAuth,
        audit_logger: AuditLogger,
    ):
        self.config = config
        self.github_auth = github_auth

        # Initialize components
        self.feature_extractor = FeatureExtractor()
        self.scorer = HybridScorer(
            spam_keywords_weight=config.scoring.spam_keywords_weight,
            link_ratio_weight=config.scoring.link_ratio_weight,
            length_penalty_weight=config.scoring.length_penalty_weight,
            repetition_weight=config.scoring.repetition_weight,
            mention_spam_weight=config.scoring.mention_spam_weight,
            semantic_weight=config.scoring.semantic_weight,
            enable_semantic=config.enable_semantic_classifier,
            semantic_endpoint=config.semantic_classifier_endpoint,
        )
        self.whitelist_checker = WhitelistChecker(config.whitelist)
        self.github_client = GitHubClient(
            auth=github_auth,
            api_base_url=config.github_app.api_base_url if config.github_app else "https://api.github.com",
        )

        # Idempotency
        self.delivery_cache = DeliveryCache(
            ttl_seconds=config.delivery_cache_ttl_seconds
        )
        self.idempotency = IdempotencyHandler(self.delivery_cache)

        # Audit logging
        self.audit_logger = audit_logger

        # Operational state
        self.enabled = config.enabled
        self.dry_run = config.dry_run

    async def process_comment_event(
        self,
        comment_data: dict[str, Any],
        issue_data: dict[str, Any],
        delivery_id: str,
        event_type: str,
        repo: str,
        installation_id: int,
    ) -> ModerationDecision:
        """
        Process a comment creation event.

        Args:
            comment_data: Comment payload from webhook
            issue_data: Issue payload from webhook
            delivery_id: GitHub delivery ID
            event_type: Event type
            repo: Repository name
            installation_id: Installation ID

        Returns:
            ModerationDecision
        """
        # Check if bot is enabled
        if not self.enabled:
            return ModerationDecision(
                action="allow",
                risk_score=0.0,
                breakdown=ScoreBreakdown(),
                is_exempt=False,
                exemption_reason="Bot is disabled",
                dry_run=self.dry_run,
            )

        # Parse comment data
        comment = self._parse_comment(comment_data)
        issue = self._parse_issue(issue_data)

        # Create context
        context = ModerationContext(
            comment=comment,
            issue=issue,
            delivery_id=delivery_id,
            event_type=event_type,
            repo=repo,
            installation_id=installation_id,
        )

        # Check idempotency
        is_duplicate, was_recorded = self.idempotency.check_and_record(
            delivery_id=delivery_id,
            event_type=event_type,
            repo=repo,
            comment_id=comment.id,
        )

        if is_duplicate:
            self.audit_logger.log_action(
                action="skipped_duplicate",
                comment_id=comment.id,
                repo=repo,
                issue_number=issue.number,
                risk_score=0.0,
                author=comment.author_login,
                decision="skip",
                dry_run=self.dry_run,
                delivery_id=delivery_id,
                additional_data={"reason": "Duplicate delivery ID"},
            )
            return ModerationDecision(
                action="allow",
                risk_score=0.0,
                breakdown=ScoreBreakdown(),
                is_exempt=False,
                exemption_reason="Duplicate delivery (replay)",
                dry_run=self.dry_run,
            )

        # Perform moderation analysis
        decision = await self._analyze_and_decide(context)

        # Update idempotency record with action taken
        if was_recorded:
            self.delivery_cache._cache  # Access to trigger any needed updates

        # Take action if needed
        if decision.action == "delete":
            await self._execute_action(decision, context)

        return decision

    def _parse_comment(self, data: dict[str, Any]) -> CommentData:
        """Parse comment data from webhook payload."""
        return CommentData(
            id=data["id"],
            body=data.get("body") or "",
            author_login=data["user"]["login"],
            author_association=data.get("author_association", "NONE"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            issue_url=data["issue_url"],
            html_url=data["html_url"],
        )

    def _parse_issue(self, data: dict[str, Any]) -> IssueData:
        """Parse issue data from webhook payload."""
        return IssueData(
            number=data["number"],
            title=data.get("title", ""),
            state=data.get("state", "open"),
            labels=[label["name"] for label in data.get("labels", [])],
            created_at=data["created_at"],
            comments_count=data.get("comments", 0),
        )

    async def _analyze_and_decide(
        self, context: ModerationContext
    ) -> ModerationDecision:
        """Analyze comment and make moderation decision."""
        # Check whitelist
        whitelist_result = await self._check_whitelist(context)

        if whitelist_result.is_exempt:
            decision = ModerationDecision(
                action="allow",
                risk_score=0.0,
                breakdown=ScoreBreakdown(),
                is_exempt=True,
                exemption_reason=whitelist_result.reason,
                dry_run=self.dry_run,
            )

            self.audit_logger.log_action(
                action="allowed_whitelisted",
                comment_id=context.comment.id,
                repo=context.repo,
                issue_number=context.issue.number,
                risk_score=0.0,
                breakdown=ScoreBreakdown(),
                author=context.comment.author_login,
                decision="allow",
                dry_run=self.dry_run,
                delivery_id=context.delivery_id,
                additional_data={"exemption_reason": whitelist_result.reason},
            )

            return decision

        # Extract features
        features = self._extract_features(context)

        # Calculate risk score
        risk_score, breakdown = self.scorer.score(features)

        # Determine action based on thresholds
        if risk_score >= self.config.scoring.auto_delete_threshold:
            action = "delete"
        elif risk_score >= self.config.scoring.flag_threshold:
            action = "flag"
        else:
            action = "allow"

        # Create decision
        decision = ModerationDecision(
            action=action,
            risk_score=risk_score,
            breakdown=breakdown,
            is_exempt=False,
            dry_run=self.dry_run,
        )

        # Log the action
        self.audit_logger.log_action(
            action=f"{action}_comment",
            comment_id=context.comment.id,
            repo=context.repo,
            issue_number=context.issue.number,
            risk_score=risk_score,
            breakdown=breakdown,
            author=context.comment.author_login,
            decision="auto",
            dry_run=self.dry_run,
            delivery_id=context.delivery_id,
        )

        return decision

    async def _check_whitelist(
        self, context: ModerationContext
    ) -> WhitelistCheckResult:
        """Check if comment is exempt from moderation."""
        # Check repository exemption
        repo_result = self.whitelist_checker.check_repository(context.repo)
        if repo_result.is_exempt:
            return repo_result

        # Check issue labels
        label_result = self.whitelist_checker.check_issue_labels(
            context.issue.labels
        )
        if label_result.is_exempt:
            return label_result

        # Check user (with GitHub API for org membership)
        try:
            user_result = await self.whitelist_checker.check_with_github(
                username=context.comment.author_login,
                repo=context.repo,
                issue_labels=context.issue.labels,
                github_client=self.github_client,
                installation_id=context.installation_id,
            )
            return user_result
        except Exception:
            # Fall back to basic user check if API fails
            return self.whitelist_checker.check_user(
                context.comment.author_login,
                author_association=context.comment.author_association,
            )

    def _extract_features(self, context: ModerationContext) -> CommentFeatures:
        """Extract features from comment."""
        # Build context for feature extraction
        feature_context = {
            "is_first_comment": context.issue.comments_count == 0,
            "comment_position": context.issue.comments_count,
        }

        return self.feature_extractor.extract(
            body=context.comment.body,
            context=feature_context,
        )

    async def _execute_action(
        self, decision: ModerationDecision, context: ModerationContext
    ) -> bool:
        """Execute the moderation action."""
        if decision.action != "delete":
            return False

        if self.dry_run:
            self.audit_logger.log_action(
                action="delete_dry_run",
                comment_id=context.comment.id,
                repo=context.repo,
                issue_number=context.issue.number,
                risk_score=decision.risk_score,
                breakdown=decision.breakdown,
                author=context.comment.author_login,
                decision="auto",
                dry_run=True,
                delivery_id=context.delivery_id,
                additional_data={
                    "reason": "Dry run mode - comment not actually deleted"
                },
            )
            return False

        # Actually delete the comment
        try:
            repo_owner, repo_name = context.repo.split("/", 1)

            success = await self.github_client.delete_comment(
                repo_owner=repo_owner,
                repo_name=repo_name,
                comment_id=context.comment.id,
                installation_id=context.installation_id,
            )

            if success:
                self.audit_logger.log_action(
                    action="deleted",
                    comment_id=context.comment.id,
                    repo=context.repo,
                    issue_number=context.issue.number,
                    risk_score=decision.risk_score,
                    breakdown=decision.breakdown,
                    author=context.comment.author_login,
                    decision="auto",
                    dry_run=False,
                    delivery_id=context.delivery_id,
                )
            else:
                self.audit_logger.log_error(
                    error_type="delete_failed",
                    message="GitHub API returned failure for comment deletion",
                    comment_id=context.comment.id,
                    repo=context.repo,
                    delivery_id=context.delivery_id,
                )

            return success

        except Exception as e:
            self.audit_logger.log_error(
                error_type="delete_error",
                message=str(e),
                comment_id=context.comment.id,
                repo=context.repo,
                delivery_id=context.delivery_id,
                traceback=repr(e),
            )
            return False

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "delivery_cache": self.delivery_cache.get_stats(),
            "thresholds": {
                "auto_delete": self.config.scoring.auto_delete_threshold,
                "flag": self.config.scoring.flag_threshold,
            },
        }
