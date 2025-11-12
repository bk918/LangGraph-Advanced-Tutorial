# SerenaMCP Tools Reference (serena/tools)

본 문서는 SerenaMCP의 도구 시스템과 `serena/tools` 하위 모든 도구를 한눈에 파악하고 안전하게 활용하기 위한 레퍼런스입니다. MCP(Models as Clients/Servers) 통합 관점에서 도구 노출, 메타데이터, 호출 방법을 설명하고, 각 도구별 정확한 시그니처/파라미터/반환/예외/주의사항/예시를 제공합니다.

- 버전 대상: 소스에 동봉된 현재 SerenaMCP
- 언어: Python 3.12+
- 범위: `serena/tools` 및 연계 컴포넌트(`tools_base.py`, `symbol_tools.py`, `file_tools.py`, `jetbrains_tools.py`, `cmd_tools.py`, `config_tools.py`, `memory_tools.py`, `workflow_tools.py`, `jetbrains_plugin_client.py`)

---

## 목차

- [개요](#개요)
- [퀵 레퍼런스 표](#퀵-레퍼런스-표)
- [코어 아키텍처](#코어-아키텍처)
- [카테고리별 상세 문서](#카테고리별-상세-문서)
  - [파일/FS 도구 (file_tools)](#파일fs-도구-file_tools)
  - [심볼/LSP 도구 (symbol_tools)](#심볼lsp-도구-symbol_tools)
  - [JetBrains 연동 도구 (jetbrains_tools)](#jetbrains-연동-도구-jetbrains_tools)
  - [명령 실행 도구 (cmd_tools)](#명령-실행-도구-cmd_tools)
  - [구성/모드 도구 (config_tools)](#구성모드-도구-config_tools)
  - [메모리 도구 (memory_tools)](#메모리-도구-memory_tools)
  - [워크플로우 도구 (workflow_tools)](#워크플로우-도구-workflow_tools)
- [LSP vs JetBrains 선택 가이드](#lsp-vs-jetbrains-선택-가이드)
- [에러 처리와 안전성](#에러-처리와-안전성)
- [예시 섹션 (MCP 호출 파라미터)](#예시-섹션-mcp-호출-파라미터)
- [부록](#부록)

---

## 개요

SerenaMCP 도구 시스템은 MCP 서버를 통해 에이전트가 코드베이스에 안전하고 정밀하게 접근/분석/편집할 수 있도록 합니다.

- MCP 통합: 각 도구는 `apply()` 메서드의 시그니처/독스트링/타입 힌트를 기반으로 MCP 툴 메타데이터로 노출됩니다.
- 호출 모델: 클라이언트는 툴 이름(기본적으로 클래스명에서 `Tool`을 제거하고 snake_case로 변환)과 `apply()` 파라미터 JSON을 전송합니다.
- 안전성:
  - 편집성 도구는 마커(`ToolMarkerCanEdit`/`ToolMarkerSymbolicEdit`)로 구분되며 read-only 모드에서는 비활성화 가능합니다.
  - 일부 도구는 선택적(`ToolMarkerOptional`)로 분류되어 기본 비활성화 상태입니다.
  - 위험한 셸 명령(예: `rm -rf /`)은 금지됩니다.
  - `_limit_length(max_answer_chars)`로 과도한 출력은 자동 제한됩니다.

---

## 퀵 레퍼런스 표

| Tool (클래스) | Category | can_edit | optional | requires_active_project | notes |
| --- | --- | --- | --- | --- | --- |
| ReadFileTool | file | no | no | yes | 라인 범위/캐시 지원 |
| CreateTextFileTool | file | yes | no | yes | 새 파일/덮어쓰기, 프로젝트 밖 생성 금지 |
| ListDirTool | file | no | no | yes | 경로 없으면 JSON error 리턴 |
| FindFileTool | file | no | no | yes | `fnmatch` 기반 마스크 검색 |
| ReplaceRegexTool | file | yes | no | yes | DOTALL/MULTILINE, 0/다중 매치 에러 문자열 |
| DeleteLinesTool | file | yes | yes | yes | 동일 범위 사전 `read_file` 필요 |
| ReplaceLinesTool | file | yes | yes | yes | delete→insert 조합, 최종 개행 보장 |
| InsertAtLineTool | file | yes | yes | yes | 최종 개행 보장 |
| SearchForPatternTool | file | no | no | yes | 경로 없으면 FileNotFoundError |
| RestartLanguageServerTool | symbol | no | yes | yes | 언어 서버 재시작 |
| GetSymbolsOverviewTool | symbol | no (symbolic read) | no | yes | 파일 경로 검증, JSON 배열 |
| FindSymbolTool | symbol | no (symbolic read) | no | yes | name_path 규칙, kinds 필터 |
| FindReferencingSymbolsTool | symbol | no (symbolic read) | no | yes | 참조 스니펫 포함 |
| ReplaceSymbolBodyTool | symbol | yes (symbolic) | no | yes | 심볼 전체 정의 교체 |
| InsertAfterSymbolTool | symbol | yes (symbolic) | no | yes | 심볼 정의 이후 삽입 |
| InsertBeforeSymbolTool | symbol | yes (symbolic) | no | yes | 심볼 정의 이전 삽입 |
| JetBrainsFindSymbolTool | jetbrains | no (symbolic read) | yes | yes | IDE 서비스 필요 |
| JetBrainsFindReferencingSymbolsTool | jetbrains | no (symbolic read) | yes | yes | IDE 서비스 필요 |
| JetBrainsGetSymbolsOverviewTool | jetbrains | no (symbolic read) | yes | yes | IDE 서비스 필요 |
| ExecuteShellCommandTool | cmd | yes | no | yes | 안전한 셸 실행, JSON 결과 |
| ActivateProjectTool | config | no | no | no | 신규/기존 활성화 문자열 |
| RemoveProjectTool | config | no | yes | no | 구성에서 프로젝트 제거 |
| SwitchModesTool | config | no | yes | yes | 모드 프롬프트/활성 도구 리턴 |
| GetCurrentConfigTool | config | no | no | yes | 전체 구성 개요 문자열 |
| WriteMemoryTool | memory | no | no | yes | 길이 제한 검증 |
| ReadMemoryTool | memory | no | no | yes | 파일 전체 내용 |
| ListMemoriesTool | memory | no | no | yes | JSON 배열 문자열 |
| DeleteMemoryTool | memory | no | no | yes | 삭제 확인 메시지 |
| CheckOnboardingPerformedTool | workflow | no | no | yes | 메모리 유무 검사 |
| OnboardingTool | workflow | no | no | yes | 플랫폼 기반 온보딩 프롬프트 |
| ThinkAboutCollectedInformationTool | workflow | no | no | yes | 수집정보 충분성 점검 프롬프트 |
| ThinkAboutTaskAdherenceTool | workflow | no | no | yes | 목표 적합성 점검 프롬프트 |
| ThinkAboutWhetherYouAreDoneTool | workflow | no | no | yes | 종료 판단 프롬프트 |
| SummarizeChangesTool | workflow | no | yes | yes | 변경 요약 프롬프트 |
| PrepareForNewConversationTool | workflow | no | no | yes | 새 대화 준비 프롬프트 |
| InitialInstructionsTool | workflow | no | yes | no | 초기 지침, 프로젝트 불필요 |

> 이름 규칙: MCP 툴 이름은 기본적으로 클래스명에서 `Tool`을 제거 후 snake_case로 변환됩니다. 예: `ReadFileTool` → `read_file`.

---

## 코어 아키텍처

- 클래스
  - `Tool`: 모든 도구의 베이스. `get_name_from_cls()`, `get_apply_fn_metadata_from_cls()`, `apply_ex()` 등 제공.
  - `Component`: 에이전트 컴포넌트 접근(프로젝트, 프롬프트 팩토리, 메모리 매니저, 코드 에디터, 심볼 리트리버, lines_read).
  - `ToolRegistry`: `serena.tools` 네임스페이스의 `Tool` 서브클래스를 자동 검색/등록. 선택적 도구 구분 관리.
  - `EditedFileContext`: 파일 편집 컨텍스트 매니저. 정상 종료 시 업데이트 내용을 디스크에 기록.
- 상수
  - `SUCCESS_RESULT = "OK"`
- 마커(도구 속성)
  - `ToolMarkerCanEdit`: 파일 편집 가능
  - `ToolMarkerSymbolicRead`: 심볼 읽기 작업
  - `ToolMarkerSymbolicEdit`: 심볼 편집 작업(편집 가능)
  - `ToolMarkerOptional`: 선택적(기본 비활성)
  - `ToolMarkerDoesNotRequireActiveProject`: 활성 프로젝트 불필요
- `apply_ex()` 실행 플로우(요약)
  1. 활성화 여부 확인(선택적 도구/비활성 시 에러 문자열로 안내)
  2. 활성 프로젝트 요구 도구의 경우, 프로젝트 유효성 검증
  3. 언어 서버 모드에서 서버 미기동 시 자동 시작
  4. 실제 `apply()` 호출; `SolidLSPException` 발생 시 종료 판단 → 재기동 후 1회 재시도
  5. 도구 사용 기록(활성 시) 및 LSP 캐시 저장 시도
  6. 타임아웃: `tool_timeout` 내에서 실행
- 출력 길이 제한
  - `_limit_length(result, max_answer_chars)`: 결과 길이가 제한 초과 시 메시지로 교체
- LinesRead 사전조건
  - `DeleteLinesTool`, `ReplaceLinesTool` 등은 동일 라인 범위를 `ReadFileTool`로 먼저 읽어야 합니다(정확성 보장).
- 이름 규칙
  - `get_name_from_cls()`: 클래스명에서 `Tool` 제거 후 snake_case로 변환 → MCP 툴 이름으로 사용

---

## 카테고리별 상세 문서

### 파일/FS 도구 (file_tools)

#### ReadFileTool

- 마커: (none)
- 시그니처:

```python
def apply(self, relative_path: str, start_line: int = 0, end_line: int | None = None, max_answer_chars: int = -1) -> str
```

- 파라미터
  - `relative_path`: 프로젝트 루트 기준 파일 경로
  - `start_line`: 0-based 시작 라인
  - `end_line`: 포함(inclusive) 0-based 종료 라인, `None`이면 파일 끝까지
  - `max_answer_chars`: 출력 길이 제한
- 동작/반환: 파일 전체 또는 지정 범위를 읽어 텍스트 반환. 범위 읽기 시 `lines_read`에 기록.
- 예외/에러: 경로 유효성 검증 실패 시 예외. 출력 길이 제한 초과 시 제한 메시지로 대체.
- 팁: 심볼 기반 도구가 더 적합한 경우 이를 우선 고려. 범위 편집 전에는 동일 범위로 미리 읽어 둘 것.

예시(JSON):

```json
{
  "tool": "read_file",
  "arguments": {
    "relative_path": "src/app.py",
    "start_line": 0,
    "end_line": 120
  }
}
```

---

#### CreateTextFileTool

- 마커: `ToolMarkerCanEdit`
- 시그니처:

```python
def apply(self, relative_path: str, content: str) -> str
```

- 파라미터: `relative_path`, `content`(UTF-8)
- 동작/반환: 새 파일 생성 또는 덮어쓰기, 상위 디렉토리 자동 생성. 결과를 JSON 문자열로 반환(예: `"File created: ..."`).
- 예외/에러: 프로젝트 밖 경로 생성 금지(Assertion). 기존 파일 덮어쓰기 시 경로 유효성 검증.
- 팁: 생성/덮어쓰기 의도를 사전에 분명히 하고 경로를 반드시 프로젝트 내로 한정.

예시(JSON):

```json
{
  "tool": "create_text_file",
  "arguments": {
    "relative_path": "docs/AGENTS.md",
    "content": "# Title\n..."
  }
}
```

---

#### ListDirTool

- 마커: (none)
- 시그니처:

```python
def apply(self, relative_path: str, recursive: bool, skip_ignored_files: bool = False, max_answer_chars: int = -1) -> str
```

- 동작/반환: 디렉토리 존재 시 스캔 결과 `{"dirs": [...], "files": [...]}` JSON 문자열 반환.
- 에러 처리: 디렉토리 미존재 시 JSON 에러 객체 반환:
  - `{"error": "Directory not found: ...", "project_root": "...", "hint": "..."}`

예시(JSON):

```json
{
  "tool": "list_dir",
  "arguments": {
    "relative_path": ".",
    "recursive": true,
    "skip_ignored_files": true
  }
}
```

---

#### FindFileTool

- 마커: (none)
- 시그니처:

```python
def apply(self, file_mask: str, relative_path: str) -> str
```

- 동작/반환: `fnmatch` 기반 마스크로 파일 필터링, `{"files": [...]}` JSON 반환.
- 팁: 프로젝트 루트 기준 하위 탐색, `relative_path`로 스코프 축소 권장.

예시(JSON):

```json
{
  "tool": "find_file",
  "arguments": {
    "file_mask": "*.py",
    "relative_path": "src"
  }
}
```

---

#### ReplaceRegexTool

- 마커: `ToolMarkerCanEdit`
- 시그니처:

```python
def apply(self, relative_path: str, regex: str, repl: str, allow_multiple_occurrences: bool = False) -> str
```

- 동작: `re.subn`(DOTALL|MULTILINE)로 교체. 와일드카드/비탐욕 사용 권장.
- 반환:
  - 성공 시: `"OK"`
  - 실패/경고:
    - 매치 0회: `"Error: No matches found for regex '...' in file '...'.'"`
    - 다중 매치(허용 안 함): `"Error: Regex '...' matches N occurrences ..."`
- 팁: 여러 곳 교체 필요 시 `allow_multiple_occurrences=True`. 큰 블록 치환 시 `begin...end` 패턴 비탐욕 사용.

예시(JSON):

```json
{
  "tool": "replace_regex",
  "arguments": {
    "relative_path": "src/app.py",
    "regex": "def old_func\\(.*?\\):[\\s\\S]*?return 0",
    "repl": "def old_func():\n    return 1",
    "allow_multiple_occurrences": false
  }
}
```

---

#### DeleteLinesTool

- 마커: `ToolMarkerCanEdit`, `ToolMarkerOptional`
- 시그니처:

```python
def apply(self, relative_path: str, start_line: int, end_line: int) -> str
```

- 사전조건: 동일 라인 범위를 `ReadFileTool`로 먼저 읽어야 함. 불이행 시 에러:
  - `"Error: Must call 'read_file' first to read exactly the affected lines."`
- 동작/반환: 코드 에디터로 라인 삭제, `"OK"` 반환.

예시(JSON):

```json
{
  "tool": "delete_lines",
  "arguments": { "relative_path": "src/app.py", "start_line": 10, "end_line": 30 }
}
```

---

#### ReplaceLinesTool

- 마커: `ToolMarkerCanEdit`, `ToolMarkerOptional`
- 시그니처:

```python
def apply(self, relative_path: str, start_line: int, end_line: int, content: str) -> str
```

- 동작: `DeleteLinesTool` → `InsertAtLineTool` 조합. `content`는 최종 개행 보장(필요 시 추가).
- 반환: `"OK"`
- 팁: 동일 라인 범위를 먼저 `ReadFileTool`로 읽어 정확성 확보.

예시(JSON):

```json
{
  "tool": "replace_lines",
  "arguments": {
    "relative_path": "src/app.py",
    "start_line": 50,
    "end_line": 60,
    "content": "print('replaced')\n"
  }
}
```

---

#### InsertAtLineTool

- 마커: `ToolMarkerCanEdit`, `ToolMarkerOptional`
- 시그니처:

```python
def apply(self, relative_path: str, line: int, content: str) -> str
```

- 동작: 지정 라인에 내용 삽입(기존 라인 아래로 밀림). `content` 최종 개행 보장.
- 반환: `"OK"`

예시(JSON):

```json
{
  "tool": "insert_at_line",
  "arguments": { "relative_path": "src/app.py", "line": 0, "content": "# header\n" }
}
```

---

#### SearchForPatternTool

- 마커: (none)
- 시그니처:

```python
def apply(self, substring_pattern: str, context_lines_before: int = 0, context_lines_after: int = 0, paths_include_glob: str = "", paths_exclude_glob: str = "", relative_path: str = "", restrict_search_to_code_files: bool = False, max_answer_chars: int = -1) -> str
```

- 동작:
  - `relative_path` 존재 필수(없으면 `FileNotFoundError`).
  - `restrict_search_to_code_files=True`면 소스 코드 심볼 분석에 사용되는 파일만 검색.
  - 결과는 `file_path -> [matched_blocks_as_string...]` JSON 맵.
- 팁: 비탐욕 정규식 사용 권장. 너무 넓은 경로/패턴은 결과가 길어져 `_limit_length`에 걸릴 수 있음.

예시(JSON):

```json
{
  "tool": "search_for_pattern",
  "arguments": {
    "substring_pattern": "class\\s+MyService[\\s\\S]*?def\\s+run",
    "context_lines_before": 2,
    "context_lines_after": 2,
    "relative_path": "src",
    "restrict_search_to_code_files": true
  }
}
```

---

### 심볼/LSP 도구 (symbol_tools)

#### RestartLanguageServerTool

- 마커: `ToolMarkerOptional`
- 시그니처:

```python
def apply(self) -> str
```

- 동작: 언어 서버 완전 재시작 및 심볼 캐시 초기화.
- 반환: `"OK"`
- 주의: 필요 시에만 사용(진행 중 작업에 영향).

예시(JSON):

```json
{ "tool": "restart_language_server", "arguments": {} }
```

---

#### GetSymbolsOverviewTool

- 마커: `ToolMarkerSymbolicRead`
- 시그니처:

```python
def apply(self, relative_path: str, max_answer_chars: int = -1) -> str
```

- 동작: 파일의 최상위 심볼 개요 조회. 파일 존재 확인, 디렉토리면 `ValueError`.
- 반환: `[{...symbol dataclass as dict...}, ...]` JSON 배열.

예시(JSON):

```json
{
  "tool": "get_symbols_overview",
  "arguments": { "relative_path": "src/app.py" }
}
```

---

#### FindSymbolTool

- 마커: `ToolMarkerSymbolicRead`
- 시그니처:

```python
def apply(self, name_path: str, depth: int = 0, relative_path: str = "", include_body: bool = False, include_kinds: list[int] = [], exclude_kinds: list[int] = [], substring_matching: bool = False, max_answer_chars: int = -1) -> str
```

- name_path 매칭 규칙(요약):
  - 단순 이름: 조상 제약 없음
  - 상대 경로(`a/b`): 동일 조상 시퀀스를 가진 심볼
  - 절대 경로(`/a/b`): 최상위부터 정확히 일치
  - 마지막 세그먼트는 정확 일치 또는 `substring_matching=True`일 때 부분 문자열 일치
- kinds 필터: `solidlsp.ls_types.SymbolKind` 정수값 목록 포함/제외
- 반환: 심볼 딕셔너리 리스트(JSON), 위치/종류/선택적 body 포함(위생 처리된 필드)

예시(JSON):

```json
{
  "tool": "find_symbol",
  "arguments": {
    "name_path": "Service/run",
    "depth": 1,
    "relative_path": "src",
    "include_body": false,
    "include_kinds": [5, 6],
    "substring_matching": false
  }
}
```

---

#### FindReferencingSymbolsTool

- 마커: `ToolMarkerSymbolicRead`
- 시그니처:

```python
def apply(self, name_path: str, relative_path: str, include_kinds: list[int] = [], exclude_kinds: list[int] = [], max_answer_chars: int = -1) -> str
```

- 동작: 지정 심볼을 참조하는 심볼 조회. `include_body=False` 고정. 참조 라인 주변 스니펫을 `content_around_reference`로 포함.
- 반환: JSON 리스트

예시(JSON):

```json
{
  "tool": "find_referencing_symbols",
  "arguments": {
    "name_path": "Service/run",
    "relative_path": "src/app.py"
  }
}
```

---

#### ReplaceSymbolBodyTool

- 마커: `ToolMarkerSymbolicEdit`(편집 가능)
- 시그니처:

```python
def apply(self, name_path: str, relative_path: str, body: str) -> str
```

- 동작: 심볼 전체 정의(서명 포함, 주석/임포트 제외)를 새 `body`로 교체.
- 반환: `"OK"`
- 팁: 사전에 `find_symbol`로 정확한 심볼 경계를 파악 후 호출.

예시(JSON):

```json
{
  "tool": "replace_symbol_body",
  "arguments": {
    "name_path": "Service/run",
    "relative_path": "src/app.py",
    "body": "def run(self):\n    return True\n"
  }
}
```

---

#### InsertAfterSymbolTool

- 마커: `ToolMarkerSymbolicEdit`
- 시그니처:

```python
def apply(self, name_path: str, relative_path: str, body: str) -> str
```

- 동작: 심볼 정의 끝 이후에 새 코드 삽입.
- 반환: `"OK"`

예시(JSON):

```json
{
  "tool": "insert_after_symbol",
  "arguments": {
    "name_path": "Service",
    "relative_path": "src/app.py",
    "body": "def new_method(self):\n    pass\n"
  }
}
```

---

#### InsertBeforeSymbolTool

- 마커: `ToolMarkerSymbolicEdit`
- 시그니처:

```python
def apply(self, name_path: str, relative_path: str, body: str) -> str
```

- 동작: 심볼 정의 시작 이전에 새 코드 삽입(예: import 앞 삽입).
- 반환: `"OK"`

예시(JSON):

```json
{
  "tool": "insert_before_symbol",
  "arguments": {
    "name_path": "Service",
    "relative_path": "src/app.py",
    "body": "import logging\n"
  }
}
```

---

### JetBrains 연동 도구 (jetbrains_tools)

사전 조건:

- JetBrains IDE(예: IntelliJ, PyCharm)에 Serena 플러그인 서비스가 실행 중이어야 합니다.
- 포트 스캔: `BASE_PORT = 0x5EA2`부터 +20 범위를 검사해 프로젝트 경로와 매칭되는 서비스 탐색.
- 서비스 미발견 시: `ServerNotFoundError` 발생.

REST 통신/예외:

- HTTP 요청 실패/타임아웃/HTTP 에러 시 각각 `ConnectionError`/`ConnectionError`/`APIError` 발생.
- 플러그인 응답의 camelCase 키는 snake_case로 변환되어 전달됩니다.

공통 반환:

- IDE 응답 딕셔너리를 JSON 문자열로 래핑하여 반환하며 `_limit_length` 적용.

#### JetBrainsFindSymbolTool

- 마커: `ToolMarkerSymbolicRead`, `ToolMarkerOptional`
- 시그니처:

```python
def apply(self, name_path: str, depth: int = 0, relative_path: str | None = None, include_body: bool = False, max_answer_chars: int = -1) -> str
```

#### JetBrainsFindReferencingSymbolsTool

- 마커: `ToolMarkerSymbolicRead`, `ToolMarkerOptional`
- 시그니처:

```python
def apply(self, name_path: str, relative_path: str, max_answer_chars: int = -1) -> str
```

#### JetBrainsGetSymbolsOverviewTool

- 마커: `ToolMarkerSymbolicRead`, `ToolMarkerOptional`
- 시그니처:

```python
def apply(self, relative_path: str, max_answer_chars: int = -1) -> str
```

예시(JSON):

```json
{
  "tool": "jet_brains_find_symbol",
  "arguments": {
    "name_path": "Service/run",
    "depth": 1,
    "relative_path": "src/app.py",
    "include_body": false
  }
}
```

---

### 명령 실행 도구 (cmd_tools)

#### ExecuteShellCommandTool

- 마커: `ToolMarkerCanEdit`
- 시그니처:

```python
def apply(self, command: str, cwd: str | None = None, capture_stderr: bool = True, max_answer_chars: int = -1) -> str
```

- 동작:
  - `cwd=None`이면 프로젝트 루트에서 실행.
  - `cwd`가 상대 경로면 프로젝트 루트 기준으로 조합 후 디렉토리 검증(아닐 경우 `FileNotFoundError`).
  - `execute_shell_command()`를 호출해 안전하게 실행. 결과를 `.json()`으로 직렬화한 문자열 반환.
- 반환: 명령의 stdout, 선택적 stderr, 종료 코드 등을 담은 JSON 문자열.
- 주의: 위험 명령(시스템 파괴적)은 금지.

예시(JSON):

```json
{
  "tool": "execute_shell_command",
  "arguments": { "command": "pytest -q", "cwd": "project", "capture_stderr": true }
}
```

---

### 구성/모드 도구 (config_tools)

#### ActivateProjectTool

- 마커: `ToolMarkerDoesNotRequireActiveProject`
- 시그니처:

```python
def apply(self, project: str) -> str
```

- 동작/반환:
  - 경로/이름으로 프로젝트 활성화.
  - 신규 생성 시 생성/활성화 메시지 + 경로/언어/설정 파일 위치 안내.
  - 기존 프로젝트 활성화 시 활성화 메시지.
  - 초기 프롬프트, 사용 가능한 메모리 목록(JSON), 활성 도구 목록(JSON)을 문자열로 포함.

예시(JSON):

```json
{
  "tool": "activate_project",
  "arguments": { "project": "/abs/path/to/repo" }
}
```

---

#### RemoveProjectTool

- 마커: `ToolMarkerDoesNotRequireActiveProject`, `ToolMarkerOptional`
- 시그니처:

```python
def apply(self, project_name: str) -> str
```

- 동작/반환: 구성에서 지정 프로젝트 제거 후 확인 메시지.

예시(JSON):

```json
{
  "tool": "remove_project",
  "arguments": { "project_name": "my_project" }
}
```

---

#### SwitchModesTool

- 마커: `ToolMarkerOptional`
- 시그니처:

```python
def apply(self, modes: list[str]) -> str
```

- 동작/반환: 지정 모드 활성화, 각 모드 프롬프트 출력, 현재 활성 도구 나열.

예시(JSON):

```json
{
  "tool": "switch_modes",
  "arguments": { "modes": ["editing", "interactive"] }
}
```

---

#### GetCurrentConfigTool

- 마커: (none)
- 시그니처:

```python
def apply(self) -> str
```

- 동작/반환: 활성 프로젝트/사용 가능한 프로젝트/활성화된 도구/컨텍스트/모드 등 전체 구성 상태 개요 문자열.

예시(JSON):

```json
{ "tool": "get_current_config", "arguments": {} }
```

---

### 메모리 도구 (memory_tools)

#### WriteMemoryTool

- 마커: (none)
- 시그니처:

```python
def apply(self, memory_name: str, content: str, max_answer_chars: int = -1) -> str
```

- 동작: 프로젝트 메모리 생성/덮어쓰기. `max_answer_chars`보다 길면 `ValueError`.
- 반환: 저장 성공 메시지.

예시(JSON):

```json
{
  "tool": "write_memory",
  "arguments": {
    "memory_name": "onboarding-summary",
    "content": "### 프로젝트 개요 ...",
    "max_answer_chars": 20000
  }
}
```

---

#### ReadMemoryTool

- 마커: (none)
- 시그니처:

```python
def apply(self, memory_file_name: str, max_answer_chars: int = -1) -> str
```

- 동작/반환: 메모리 파일 전체 텍스트.

예시(JSON):

```json
{ "tool": "read_memory", "arguments": { "memory_file_name": "onboarding-summary.md" } }
```

---

#### ListMemoriesTool

- 마커: (none)
- 시그니처:

```python
def apply(self) -> str
```

- 동작/반환: 메모리 파일 이름 배열(JSON 문자열).

예시(JSON):

```json
{ "tool": "list_memories", "arguments": {} }
```

---

#### DeleteMemoryTool

- 마커: (none)
- 시그니처:

```python
def apply(self, memory_file_name: str) -> str
```

- 동작/반환: 삭제 확인 메시지.

예시(JSON):

```json
{ "tool": "delete_memory", "arguments": { "memory_file_name": "old.md" } }
```

---

### 워크플로우 도구 (workflow_tools)

#### CheckOnboardingPerformedTool

- 마커: (none)
- 시그니처:

```python
def apply(self) -> str
```

- 동작/반환: 메모리 존재 여부 검사 후 안내 문자열(온보딩 필요 여부/메모리 리스트).

예시(JSON):

```json
{ "tool": "check_onboarding_performed", "arguments": {} }
```

---

#### OnboardingTool

- 마커: (none)
- 시그니처:

```python
def apply(self) -> str
```

- 동작/반환: 플랫폼(OS) 기반 온보딩 프롬프트(지침) 문자열.

---

#### ThinkAboutCollectedInformationTool / ThinkAboutTaskAdherenceTool / ThinkAboutWhetherYouAreDoneTool

- 마커: (none)
- 시그니처(공통):

```python
def apply(self) -> str
```

- 동작/반환: 각각 수집정보 충분성/작업 목표 적합성/완료 판단을 촉진하는 지침 문자열.

---

#### SummarizeChangesTool

- 마커: `ToolMarkerOptional`
- 시그니처:

```python
def apply(self) -> str
```

- 동작/반환: 변경사항 요약을 위한 지침 문자열.

---

#### PrepareForNewConversationTool

- 마커: (none)
- 시그니처:

```python
def apply(self) -> str
```

- 동작/반환: 새 대화 준비 지침(컨텍스트 이어가기).

---

#### InitialInstructionsTool

- 마커: `ToolMarkerDoesNotRequireActiveProject`, `ToolMarkerOptional`
- 시그니처:

```python
def apply(self) -> str
```

- 동작/반환: 시스템 프롬프트를 설정할 수 없는 환경에서 초기 지침 문자열.

---

## LSP vs JetBrains 선택 가이드

- JetBrains 기반 도구를 사용해야 할 때
  - IDE가 해당 프로젝트를 열고 있고 Serena 플러그인 서비스가 실행 중이며, 풍부한 인덱싱/참조 분석을 즉시 활용하고 싶을 때.
  - 일부 언어/프로젝트에서 IDE 인덱스가 LSP보다 더 정확하거나 준비가 빠른 경우.
- LSP 기반 도구를 사용해야 할 때
  - 별도의 IDE 의존성 없이 서버 사이드/CI 환경에서 일관된 분석/편집이 필요할 때(기본적 선택).
  - 언어 서버가 잘 지원되는 언어/프로젝트 구성.
- 동일 목적 도구의 선택
  - `find_symbol` vs `jet_brains_find_symbol`: 실행 환경에 따라 선택. 결과 구조는 유사하나 원천(LS vs IDE)과 세부 필드가 다를 수 있음.
  - 편집은 LSP/JetBrains 모두 지원되나, 현재 심볼 편집은 LSP 경로(`LanguageServerCodeEditor`)를 기본으로 가정.

---

## 에러 처리와 안전성

- 공통 에러/메시지 패턴
  - 활성 프로젝트 없음: `"Error: No active project. Ask to user to select a project from this list: [...]"`
  - 도구 비활성: `"Error: Tool '...' is not active. Active tools: [...]"`
  - 출력 길이 초과: `"The answer is too long (N characters). Please try a more specific tool query or raise the max_answer_chars parameter."`
- 파일 경로 검증
  - 파일/디렉토리 존재 확인 및 프로젝트 내 경로 제한.
  - 디렉토리 기대/파일 기대가 어긋나면 `ValueError`.
- 위험 명령 금지
  - `ExecuteShellCommandTool`은 보안상 위험한 명령을 실행하지 않도록 설계/프롬프트 가이드에 의존.
- SolidLSPException 처리
  - 언어 서버 종료 감지 시 재기동 후 1회 재시도.
- 대용량 출력
  - `max_answer_chars`를 조정하기보다 쿼리를 더 구체화하는 것을 권장.

---

## 예시 섹션 (MCP 호출 파라미터)

- 검색→검토→편집→검증 워크플로우 예
  1) 검색:

  ```json
  { "tool": "find_symbol", "arguments": { "name_path": "Service/run", "relative_path": "src", "depth": 1 } }
  ```

  2) 참조 검토:

  ```json
  { "tool": "find_referencing_symbols", "arguments": { "name_path": "Service/run", "relative_path": "src/app.py" } }
  ```

  3) 편집:

  ```json
  { "tool": "replace_symbol_body", "arguments": { "name_path": "Service/run", "relative_path": "src/app.py", "body": "def run(self):\n    return True\n" } }
  ```

  4) 요약:

  ```json
  { "tool": "summarize_changes", "arguments": {} }
  ```

---

## 부록

- SymbolKind 값(요약)
  - 대표값: 5(Class), 6(Method), 12(Function) 등. 전체 목록은 `solidlsp.ls_types.SymbolKind` 참조.
- 도구 활성/비활성 정책
  - 기본 활성: 선택적 마커 없는 도구
  - 선택적(기본 비활성): `ToolMarkerOptional` 표시된 도구
- 이름 변환 규칙
  - 클래스명 `XxxYyyTool` → MCP 툴 이름 `xxx_yyy`

---
