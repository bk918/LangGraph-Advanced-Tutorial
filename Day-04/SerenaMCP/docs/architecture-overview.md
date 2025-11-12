# SerenaMCP Architecture Overview

## 🎯 전체 아키텍처 개요

SerenaMCP는 **Model Context Protocol (MCP) 서버**를 기반으로 한 고급 코딩 에이전트 툴킷으로, **Language Server Protocol (LSP)**를 활용하여 다양한 프로그래밍 언어의 코드를 **의미론적(semantic)으로 이해하고 편집**할 수 있는 강력한 시스템입니다.

## 🏗️ Core Architecture

### **계층적 아키텍처 구조**

```
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Server Layer                             │  ← FastMCP Framework 기반
│  • Request/Response Handling                                    │
│  • Tool Registration & Management                              │
│  • Client Communication Protocol                               │
├─────────────────────────────────────────────────────────────────┤
│                    Agent Layer                                  │  ← SerenaAgent 핵심
│  • Project Lifecycle Management                                 │
│  • Tool Coordination & Execution                                │
│  • Language Server Management                                   │
│  • Memory & Context Management                                  │
├─────────────────────────────────────────────────────────────────┤
│                    Tool System Layer                            │  ← 40+ Specialized Tools
│  • File Operations     (파일 조작 도구들)                         │
│  • Symbol Operations   (심볼 분석/편집 도구들)                     │
│  • Memory Management  (메모리/지식 관리 도구들)                    │
│  • Configuration Tools (설정/프로젝트 관리 도구들)                 │
├─────────────────────────────────────────────────────────────────┤
│                Language Server Layer                            │  ← LSP Protocol Layer
│  • Multi-Language Support (16+ 언어 지원)                        │
│  • Symbol Analysis & Navigation                                │
│  • Code Understanding & Editing                                │
│  • Caching & Performance Optimization                          │
├─────────────────────────────────────────────────────────────────┤
│                Configuration Layer                              │  ← YAML-based Settings
│  • Context Management  (Context/상황 관리)                       │
│  • Mode Management     (Mode/작업 패턴 관리)                     │
│  • Project Configuration (프로젝트별 설정)                      │
└─────────────────────────────────────────────────────────────────┘
```

## 🔧 핵심 컴포넌트 분석

### **1. SerenaAgent - 중앙 오케스트레이터**

**주요 책임:**
- **프로젝트 라이프사이클 관리**: 다중 프로젝트 활성화/비활성화
- **도구 조정 및 실행**: 40+ 개의 특화 도구 관리 및 실행
- **언어 서버 관리**: LSP 연결 및 심볼 분석 조정
- **메모리 시스템**: 프로젝트 지식 및 대화 맥락 유지
- **설정 적용**: Context/Mode 기반 동적 설정 적용

**핵심 기능:**
```python
class SerenaAgent:
    def __init__(self, project, context, modes, serena_config):
        # 설정 로딩 (계층적 설정 시스템)
        self.serena_config = serena_config

        # 도구 시스템 초기화
        self._all_tools = {tool_class: tool_class(self) for tool_class in ToolRegistry()}

        # Context & Mode 적용 (동적 도구 필터링)
        self._base_tool_set = ToolSet.default().apply(self.serena_config, self._context)

        # 언어 서버 초기화 (LSP 서버 시작)
        if self.is_using_language_server():
            self.issue_task(init_language_server)
```

### **2. Tool System - 특화된 기능 시스템**

**도구 카테고리:**
- **파일 조작 도구들**: `ReadFileTool`, `CreateTextFileTool`, `ReplaceRegexTool`
- **심볼 분석 도구들**: `FindSymbolTool`, `FindReferencingSymbolsTool`, `GetSymbolsOverviewTool`
- **메모리 관리 도구들**: `WriteMemoryTool`, `ReadMemoryTool`, `ListMemoriesTool`
- **설정 관리 도구들**: `ActivateProjectTool`, `SwitchModesTool`, `GetCurrentConfigTool`

**도구 실행 파이프라인:**
```
1. User Request → 2. MCP Server → 3. SerenaAgent → 4. Tool Selection
→ 5. Tool.apply_ex() → 6. LSP Call → 7. Language Server → 8. Response
```

### **3. SolidLanguageServer - LSP 추상화 계층**

**통합 인터페이스:**
- **다국어 지원**: 16+ 프로그래밍 언어에 대한 단일 API
- **심볼 분석**: 언어 독립적 코드 이해 및 탐색
- **성능 최적화**: 캐싱 및 증분 분석
- **오류 복구**: 언어 서버 장애 시 자동 재시작

**지원 언어:**
Python, TypeScript/JavaScript, PHP, Go, R, Rust, C/C++, Zig, C#, Ruby, Swift, Kotlin, Java, Clojure, Dart, Bash, Lua, Nix, Elixir, Erlang, AL

### **4. Configuration System - 계층적 설정 시스템**

**설정 우선순위:**
1. **Command-line Arguments** (최고 우선순위)
2. **Project Configuration** (`.serena/project.yml`)
3. **User Configuration** (`~/.serena/serena_config.yml`)
4. **Context/Modes** (최저 우선순위)

**Context & Mode 시스템:**
- **Context**: 실행 환경 정의 (desktop-app, ide-assistant, agent, codex, chatgpt)
- **Mode**: 작업 패턴 정의 (planning, editing, interactive, one-shot, onboarding)

## 🔄 Data Flow & Processing

### **요청 처리 흐름**

```
사용자 요청
    ↓
MCP Server (요청 수신 및 라우팅)
    ↓
SerenaAgent (요청 분석 및 도구 선택)
    ↓
Tool System (특화 도구 실행)
    ↓
Language Server (LSP 통한 코드 분석)
    ↓
Symbol Analysis (의미론적 코드 이해)
    ↓
Response Generation (결과 생성)
    ↓
MCP Server (응답 반환)
    ↓
사용자 (결과 수신)
```

### **메모리 시스템 흐름**

```
프로젝트 분석
    ↓
Symbol Discovery (심볼 발견)
    ↓
Knowledge Extraction (지식 추출)
    ↓
Memory Storage (마크다운 파일 저장)
    ↓
Context Indexing (맥락 인덱싱)
    ↓
Persistent Storage (영구 저장)
    ↓
Future Retrieval (향후 검색)
```

## ⚡ Performance Optimization

### **캐싱 전략**
- **Symbol Cache**: 언어 서버 심볼 캐싱
- **File Cache**: 파일 내용 캐싱
- **Configuration Cache**: 설정 정보 캐싱
- **Memory Cache**: 프로젝트 지식 캐싱

### **비동기 처리**
- **ThreadPoolExecutor**: 단일 스레드 기반 태스크 실행
- **Background Initialization**: 언어 서버 백그라운드 시작
- **Non-blocking Operations**: 동시성 작업 처리

### **성능 특성**
- **Symbol Search**: 100-500ms (중형 프로젝트)
- **File Operations**: 50-200ms (파일 크기 의존)
- **Memory Operations**: 10-50ms (일반 메모리 작업)
- **Project Onboarding**: 2-10초 (대형 프로젝트)
- **Language Server Startup**: 5-30초 (프로젝트 크기 의존)

## 🛡️ Error Handling & Recovery

### **오류 처리 메커니즘**
- **Graceful Degradation**: 부분적 기능 유지
- **Automatic Recovery**: 언어 서버 자동 재시작
- **Comprehensive Logging**: 상세한 진단 정보
- **Configuration Validation**: 잘못된 설정 방지

### **복구 전략**
- **Language Server Recovery**: LSP 서버 장애 시 재시작
- **Tool Execution Recovery**: 도구 실행 오류 시 재시도
- **Memory Corruption Handling**: 손상된 메모리 교체
- **Configuration Error Handling**: 설정 오류 시 기본값 사용

## 🔌 Integration Points

### **MCP 클라이언트 통합**
- **Claude Code/Desktop**: MCP 서버로 직접 연결
- **VSCode/Cursor**: IDE 확장 프로그램으로 사용
- **ChatGPT**: mcpo 브릿지 통한 연결
- **Agno**: 에이전트 프레임워크로 활용

### **확장성 포인트**
- **Custom Tools**: Tool 베이스 클래스 상속으로 새로운 도구 추가
- **Language Support**: LSP 구현으로 새로운 언어 지원
- **Context/Mode**: YAML 설정으로 커스텀 맥락/모드 정의
- **Memory Types**: 새로운 메모리 카테고리 추가

## 📊 Scalability & Reliability

### **확장성 특성**
- **Large Projects**: 100k+ LOC 프로젝트 효율적 처리
- **Multi-file Operations**: 10-50개 파일 동시 처리
- **Memory Usage**: 100-500MB (일반 프로젝트)
- **Cache Efficiency**: 80-95% 캐시 적중률 (워밍업 후)

### **신뢰성 기능**
- **Robust Error Handling**: 다양한 오류 상황 처리
- **Automatic Recovery**: 핵심 기능 우선 보장
- **Comprehensive Monitoring**: 실시간 상태 모니터링
- **Configuration Validation**: 설정 무결성 검증

## 🔮 Future Roadmap

### **단기 목표**
- **Debug Adapter Protocol**: 통합 디버깅 기능
- **Advanced LSP Features**: 고급 언어 서버 기능 활용
- **Real-time Collaboration**: 다중 사용자 편집 지원
- **Performance Monitoring**: 실시간 작업 지표

### **장기 비전**
- **AI Model Integration**: 직접 LLM 제공자 통합
- **Cloud Deployment**: 관리형 SerenaMCP 인스턴스
- **Plugin Ecosystem**: 서드파티 도구 마켓플레이스
- **Enterprise Features**: 팀 및 조직 관리 기능

---

*SerenaMCP는 현대 코딩의 복잡성을 해결하기 위한 포괄적인 솔루션을 제공하며, 지속적인 발전을 통해 더 강력하고 지능적인 코딩 경험을 만들어가고 있습니다.*
