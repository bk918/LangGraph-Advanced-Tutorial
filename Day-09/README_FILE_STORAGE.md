# CompositeBackend 파일 저장 전략 가이드

## 📚 개요

이 프로젝트는 **CompositeBackend**를 사용하여 LangGraph State와 FileSystem을 동시에 활용합니다.
에이전트가 파일을 저장할 때 **경로에 따라 자동으로** 적절한 백엔드로 라우팅됩니다.

## 🏗️ 아키텍처

### Backend 구조

```python
CompositeBackend(
    default=StateBackend(runtime),           # 기본: LangGraph State (휘발성)
    routes={
        "/workspace/": FilesystemBackend()   # /workspace/* → 실제 디스크 (영구)
    }
)
```

### 동작 원리

1. **경로 기반 라우팅**: CompositeBackend가 파일 경로의 접두어를 확인
2. **자동 백엔드 선택**: 
   - `/workspace/`로 시작 → FilesystemBackend (디스크 저장)
   - 기타 경로 → StateBackend (메모리 저장)
3. **에이전트 제어**: System Prompt로 경로 선택 가이드 제공

## 📁 파일 저장 위치 규칙

### ✅ 영구 저장 (FilesystemBackend)

**경로**: `/workspace/`로 시작하는 모든 파일

**특징**:
- 실제 디스크에 저장
- 세션 종료 후에도 유지
- 외부 프로그램 접근 가능

**사용 사례**:
```python
# ✅ 좋은 예시
"/workspace/data.csv"                    # 데이터 파일
"/workspace/reports/analysis.md"         # 최종 보고서
"/workspace/output/results.json"         # 처리 결과
"/workspace/exports/user_data.xlsx"      # 내보내기 파일
```

**언제 사용하나요?**
- 사용자에게 전달할 최종 결과물
- 다음 세션에서도 필요한 데이터
- 외부 도구와 공유할 파일
- 장기 보관이 필요한 문서

### 🔄 임시 저장 (StateBackend)

**경로**: `/workspace/` 이외의 모든 경로

**특징**:
- LangGraph State (메모리)에 저장
- 세션 종료 시 자동 삭제
- 빠른 접근 속도

**사용 사례**:
```python
# ✅ 좋은 예시
"/temp/notes.txt"                        # 임시 메모
"/scratch/intermediate_data.json"        # 중간 처리 결과
"/cache/processed_items.csv"             # 캐시 데이터
"/debug/trace_log.txt"                   # 디버깅 로그
```

**언제 사용하나요?**
- 일시적인 작업 파일
- 중간 계산 결과
- 디버깅/테스트용 파일
- 한 세션 내에서만 필요한 데이터

## 🎯 에이전트 사용 가이드

### System Prompt 전략

에이전트가 올바른 경로를 선택하도록 **명확한 규칙**을 System Prompt에 제공합니다:

```python
system_prompt = """
## 파일 저장 위치 규칙

1. 영구 보관 필요 → `/workspace/` 사용
2. 임시 작업 → `/temp/`, `/scratch/` 등 사용
3. 불확실한 경우 → `/workspace/` 사용 (안전)
"""
```

### 실제 예시

#### 시나리오 1: 데이터 분석 작업

**사용자 요청**: "CSV 파일을 분석하고 결과를 저장해줘"

**에이전트 동작**:
```python
1. read_file("/input/data.csv")                  # 입력 데이터 읽기
2. write_file("/temp/processing.json", ...)      # 중간 결과 (임시)
3. write_file("/workspace/analysis_result.csv", ...) # 최종 결과 (영구)
```

#### 시나리오 2: 보고서 생성

**사용자 요청**: "분석 보고서를 작성해서 파일로 저장해줘"

**에이전트 동작**:
```python
1. write_file("/temp/draft.md", ...)             # 초안 작성 (임시)
2. edit_file("/temp/draft.md", ...)              # 수정
3. write_file("/workspace/reports/final_report.md", ...) # 최종본 (영구)
```

#### 시나리오 3: 디버깅

**사용자 요청**: "중간 처리 과정을 로그로 남겨줘"

**에이전트 동작**:
```python
1. write_file("/debug/step1.log", ...)           # 디버그 로그 (임시)
2. write_file("/debug/step2.log", ...)           # 추가 로그 (임시)
# 세션 종료 시 자동 삭제됨
```

## ⚙️ 구현 세부사항

### 1. PROJECT_ROOT 동적 설정

```python
import os
from pathlib import Path

# 환경 변수 우선, 없으면 현재 디렉토리 사용
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", os.getcwd()))
WORKSPACE_DIR = PROJECT_ROOT / "workspace"

# workspace 디렉토리 자동 생성
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
```

**장점**:
- 환경 변수로 배포 환경마다 다른 경로 지정 가능
- 개발 중에는 현재 디렉토리 자동 사용
- 디렉토리 없으면 자동 생성

### 2. BackendFactory 패턴

```python
def create_composite_backend(runtime):
    """런타임에 백엔드를 생성하는 팩토리 함수"""
    state_backend = StateBackend(runtime)  # ToolRuntime 필요
    filesystem_backend = FilesystemBackend(
        root_dir=WORKSPACE_DIR,
        virtual_mode=True  # 보안: 루트 밖으로 못 나감
    )
    
    return CompositeBackend(
        default=state_backend,
        routes={"/workspace/": filesystem_backend}
    )

# create_deep_agent에 팩토리 함수 전달
deep_agent = create_deep_agent(
    model,
    tools,
    backend=create_composite_backend,  # 함수 자체 전달 (호출 X)
    system_prompt=FILE_STORAGE_RULES
)
```

**중요**: `StateBackend`는 `ToolRuntime`을 생성자에서 받아야 하므로, 팩토리 패턴을 사용해야 합니다.

### 3. System Prompt 통합

```python
FILE_STORAGE_RULES = """
## 파일 저장 위치 규칙
...
"""

deep_agent = create_deep_agent(
    model,
    tools,
    backend=create_composite_backend,
    system_prompt=FILE_STORAGE_RULES  # 규칙을 프롬프트로 전달
)
```

## 🔍 동작 흐름 상세

### write_file 호출 시

```
에이전트: write_file("/workspace/data.csv", "...")
    ↓
FilesystemMiddleware: 도구 실행
    ↓
CompositeBackend._get_backend_and_key("/workspace/data.csv")
    ↓
경로 확인: "/workspace/"로 시작?
    ↓ YES
FilesystemBackend.write("/data.csv", "...")  # 접두어 제거
    ↓
실제 디스크에 {WORKSPACE_DIR}/data.csv 생성
    ↓
WriteResult(path="/workspace/data.csv", files_update=None)
```

### write_file (임시) 호출 시

```
에이전트: write_file("/temp/notes.txt", "...")
    ↓
FilesystemMiddleware: 도구 실행
    ↓
CompositeBackend._get_backend_and_key("/temp/notes.txt")
    ↓
경로 확인: "/workspace/"로 시작?
    ↓ NO
StateBackend.write("/temp/notes.txt", "...")  # 기본 백엔드
    ↓
runtime.state["files"]["/temp/notes.txt"] = {...}  # State 저장
    ↓
WriteResult(path="/temp/notes.txt", files_update={...})
```

## 🚀 사용 예제

### 기본 사용법

```python
from pathlib import Path
import os
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, FilesystemBackend

# 프로젝트 루트 설정
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", os.getcwd()))
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# 팩토리 함수
def create_composite_backend(runtime):
    return CompositeBackend(
        default=StateBackend(runtime),
        routes={
            "/workspace/": FilesystemBackend(root_dir=WORKSPACE_DIR, virtual_mode=True)
        }
    )

# 에이전트 생성
agent = create_deep_agent(
    model="gpt-4",
    tools=[],
    backend=create_composite_backend,
    system_prompt=FILE_STORAGE_RULES
)

# 실행
result = agent.invoke({"messages": [{"role": "user", "content": "데이터를 분석해줘"}]})
```

### 환경 변수 설정

```bash
# 프로덕션 환경
export PROJECT_ROOT=/app/data
python run.py

# 개발 환경 (현재 디렉토리 사용)
python run.py
```

## 💡 Best Practices

### 1. 명확한 의도 전달

**❌ 나쁜 예시**:
```python
# 에이전트가 어디에 저장할지 모름
"파일을 저장해줘"
```

**✅ 좋은 예시**:
```python
# 명확한 지시
"분석 결과를 /workspace/results.csv에 저장해줘"
```

### 2. 경로 구조화

```
/workspace/
├── data/           # 입력 데이터
├── outputs/        # 처리 결과
├── reports/        # 보고서
└── exports/        # 내보내기

/temp/
├── cache/          # 캐시
├── processing/     # 중간 처리
└── debug/          # 디버그 로그
```

### 3. 적절한 경로 선택

| 파일 용도 | 권장 경로 | 백엔드 |
|----------|----------|--------|
| 최종 결과 | `/workspace/output/` | FileSystem |
| 보고서 | `/workspace/reports/` | FileSystem |
| 내보내기 | `/workspace/exports/` | FileSystem |
| 중간 결과 | `/temp/processing/` | State |
| 캐시 | `/cache/` | State |
| 디버그 로그 | `/debug/` | State |

## 🐛 트러블슈팅

### Q1: 파일이 저장되지 않아요

**확인 사항**:
1. 경로가 `/`로 시작하는지 확인
2. WORKSPACE_DIR이 올바르게 생성되었는지 확인
3. 파일 시스템 권한 확인

```bash
ls -la /path/to/workspace
```

### Q2: 세션 종료 후 파일이 사라졌어요

**원인**: `/workspace/` 이외 경로는 State에만 저장됨

**해결**: 영구 보관이 필요하면 `/workspace/` 사용

### Q3: 에이전트가 잘못된 경로를 선택해요

**원인**: System Prompt가 명확하지 않음

**해결**: FILE_STORAGE_RULES를 더 구체적으로 작성

## 📚 참고 자료

- [DeepAgents 공식 문서](https://docs.langchain.com/oss/python/deepagents/overview)
- [LangGraph Backends](https://docs.langchain.com/oss/python/langgraph/concepts/backends)
- [CompositeBackend 구현](../Day-06/DeepAgent/src/deepagents/backends/composite.py)

## 📝 결론

CompositeBackend + System Prompt 조합은:

✅ **장점**:
- 에이전트가 자동으로 적절한 저장소 선택
- 영구/임시 파일 명확히 구분
- 유연한 경로 규칙 설정
- 자연어로 동작 제어

✅ **적합한 경우**:
- 일부 파일만 영구 저장이 필요할 때
- 중간 결과와 최종 결과를 분리하고 싶을 때
- 메모리 효율성이 중요할 때

이 패턴을 활용하면 에이전트가 **상황에 맞게 자동으로** 파일 저장 위치를 결정합니다! 🎯
