"""
FastAPI Webhook Receiver.

Handles incoming GitHub webhook events for comment moderation.
"""

import hashlib
import hmac
import logging
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from .audit_logger import AuditLogger
from .config import BotConfig, get_config
from .github_auth import GitHubAuth
from .moderation_service import ModerationService


logger = logging.getLogger(__name__)


def create_app(config: Optional[BotConfig] = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        config: Optional configuration override

    Returns:
        Configured FastAPI application
    """
    if config is None:
        config = get_config().moderation_bot

    # Initialize components
    audit_logger = AuditLogger(
        log_dir=config.log_dir,
        log_level=config.log_level,
    )

    # Only initialize GitHub auth if credentials are available
    github_auth = None
    moderation_service = None

    if config.github_app:
        github_auth = GitHubAuth(
            app_id=config.github_app.app_id,
            private_key=config.github_app.private_key.get_secret_value(),
            client_id=config.github_app.client_id,
            client_secret=config.github_app.client_secret.get_secret_value(),
            api_base_url=config.github_app.api_base_url,
        )

        moderation_service = ModerationService(
            config=config,
            github_auth=github_auth,
            audit_logger=audit_logger,
        )

    # Create FastAPI app
    app = FastAPI(
        title="Comment Moderation Bot",
        description="GitHub App webhook receiver for comment moderation",
        version="1.0.0",
    )

    # Store config and services in app state
    app.state.config = config
    app.state.audit_logger = audit_logger
    app.state.github_auth = github_auth
    app.state.moderation_service = moderation_service

    # Register routes
    register_routes(app, config)

    return app


def register_routes(app: FastAPI, config: BotConfig) -> None:
    """Register API routes."""

    @app.get("/health")
    async def health_check() -> dict[str, Any]:
        """Health check endpoint."""
        service = app.state.moderation_service
        return {
            "status": "healthy",
            "enabled": config.enabled,
            "dry_run": config.dry_run,
            "service_stats": service.get_stats() if service else None,
        }

    @app.get("/ready")
    async def readiness_check() -> dict[str, str]:
        """Readiness check endpoint."""
        return {"status": "ready"}

    @app.post("/webhook")
    async def handle_webhook(
        request: Request,
        x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
        x_github_delivery: Optional[str] = Header(
            None, alias="X-GitHub-Delivery"
        ),
        x_hub_signature_256: Optional[str] = Header(
            None, alias="X-Hub-Signature-256"
        ),
        x_hub_signature: Optional[str] = Header(None, alias="X-Hub-Signature"),
    ) -> Response:
        """
        Handle incoming GitHub webhook events.

        Only processes issue_comment events for comment moderation.
        """
        audit_logger = app.state.audit_logger
        moderation_service = app.state.moderation_service

        # Validate required headers
        if not x_github_event:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing X-GitHub-Event header",
            )

        if not x_github_delivery:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing X-GitHub-Delivery header",
            )

        # Verify webhook signature
        body = await request.body()

        if not verify_webhook_signature(
            body=body,
            signature=x_hub_signature_256 or x_hub_signature,
            secret=config.github_app.webhook_secret.get_secret_value()
            if config.github_app
            else "",
        ):
            audit_logger.log_error(
                error_type="signature_verification_failed",
                message="Webhook signature verification failed",
                delivery_id=x_github_delivery,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )

        # Parse payload
        try:
            payload = await request.json()
        except Exception as e:
            audit_logger.log_error(
                error_type="invalid_payload",
                message=f"Failed to parse webhook payload: {e}",
                delivery_id=x_github_delivery,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload",
            )

        # Log webhook receipt
        repo = payload.get("repository", {}).get("full_name", "unknown")
        audit_logger.log_webhook_event(
            event_type=x_github_event,
            delivery_id=x_github_delivery,
            repo=repo,
            action=payload.get("action", "unknown"),
            payload_summary={
                "comment_id": payload.get("comment", {}).get("id"),
                "issue_number": payload.get("issue", {}).get("number"),
                "author": payload.get("comment", {})
                .get("user", {})
                .get("login"),
            },
        )

        # Only handle issue_comment events
        if x_github_event != "issue_comment":
            logger.debug(
                f"Ignoring event type: {x_github_event}"
            )
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"status": "ignored", "reason": "Not an issue_comment event"},
            )

        # Check action type
        action = payload.get("action")
        if action != "created":
            logger.debug(f"Ignoring issue_comment action: {action}")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"status": "ignored", "reason": f"Action '{action}' not handled"},
            )

        # Check if moderation service is available
        if not moderation_service:
            logger.warning("Moderation service not initialized")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "error", "reason": "Service not initialized"},
            )

        # Extract required data
        try:
            comment = payload.get("comment", {})
            issue = payload.get("issue", {})
            installation = payload.get("installation", {})

            if not comment or not issue:
                raise ValueError("Missing comment or issue data")

            installation_id = installation.get("id")
            if not installation_id:
                raise ValueError("Missing installation ID")

        except Exception as e:
            audit_logger.log_error(
                error_type="invalid_payload",
                message=f"Missing required fields: {e}",
                delivery_id=x_github_delivery,
                repo=repo,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

        # Process the comment
        try:
            decision = await moderation_service.process_comment_event(
                comment_data=comment,
                issue_data=issue,
                delivery_id=x_github_delivery,
                event_type=x_github_event,
                repo=repo,
                installation_id=installation_id,
            )

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "processed",
                    "action": decision.action,
                    "risk_score": round(decision.risk_score, 4),
                    "dry_run": decision.dry_run,
                    "is_exempt": decision.is_exempt,
                    "exemption_reason": decision.exemption_reason,
                    "factors": decision.breakdown.factors,
                },
            )

        except Exception as e:
            audit_logger.log_error(
                error_type="processing_error",
                message=f"Error processing comment: {e}",
                delivery_id=x_github_delivery,
                repo=repo,
                comment_id=payload.get("comment", {}).get("id"),
                traceback=repr(e),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    @app.get("/stats")
    async def get_stats() -> dict[str, Any]:
        """Get service statistics."""
        service = app.state.moderation_service
        if not service:
            return {"error": "Service not initialized"}

        return service.get_stats()


def verify_webhook_signature(
    body: bytes, signature: Optional[str], secret: str
) -> bool:
    """
    Verify GitHub webhook signature.

    Args:
        body: Raw request body
        signature: Signature from X-Hub-Signature-256 header
        secret: Webhook secret

    Returns:
        True if signature is valid
    """
    if not signature:
        return False

    if not secret:
        logger.warning("No webhook secret configured")
        return False

    # Parse signature
    try:
        method, signature_hash = signature.split("=", 1)
    except ValueError:
        return False

    # Calculate expected signature
    if method == "sha256":
        expected = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
    elif method == "sha1":
        expected = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha1,
        ).hexdigest()
    else:
        return False

    # Constant-time comparison
    return hmac.compare_digest(expected, signature_hash)


# Default app instance for running directly
app = create_app()
