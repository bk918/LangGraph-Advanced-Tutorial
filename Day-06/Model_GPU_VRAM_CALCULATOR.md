# 웹사이트
1) https://huggingface.co/spaces/NyxKrage/LLM-Model-VRAM-Calculator
2) https://apxml.com/tools/vram-calculator

---

# GPU Memory 계산하는 방법

## 기능

- **파라미터 입력**: 모델의 파라미터 수를 십억 단위로 입력합니다.
- **양자화 선택**: 다양한 양자화 비트 옵션 중 선택합니다 (예: 2-bit, 4-bit, FP16, FP32 등).
- **GPU 메모리 계산**: 필요한 GPU 메모리 요구사항을 즉시 계산합니다.

---

## 수식 (Inference 전용)

Inference 시 필요한 총 VRAM은 다음과 같이 계산됩니다:

**Total VRAM (GB) = Model Weights + KV Cache + Activation Memory**

### 간단 버전 (근사치)

**Total VRAM (GB) = (Parameters_in_billions × Quantization Bits / 8) × 1.2**

여기서:

- **Parameters_in_billions**: 모델 파라미터 수 (십억 단위, 예: 10B 모델은 10)
- **Quantization Bits**: 파라미터 양자화에 사용되는 비트 수 (FP32=32, FP16=16, INT8=8, INT4=4)
- **8**: 바이트당 비트 수
- **1.2**: 오버헤드 계수 (Model Weights 100% + KV Cache ~15% + Activation ~5%)

---

### 상세 버전

각 구성 요소를 개별적으로 계산할 수 있습니다:

#### 1. Model Weights (모델 가중치)

**Model Weights (GB) = Parameters_in_billions × Quantization Bits / 8**

- 모델 파라미터의 실제 메모리 사용량입니다
- 예: 10B 모델, FP16 → 10 × 16 / 8 = **20 GB**

#### 2. KV Cache (Key-Value 캐시)

**KV Cache (GB) = 2 × 2 × n_layers × d_model × sequence_length × batch_size / 1,000,000,000**

여기서:
- **2 (첫 번째)**: Key와 Value 행렬
- **2 (두 번째)**: FP16 기준 파라미터당 바이트 수
- **n_layers**: 트랜스포머 레이어 수
- **d_model**: 모델 차원 (hidden_dim × n_heads)
- **sequence_length**: 처리할 최대 컨텍스트 길이
- **batch_size**: 동시 처리 시퀀스 수

**간단 근사치**: Model Weights의 약 **15-20%** (일반적인 컨텍스트 길이 기준)

#### 3. Activation Memory (활성화 메모리)

Inference 시 중간 계산을 위한 메모리입니다.

**Activation Memory (GB) ≈ Model Weights × 0.05**

- Inference 시에는 매우 작습니다 (학습 시와 달리 역전파가 없음)
- 일반적으로 Model Weights의 **약 5%**

### 요약

**Total VRAM (GB) = Model Weights × (1.0 + 0.15~0.20 + 0.05) ≈ Model Weights × 1.2~1.25**

**주의사항:**
- 위 수식은 **Inference 전용**입니다 (학습 시에는 Optimizer States와 Gradients가 추가로 필요)
- KV Cache는 **컨텍스트 길이에 비례**하여 증가합니다
- Batch size가 클수록 KV Cache와 Activation Memory도 증가합니다

---

## 예제

다음과 같은 모델의 inference 메모리를 계산해봅시다:

**모델 스펙:**
- 10B 파라미터
- 16-bit 양자화 (FP16)
- Sequence length: 2048 tokens (일반적인 값)
- Batch size: 1

### 간단 버전 계산

**Total VRAM (GB) = (10 × 16 / 8) × 1.2 = 20 × 1.2 = 24 GB**

### 상세 버전 계산

#### 1. Model Weights
**Model Weights = 10 × 16 / 8 = 20 GB**

#### 2. KV Cache (근사치)
**KV Cache ≈ 20 GB × 0.15 = 3 GB**
(일반적인 컨텍스트 길이 기준)

#### 3. Activation Memory
**Activation Memory ≈ 20 GB × 0.05 = 1 GB**

#### 총합
**Total VRAM = 20 + 3 + 1 = 24 GB**

**결론:** 이 모델을 inference하려면 최소 **24GB 이상의 VRAM**을 가진 GPU가 필요합니다.

### 양자화별 메모리 비교 (10B 모델 기준)

| 양자화 | Bits | Model Weights | Total VRAM (×1.2) |
|--------|------|---------------|-------------------|
| FP32   | 32   | 40 GB         | 48 GB             |
| FP16   | 16   | 20 GB         | 24 GB             |
| INT8   | 8    | 10 GB         | 12 GB             |
| INT4   | 4    | 5 GB          | 6 GB              |