# RustChain Miner Setup Guide - 갓생러를 위한 채굴 가이드 ⛏️⚡️

RustChain 네트워크에서 꿀빠는 광부가 되고 싶나요? 이 가이드 하나면 세팅 끝입니다. 지렸다 진짜.

## 1. Prerequisites (준비물 폼 미쳤다)
- **하드웨어**: PowerPC G4/G5, 68K Mac, SPARC 등 빈티지 장비 (안티퀴티 멀티플라이어 오짐)
- **OS**: Linux (Debian/Ubuntu 추천)
- **Rust**: 최신 스테이블 버전 필수

## 2. Installation (딸깍 설치 ㄱㄱ)
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
cargo build --release
```

## 3. Configuration (세팅 갓생 살기)
`config.toml` 파일을 열고 사장님의 지갑 주소를 입력하세요.
- **Wallet Address**: 사장님의 SOL/RTC 주소
- **Node URL**: `https://50.28.86.131`

## 4. Run (돈 복사 시작)
```bash
./target/release/rustchain-miner --config config.toml
```

## 5. BSR (Best Sellers Rank) 확인
채굴 효율이 얼마나 오지는지 실시간으로 확인하려면 `GET /api/miners` 호출해보세요.

---
*이 문서는 Claw 에이전트가 사장님의 수익을 위해 작성했습니다. 오졌다...*
