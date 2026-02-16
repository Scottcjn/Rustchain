# RustChain API Reference - MZ Style 🦀⚡️

오픈소스 RustChain을 빌드하려는 갓생러들을 위한 지리는 API 가이드입니다.

## 1. Node Health Check (상태 확인 폼 미쳤음)
노드가 살아있는지 딸깍 확인해보세요.
- **Endpoint**: `GET /health`
- **Example**:
  ```bash
  curl https://50.28.86.131/health
  ```
- **Response**: `{"status": "ok", "version": "RIP-200"}`

## 2. Active Miners (광부들 정모 현황)
지금 누가 꿀빨고 있는지 실시간으로 확인 ㄱㄱ.
- **Endpoint**: `GET /api/miners`
- **Example**:
  ```bash
  curl https://50.28.86.131/api/miners
  ```

## 3. Blockchain Stats (데이터 지린다..)
- **Endpoint**: `GET /api/stats`
- **내용**: 현재 에포크, 총 공급량, 해시레이트 등 싹 다 나옵니다.

---
*이 문서는 Claw 에이전트가 RustChain 생태계 발전을 위해 직접 작성했습니다. (보안 예시 수정 완료 - Insecure flags removed) 지렸다...*
