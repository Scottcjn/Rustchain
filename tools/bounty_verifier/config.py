"""
Configuration management for bounty verifier.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class PayoutCoefficient:
    """Payout coefficient rules."""
    base_amount: float = 100.0
    follow_multiplier: float = 1.0
    star_multiplier: float = 0.05  # Per star
    max_stars_bonus: float = 0.5  # Max 50% bonus from stars
    vintage_cpu_bonus: float = 0.1  # 10% bonus for vintage CPU attestations
    node_operator_bonus: float = 0.15  # 15% bonus for node operators


@dataclass
class GitHubConfig:
    """GitHub API configuration."""
    token: str = ""
    owner: str = "Scottcjn"
    repo: str = "rustchain-bounties"
    target_user: str = "Scottcjn"
    rate_limit_buffer: int = 100  # Keep this many requests in reserve
    requests_per_hour: int = 1000  # GitHub API rate limit


@dataclass
class RustChainConfig:
    """RustChain node configuration."""
    enabled: bool = False
    node_url: str = "http://localhost:8099"
    wallet_check_timeout: int = 10
    min_balance: float = 0.0  # Minimum balance to pass wallet check


@dataclass
class UrlCheckConfig:
    """URL liveness check configuration."""
    enabled: bool = False
    timeout: int = 5
    require_https: bool = True
    allowed_domains: List[str] = field(default_factory=lambda: [
        "github.com",
        "twitter.com",
        "x.com",
        "discord.com",
    ])


@dataclass
class Config:
    """Main configuration for bounty verifier."""
    github: GitHubConfig = field(default_factory=GitHubConfig)
    rustchain: RustChainConfig = field(default_factory=RustChainConfig)
    url_check: UrlCheckConfig = field(default_factory=UrlCheckConfig)
    payout: PayoutCoefficient = field(default_factory=PayoutCoefficient)
    
    # Verification criteria
    require_follow: bool = True
    require_stars: bool = True
    min_star_count: int = 3
    require_wallet: bool = True
    require_url_liveness: bool = False
    check_duplicates: bool = True
    
    # Operational settings
    dry_run: bool = False
    post_comments: bool = True
    log_level: str = "INFO"
    
    # Paths
    config_path: Optional[Path] = None
    
    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """Load configuration from YAML file."""
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        
        return cls.from_dict(data, config_path=path)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], config_path: Optional[Path] = None) -> "Config":
        """Create Config from dictionary."""
        config = cls(config_path=config_path)
        
        if "github" in data:
            gh = data["github"]
            config.github = GitHubConfig(
                token=gh.get("token", os.getenv("GITHUB_TOKEN", "")),
                owner=gh.get("owner", "Scottcjn"),
                repo=gh.get("repo", "rustchain-bounties"),
                target_user=gh.get("target_user", "Scottcjn"),
                rate_limit_buffer=gh.get("rate_limit_buffer", 100),
                requests_per_hour=gh.get("requests_per_hour", 1000),
            )
        
        if "rustchain" in data:
            rc = data["rustchain"]
            config.rustchain = RustChainConfig(
                enabled=rc.get("enabled", False),
                node_url=rc.get("node_url", "http://localhost:8099"),
                wallet_check_timeout=rc.get("wallet_check_timeout", 10),
                min_balance=rc.get("min_balance", 0.0),
            )
        
        if "url_check" in data:
            uc = data["url_check"]
            config.url_check = UrlCheckConfig(
                enabled=uc.get("enabled", False),
                timeout=uc.get("timeout", 5),
                require_https=uc.get("require_https", True),
                allowed_domains=uc.get("allowed_domains", [
                    "github.com", "twitter.com", "x.com", "discord.com",
                ]),
            )
        
        if "payout" in data:
            po = data["payout"]
            config.payout = PayoutCoefficient(
                base_amount=po.get("base_amount", 100.0),
                follow_multiplier=po.get("follow_multiplier", 1.0),
                star_multiplier=po.get("star_multiplier", 0.05),
                max_stars_bonus=po.get("max_stars_bonus", 0.5),
                vintage_cpu_bonus=po.get("vintage_cpu_bonus", 0.1),
                node_operator_bonus=po.get("node_operator_bonus", 0.15),
            )
        
        # Verification criteria
        criteria = data.get("criteria", {})
        config.require_follow = criteria.get("require_follow", True)
        config.require_stars = criteria.get("require_stars", True)
        config.min_star_count = criteria.get("min_star_count", 3)
        config.require_wallet = criteria.get("require_wallet", True)
        config.require_url_liveness = criteria.get("require_url_liveness", False)
        config.check_duplicates = criteria.get("check_duplicates", True)
        
        # Operational settings
        config.dry_run = data.get("dry_run", False)
        config.post_comments = data.get("post_comments", True)
        config.log_level = data.get("log_level", "INFO")
        
        return config
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create Config from environment variables."""
        return cls(
            github=GitHubConfig(
                token=os.getenv("GITHUB_TOKEN", ""),
                owner=os.getenv("GITHUB_OWNER", "Scottcjn"),
                repo=os.getenv("GITHUB_REPO", "rustchain-bounties"),
                target_user=os.getenv("GITHUB_TARGET_USER", "Scottcjn"),
            ),
            rustchain=RustChainConfig(
                enabled=os.getenv("RUSTCHAIN_ENABLED", "false").lower() == "true",
                node_url=os.getenv("RUSTCHAIN_NODE_URL", "http://localhost:8099"),
            ),
            dry_run=os.getenv("DRY_RUN", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from file or environment."""
    if config_path:
        path = Path(config_path)
        if path.exists():
            return Config.from_yaml(path)
    
    # Try default locations
    default_paths = [
        Path(__file__).parent / "config.yaml",
        Path(__file__).parent / "config.yml",
        Path("/etc/rustchain/bounty_verifier.yaml"),
        Path.home() / ".rustchain" / "bounty_verifier.yaml",
    ]
    
    for path in default_paths:
        if path.exists():
            return Config.from_yaml(path)
    
    # Fall back to environment
    return Config.from_env()
