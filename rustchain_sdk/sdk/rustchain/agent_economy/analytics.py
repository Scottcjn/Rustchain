"""
Agent Analytics

Provides analytics and metrics for AI agent performance and earnings.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class AnalyticsPeriod(Enum):
    """Analytics period enumeration"""
    HOUR = "1h"
    DAY = "24h"
    WEEK = "7d"
    MONTH = "30d"
    ALL = "all"


@dataclass
class EarningsReport:
    """
    Earnings report for an agent.
    
    Attributes:
        agent_id: Agent identifier
        period: Reporting period
        total_earned: Total earnings in period
        transactions_count: Number of transactions
        avg_transaction: Average transaction size
        top_source: Top earning source
        sources: Breakdown by source
        trend: Earnings trend percentage
    """
    agent_id: str
    period: AnalyticsPeriod
    total_earned: float = 0.0
    transactions_count: int = 0
    avg_transaction: float = 0.0
    top_source: Optional[str] = None
    sources: Dict[str, float] = field(default_factory=dict)
    trend: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "agent_id": self.agent_id,
            "period": self.period.value,
            "total_earned": self.total_earned,
            "transactions_count": self.transactions_count,
            "avg_transaction": self.avg_transaction,
            "top_source": self.top_source,
            "sources": self.sources,
            "trend": self.trend,
        }


@dataclass
class ActivityMetrics:
    """
    Activity metrics for an agent.
    
    Attributes:
        agent_id: Agent identifier
        period: Reporting period
        active_hours: Hours with activity
        peak_hour: Hour with most activity
        requests_served: Total requests served
        payments_received: Payments received count
        payments_sent: Payments sent count
        avg_response_time: Average response time (ms)
        uptime_percentage: Uptime percentage
    """
    agent_id: str
    period: AnalyticsPeriod
    active_hours: int = 0
    peak_hour: int = 0
    requests_served: int = 0
    payments_received: int = 0
    payments_sent: int = 0
    avg_response_time: float = 0.0
    uptime_percentage: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "agent_id": self.agent_id,
            "period": self.period.value,
            "active_hours": self.active_hours,
            "peak_hour": self.peak_hour,
            "requests_served": self.requests_served,
            "payments_received": self.payments_received,
            "payments_sent": self.payments_sent,
            "avg_response_time": self.avg_response_time,
            "uptime_percentage": self.uptime_percentage,
        }


@dataclass
class VideoMetrics:
    """
    Video performance metrics for BoTTube integration.
    
    Attributes:
        video_id: Video identifier
        views: Total views
        tips_received: Number of tips
        tips_amount: Total tips amount in RTC
        avg_tip: Average tip size
        engagement_rate: Engagement rate percentage
        revenue_share: Agent's revenue share
    """
    video_id: str
    views: int = 0
    tips_received: int = 0
    tips_amount: float = 0.0
    avg_tip: float = 0.0
    engagement_rate: float = 0.0
    revenue_share: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "video_id": self.video_id,
            "views": self.views,
            "tips_received": self.tips_received,
            "tips_amount": self.tips_amount,
            "avg_tip": self.avg_tip,
            "engagement_rate": self.engagement_rate,
            "revenue_share": self.revenue_share,
        }


class AnalyticsClient:
    """
    Client for agent analytics and metrics.
    
    Provides comprehensive analytics for AI agents including
    earnings reports, activity metrics, and BoTTube integration.
    
    Example:
        >>> analytics = AnalyticsClient(agent_economy_client)
        >>> 
        >>> # Get earnings report
        >>> earnings = analytics.get_earnings(period=AnalyticsPeriod.WEEK)
        >>> print(f"Total earned: {earnings.total_earned} RTC")
        >>> 
        >>> # Get activity metrics
        >>> activity = analytics.get_activity(period=AnalyticsPeriod.DAY)
        >>> print(f"Uptime: {activity.uptime_percentage}%")
        >>> 
        >>> # Get video metrics (BoTTube)
        >>> video_metrics = analytics.get_video_metrics("video_123")
    """
    
    def __init__(self, client):
        self.client = client

    def get_earnings(
        self,
        agent_id: Optional[str] = None,
        period: AnalyticsPeriod = AnalyticsPeriod.WEEK,
    ) -> EarningsReport:
        """
        Get earnings report for an agent.
        
        Args:
            agent_id: Agent identifier (uses client's if not provided)
            period: Reporting period
            
        Returns:
            EarningsReport instance
        """
        aid = agent_id or self.client.config.agent_id
        if not aid:
            raise ValueError("agent_id must be provided")
        
        result = self.client._request(
            "GET",
            f"/api/agent/analytics/{aid}/earnings",
            params={"period": period.value},
        )
        
        return EarningsReport(
            agent_id=aid,
            period=period,
            total_earned=result.get("total_earned", 0.0),
            transactions_count=result.get("transactions_count", 0),
            avg_transaction=result.get("avg_transaction", 0.0),
            top_source=result.get("top_source"),
            sources=result.get("sources", {}),
            trend=result.get("trend", 0.0),
        )

    def get_activity(
        self,
        agent_id: Optional[str] = None,
        period: AnalyticsPeriod = AnalyticsPeriod.DAY,
    ) -> ActivityMetrics:
        """
        Get activity metrics for an agent.
        
        Args:
            agent_id: Agent identifier (uses client's if not provided)
            period: Reporting period
            
        Returns:
            ActivityMetrics instance
        """
        aid = agent_id or self.client.config.agent_id
        if not aid:
            raise ValueError("agent_id must be provided")
        
        result = self.client._request(
            "GET",
            f"/api/agent/analytics/{aid}/activity",
            params={"period": period.value},
        )
        
        return ActivityMetrics(
            agent_id=aid,
            period=period,
            active_hours=result.get("active_hours", 0),
            peak_hour=result.get("peak_hour", 0),
            requests_served=result.get("requests_served", 0),
            payments_received=result.get("payments_received", 0),
            payments_sent=result.get("payments_sent", 0),
            avg_response_time=result.get("avg_response_time", 0.0),
            uptime_percentage=result.get("uptime_percentage", 0.0),
        )

    def get_video_metrics(
        self,
        video_id: str,
        agent_id: Optional[str] = None,
    ) -> VideoMetrics:
        """
        Get video performance metrics (BoTTube integration).
        
        Args:
            video_id: Video identifier
            agent_id: Agent identifier (uses client's if not provided)
            
        Returns:
            VideoMetrics instance
        """
        aid = agent_id or self.client.config.agent_id
        if not aid:
            raise ValueError("agent_id must be provided")
        
        result = self.client._request(
            "GET",
            f"/api/agent/analytics/{aid}/video/{video_id}",
        )
        
        return VideoMetrics(
            video_id=video_id,
            views=result.get("views", 0),
            tips_received=result.get("tips_received", 0),
            tips_amount=result.get("tips_amount", 0.0),
            avg_tip=result.get("avg_tip", 0.0),
            engagement_rate=result.get("engagement_rate", 0.0),
            revenue_share=result.get("revenue_share", 0.0),
        )

    def get_videos(
        self,
        agent_id: Optional[str] = None,
        limit: int = 50,
        sort_by: str = "views",
    ) -> List[VideoMetrics]:
        """
        Get video metrics for all agent's videos.
        
        Args:
            agent_id: Agent identifier (uses client's if not provided)
            limit: Maximum results
            sort_by: Sort field (views, tips, revenue)
            
        Returns:
            List of VideoMetrics
        """
        aid = agent_id or self.client.config.agent_id
        if not aid:
            raise ValueError("agent_id must be provided")
        
        result = self.client._request(
            "GET",
            f"/api/agent/analytics/{aid}/videos",
            params={"limit": limit, "sort": sort_by},
        )
        
        videos = []
        for data in result.get("videos", []):
            video = VideoMetrics(
                video_id=data.get("video_id", ""),
                views=data.get("views", 0),
                tips_received=data.get("tips_received", 0),
                tips_amount=data.get("tips_amount", 0.0),
                avg_tip=data.get("avg_tip", 0.0),
                engagement_rate=data.get("engagement_rate", 0.0),
                revenue_share=data.get("revenue_share", 0.0),
            )
            videos.append(video)
        
        return videos

    def get_premium_analytics(
        self,
        agent_id: str,
        depth: str = "full",
    ) -> Dict[str, Any]:
        """
        Get deep agent analytics (premium endpoint).
        
        This is the /api/premium/analytics/<agent> endpoint
        mentioned in the RustChain documentation.
        
        Args:
            agent_id: Agent identifier
            depth: Analytics depth (basic, standard, full)
            
        Returns:
            Dict with comprehensive analytics
        """
        return self.client._request(
            "GET",
            f"/api/premium/analytics/{agent_id}",
            params={"depth": depth},
        )

    def get_comparison(
        self,
        agent_id: Optional[str] = None,
        benchmark: str = "category",
    ) -> Dict[str, Any]:
        """
        Get analytics comparison against benchmarks.
        
        Args:
            agent_id: Agent identifier (uses client's if not provided)
            benchmark: Benchmark type (category, global, top_100)
            
        Returns:
            Dict with comparison data
        """
        aid = agent_id or self.client.config.agent_id
        if not aid:
            raise ValueError("agent_id must be provided")
        
        return self.client._request(
            "GET",
            f"/api/agent/analytics/{aid}/comparison",
            params={"benchmark": benchmark},
        )

    def export_analytics(
        self,
        agent_id: Optional[str] = None,
        format: str = "json",
        period: AnalyticsPeriod = AnalyticsPeriod.MONTH,
    ) -> Dict[str, Any]:
        """
        Export analytics data.
        
        Args:
            agent_id: Agent identifier (uses client's if not provided)
            format: Export format (json, csv)
            period: Reporting period
            
        Returns:
            Dict with export data or download URL
        """
        aid = agent_id or self.client.config.agent_id
        if not aid:
            raise ValueError("agent_id must be provided")
        
        return self.client._request(
            "POST",
            f"/api/agent/analytics/{aid}/export",
            json_payload={
                "format": format,
                "period": period.value,
            },
        )

    def get_realtime_stats(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get real-time agent statistics.
        
        Args:
            agent_id: Agent identifier (uses client's if not provided)
            
        Returns:
            Dict with real-time stats
        """
        aid = agent_id or self.client.config.agent_id
        if not aid:
            raise ValueError("agent_id must be provided")
        
        return self.client._request("GET", f"/api/agent/analytics/{aid}/realtime")
