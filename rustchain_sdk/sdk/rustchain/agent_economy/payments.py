"""
x402 Payment Protocol

Implements machine-to-machine payments using the x402 protocol (HTTP 402 Payment Required).
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import time

from rustchain.exceptions import ValidationError, APIError


class PaymentStatus(Enum):
    """Payment status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass
class X402Payment:
    """
    Represents an x402 protocol payment.
    
    Attributes:
        payment_id: Unique payment identifier
        from_agent: Sender agent ID
        to_agent: Recipient agent ID
        amount: Payment amount in RTC
        memo: Optional payment memo
        status: Payment status
        created_at: Creation timestamp
        completed_at: Completion timestamp
        tx_hash: Transaction hash on completion
        resource: Protected resource being accessed
    """
    payment_id: str
    from_agent: str
    to_agent: str
    amount: float
    memo: Optional[str] = None
    status: PaymentStatus = PaymentStatus.PENDING
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tx_hash: Optional[str] = None
    resource: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "payment_id": self.payment_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "amount": self.amount,
            "memo": self.memo,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "tx_hash": self.tx_hash,
            "resource": self.resource,
        }


@dataclass
class PaymentIntent:
    """
    Payment intent for x402 flow.
    
    Attributes:
        intent_id: Unique intent identifier
        resource: URL of protected resource
        amount: Required payment amount
        recipient: Recipient agent ID
        expires_at: Intent expiration time
    """
    intent_id: str
    resource: str
    amount: float
    recipient: str
    expires_at: datetime
    
    def is_expired(self) -> bool:
        """Check if intent has expired"""
        return datetime.utcnow() > self.expires_at


class PaymentProcessor:
    """
    Handles x402 payment processing for agent-to-agent transactions.
    
    The x402 protocol enables machine-to-machine micropayments via
    HTTP 402 Payment Required responses and payment negotiation.
    
    Example:
        >>> processor = PaymentProcessor(client)
        >>> 
        >>> # Send direct payment
        >>> payment = processor.send(
        ...     to="content-creator",
        ...     amount=0.5,
        ...     memo="Thanks for the video!"
        ... )
        >>> 
        >>> # Request payment for protected resource
        >>> intent = processor.create_intent(
        ...     resource="/api/premium/analytics",
        ...     amount=0.1
        ... )
        >>> 
        >>> # Process incoming payment
        >>> processor.process_payment(payment_id)
    """
    
    def __init__(self, client):
        self.client = client
        self._pending_intents: Dict[str, PaymentIntent] = {}

    def send(
        self,
        to: str,
        amount: float,
        memo: Optional[str] = None,
        from_agent: Optional[str] = None,
        resource: Optional[str] = None,
    ) -> X402Payment:
        """
        Send an x402 payment to another agent.
        
        Args:
            to: Recipient agent ID
            amount: Payment amount in RTC
            memo: Optional payment memo
            from_agent: Sender agent ID (uses client's agent_id if not provided)
            resource: Optional resource being paid for
            
        Returns:
            X402Payment instance
            
        Raises:
            ValidationError: If parameters are invalid
            APIError: If payment fails
        """
        from_agent = from_agent or self.client.config.agent_id
        if not from_agent:
            raise ValidationError("from_agent must be provided")
        
        if amount <= 0:
            raise ValidationError("amount must be positive")
        
        if not to or to == from_agent:
            raise ValidationError("invalid recipient")
        
        # Generate payment ID
        timestamp = str(int(time.time() * 1000))
        payment_hash = hashlib.sha256(
            f"{from_agent}:{to}:{amount}:{timestamp}".encode()
        ).hexdigest()[:16]
        payment_id = f"pay_{payment_hash}"
        
        payload = {
            "payment_id": payment_id,
            "from_agent": from_agent,
            "to_agent": to,
            "amount": amount,
            "memo": memo,
            "resource": resource,
        }
        
        result = self.client._request(
            "POST",
            "/api/agent/payment/send",
            json_payload=payload,
        )
        
        if result.get("error"):
            raise APIError(f"Payment failed: {result['error']}")
        
        return X402Payment(
            payment_id=payment_id,
            from_agent=from_agent,
            to_agent=to,
            amount=amount,
            memo=memo,
            status=PaymentStatus(result.get("status", "pending")),
            created_at=datetime.utcnow(),
            resource=resource,
        )

    def request(
        self,
        from_agent: str,
        amount: float,
        description: str,
        resource: Optional[str] = None,
    ) -> PaymentIntent:
        """
        Request payment from another agent.
        
        Args:
            from_agent: Agent to request payment from
            amount: Requested amount in RTC
            description: Payment description
            resource: Optional resource URL
            
        Returns:
            PaymentIntent instance
        """
        to_agent = self.client.config.agent_id
        if not to_agent:
            raise ValidationError("client must have agent_id configured")
        
        intent_id = f"intent_{hashlib.sha256(f'{from_agent}:{to_agent}:{time.time()}'.encode()).hexdigest()[:12]}"
        expires_at = datetime.utcnow().replace(second=0, microsecond=0)
        
        intent = PaymentIntent(
            intent_id=intent_id,
            resource=resource or f"/api/agent/payment/{intent_id}",
            amount=amount,
            recipient=to_agent,
            expires_at=expires_at,
        )
        
        payload = {
            "intent_id": intent_id,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "amount": amount,
            "description": description,
            "resource": intent.resource,
            "expires_at": expires_at.isoformat(),
        }
        
        result = self.client._request(
            "POST",
            "/api/agent/payment/request",
            json_payload=payload,
        )
        
        self._pending_intents[intent_id] = intent
        return intent

    def process_intent(self, intent_id: str) -> X402Payment:
        """
        Process a payment intent (pay for requested resource).
        
        Args:
            intent_id: Payment intent identifier
            
        Returns:
            X402Payment instance
        """
        result = self.client._request(
            "POST",
            f"/api/agent/payment/intent/{intent_id}/pay",
        )
        
        return X402Payment(
            payment_id=result.get("payment_id", ""),
            from_agent=result.get("from_agent", ""),
            to_agent=result.get("to_agent", ""),
            amount=result.get("amount", 0.0),
            status=PaymentStatus(result.get("status", "pending")),
            created_at=datetime.utcnow(),
            resource=result.get("resource"),
        )

    def get_payment(self, payment_id: str) -> Optional[X402Payment]:
        """
        Get payment details.
        
        Args:
            payment_id: Payment identifier
            
        Returns:
            X402Payment or None if not found
        """
        result = self.client._request("GET", f"/api/agent/payment/{payment_id}")
        
        if not result or "error" in result:
            return None
        
        return X402Payment(
            payment_id=result.get("payment_id", ""),
            from_agent=result.get("from_agent", ""),
            to_agent=result.get("to_agent", ""),
            amount=result.get("amount", 0.0),
            memo=result.get("memo"),
            status=PaymentStatus(result.get("status", "pending")),
            created_at=datetime.fromisoformat(result["created_at"]) if result.get("created_at") else None,
            completed_at=datetime.fromisoformat(result["completed_at"]) if result.get("completed_at") else None,
            tx_hash=result.get("tx_hash"),
            resource=result.get("resource"),
        )

    def get_history(
        self,
        agent_id: Optional[str] = None,
        limit: int = 50,
        status: Optional[PaymentStatus] = None,
    ) -> List[X402Payment]:
        """
        Get payment history.
        
        Args:
            agent_id: Filter by agent (sent or received)
            limit: Maximum results
            status: Filter by status
            
        Returns:
            List of X402Payment
        """
        params = {"limit": limit}
        if status:
            params["status"] = status.value
        
        endpoint = f"/api/agent/payment/history/{agent_id}" if agent_id else "/api/agent/payment/history"
        result = self.client._request("GET", endpoint, params=params)
        
        payments = []
        for data in result.get("payments", []):
            payment = X402Payment(
                payment_id=data.get("payment_id", ""),
                from_agent=data.get("from_agent", ""),
                to_agent=data.get("to_agent", ""),
                amount=data.get("amount", 0.0),
                memo=data.get("memo"),
                status=PaymentStatus(data.get("status", "pending")),
                tx_hash=data.get("tx_hash"),
            )
            payments.append(payment)
        
        return payments

    def refund(self, payment_id: str, reason: Optional[str] = None) -> bool:
        """
        Refund a payment.
        
        Args:
            payment_id: Payment identifier
            reason: Refund reason
            
        Returns:
            True if successful
        """
        payload = {"reason": reason} if reason else {}
        
        result = self.client._request(
            "POST",
            f"/api/agent/payment/{payment_id}/refund",
            json_payload=payload,
        )
        
        return result.get("success", False)

    def x402_challenge(
        self,
        resource: str,
        required_amount: float,
    ) -> Dict[str, Any]:
        """
        Generate x402 challenge for protected resource.
        
        This is used when an agent needs to require payment
        for accessing a resource.
        
        Args:
            resource: Protected resource URL/path
            required_amount: Required payment amount
            
        Returns:
            Dict with x402 challenge information
        """
        payload = {
            "resource": resource,
            "amount": required_amount,
            "recipient": self.client.config.agent_id,
        }
        
        result = self.client._request(
            "POST",
            "/api/agent/payment/x402/challenge",
            json_payload=payload,
        )
        
        return {
            "status_code": 402,
            "headers": {
                "X-Pay-To": result.get("wallet_address", ""),
                "X-Pay-Amount": str(required_amount),
                "X-Pay-Resource": resource,
                "X-Pay-Nonce": result.get("nonce", ""),
            },
            "body": {
                "error": "Payment Required",
                "payment_info": result,
            },
        }
