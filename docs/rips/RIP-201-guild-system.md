# RIP-201: RTC Guild System (Scaffold)

## Guild Types

- Mining Guilds
- Bounty Guilds
- Agent-for-Hire Guilds

## Core Objects

- `Guild`
- `GuildMember`
- `GuildPolicy`
- `GuildTask`
- `GuildSettlement`

## Security/Abuse Controls

- role-based guild permissions
- anti-sybil constraints (age/attestation thresholds)
- treasury spend limits + approval quorum

## API (planned)

- `POST /guilds` create guild
- `GET /guilds/:id` guild details
- `POST /guilds/:id/members` invite member
- `POST /guilds/:id/tasks` create task
- `POST /guilds/:id/settlements` settle reward

## Rollout

1. Schema + route stubs
2. Permission + signature checks
3. Settlement integration
4. UI/Explorer integration
