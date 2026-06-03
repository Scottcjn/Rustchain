# RustChain 문서

> **RustChain**은 오래된 하드웨어에 더 높은 채굴 배수를 부여하는 Proof-of-Antiquity 블록체인입니다. 네트워크는 VM과 에뮬레이터가 보상을 받는 것을 막기 위해 6가지 하드웨어 지문 검사를 사용합니다.

## 빠른 링크

| 문서 | 설명 |
|------|------|
| **[개발자 튜토리얼](../RUSTCHAIN_DEVELOPER_TUTORIAL.md)** | 설정, 채굴, 트랜잭션, 예제를 포함한 종합 가이드 |
| [프로토콜 명세](../PROTOCOL.md) | 전체 RIP-200 합의 프로토콜 |
| [메커니즘 명세와 반증 행렬](../MECHANISM_SPEC_AND_FALSIFICATION_MATRIX.md) | 주장, 테스트, 실패 조건을 한 페이지에 매핑한 문서 |
| [API 레퍼런스](../API.md) | curl 예제가 포함된 전체 엔드포인트 설명 |
| [빌드 가이드](../BUILD.md) | 로컬 Python 및 Rust 빌드 명령 |
| [로컬 Devnet](../DEVNET.md) | 단일 노드 개발 서버 실행 방법 |
| [CLI 지갑 안내](../CLI.md) | 지갑 생성과 트랜잭션 시뮬레이션 |
| [용어집](../GLOSSARY.md) | 주요 용어와 정의 |
| [토크노믹스](../tokenomics_v1.md) | RTC 공급량과 분배 구조 |
| [FAQ와 문제 해결](../FAQ_TROUBLESHOOTING.md) | 일반적인 설정 및 실행 문제와 복구 절차 |
| [지갑 사용자 가이드](../WALLET_USER_GUIDE.md) | 지갑 기본 사용법, 잔액 조회, 안전한 작업 |
| [기여 가이드](../CONTRIBUTING.md) | 기여 절차, PR 체크리스트, 바운티 제출 참고사항 |
| [스마트 컨트랙트 개발자 가이드](../SMART_CONTRACT_DEVELOPER_GUIDE.md) | 컨트랙트 빠른 시작, 생명주기, 배포, 보안 체크리스트 |
| [보상 분석 대시보드](../REWARD_ANALYTICS_DASHBOARD.md) | RTC 보상 투명성을 위한 차트와 API |
| [크로스 노드 동기화 검증기](../CROSS_NODE_SYNC_VALIDATOR.md) | 다중 노드 일관성 검사와 불일치 보고 |
| [Discord 리더보드 봇](../DISCORD_LEADERBOARD_BOT.md) | 웹훅 봇 설정과 사용법 |
| [중국어 문서](../zh-CN/README.md) | 커뮤니티가 관리하는 중국어 문서 진입점 |
| [중국어 API 빠른 참조](../zh-CN/API.md) | 자주 쓰는 공개 API 질의를 위한 중국어 빠른 참조 |
| [일본어 빠른 시작](../ja/README.md) | 커뮤니티가 관리하는 일본어 빠른 시작 가이드 |

## 라이브 네트워크

- **기본 노드**: `https://rustchain.org`
- **익스플로러**: `https://rustchain.org/explorer/`
- **상태 확인**: `curl -fsS https://rustchain.org/health`
- **네트워크 상태 페이지**: `docs/network-status.html` (GitHub Pages로 호스팅할 수 있는 상태 대시보드)

## 현재 상태 확인

```bash
# 노드 상태 확인
curl -fsS https://rustchain.org/health | jq .

# 활성 채굴자 목록
curl -fsS https://rustchain.org/api/miners | jq .

# 현재 epoch 정보
curl -fsS https://rustchain.org/epoch | jq .
```

## 아키텍처 개요

```text
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Vintage Miner  │────▶│ Attestation Node │────▶│  Ergo Anchor    │
│  (G4/G5/SPARC)  │     │  (rustchain.org)  │     │ (Immutability)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                        │
        │ Hardware Fingerprint   │ Epoch Settlement
        │ (6 checks)             │ Hash
        ▼                        ▼
   ┌─────────┐              ┌─────────┐
   │ RTC     │              │ Ergo    │
   │ Rewards │              │ Chain   │
   └─────────┘              └─────────┘
```

## 시작하기

1. **하드웨어가 조건을 충족하는지 확인하기**: [CPU Antiquity Guide](../../CPU_ANTIQUITY_SYSTEM.md)를 참고하세요.
2. **채굴기 설치하기**: [INSTALL.md](../../INSTALL.md)를 참고하세요.
3. **지갑 등록하기**: RTC를 받기 위해 attestation을 제출하세요.

## 바운티

활성 바운티: [github.com/Scottcjn/rustchain-bounties](https://github.com/Scottcjn/rustchain-bounties)

---
*이 문서는 RustChain 커뮤니티가 관리합니다.*

