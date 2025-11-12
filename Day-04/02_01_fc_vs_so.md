# Function Calling vs Structured Output - 실행 벤치마크

## 학습 목표

- FC와 SO의 실제 성능 차이 측정 (레이턴시, 토큰 비용)
- LLM 관점에서 FC와 SO의 본질적 동일성 이해
- SLM/불안정 모델 대응: SO Fallback 패턴 구현
- 실무 의사결정 가이드 자동 생성

## 핵심 인사이트

**LLM 입장에서는 결국 모든 것이 Structured Output입니다.**

Function Calling은 사용자 편의를 위한 Message wrapper일 뿐, 내부적으로는 JSON Schema를 기반으로 한 Structured Output으로 변환됩니다.

---

## 핵심 요약

### 1. FC와 SO는 본질적으로 동일 (LLM 관점)
- Function Calling도 내부적으로 JSON Schema 기반 SO로 변환
- 차이점은 **사용자 편의성과 에러 핸들링**

### 2. 실무 의사결정 기준
| 상황 | 선택 | 이유 |
|------|------|------|
| 멀티스텝 에이전트 | **FC** | Tool 실행 + 결과 재전달 필요 |
| 단순 데이터 추출 | **SO** | 검증만 필요, 더 단순 |
| SLM/불안정 모델 | **SO** | 규격 준수율 높음 |
| Fine-grained 검증 | **SO** | Pydantic 고급 기능 활용 |

### 3. 프로덕션 필수 패턴: SO Fallback
- FC 실패 시 자동으로 SO로 재시도
- SLM, 네트워크 불안정, 모델 업데이트 등에 robust

### 4. 성능 특성 (벤치마크 결과)
- **레이턴시**: 비슷하거나 FC가 약간 느림 (tool parsing 오버헤드)
- **토큰 비용**: FC가 약간 높음 (tool definitions 포함)
- **안정성**: SO가 더 robust (특히 SLM)
