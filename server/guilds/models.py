"""Guild domain scaffolding for RIP-201."""
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class GuildMember:
    member_id: str
    role: str

@dataclass
class Guild:
    guild_id: str
    guild_type: str
    name: str
    owner_id: str
    members: List[GuildMember] = field(default_factory=list)
    policy_ref: Optional[str] = None
