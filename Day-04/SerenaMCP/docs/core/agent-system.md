# SerenaAgent System - 에이전트 시스템 상세 분석

## 🎯 SerenaAgent 개요

`SerenaAgent`는 SerenaMCP의 **중앙 오케스트레이터**로, 모든 컴포넌트를 조정하고 관리하는 핵심 클래스입니다. 프로젝트 라이프사이클, 도구 시스템, 언어 서버, 메모리 시스템 등을 통합적으로 관리합니다.

## 🏗️ Agent Architecture

### **SerenaAgent 핵심 구조**

```python
class SerenaAgent:
    """
    SerenaMCP의 중앙 오케스트레이터 클래스.

    이 클래스는 다음의 주요 기능을 담당합니다:
    1. 프로젝트 라이프사이클 관리
    2. 도구 시스템 조정
    3. 언어 서버 관리
    4. 메모리 시스템 유지
    5. 설정 및 모드 적용
    6. MCP 서버와의 통신
    """

    def __init__(
        self,
        project: str | None = None,
        project_activation_callback: Callable[[], None] | None = None,
        serena_config: SerenaConfig | None = None,
        context: SerenaAgentContext | None = None,
        modes: list[SerenaAgentMode] | None = None,
        memory_log_handler: MemoryLogHandler | None = None,
    ):
```

### **초기화 과정 분석**

#### **1단계: 설정 로딩**
```python
# 설정 파일에서 SerenaConfig 로딩 (계층적 설정 시스템)
self.serena_config = serena_config or SerenaConfig.from_config_file()

# 로그 레벨 조정
serena_log_level = self.serena_config.log_level
if Logger.root.level > serena_log_level:
    Logger.root.setLevel(serena_log_level)
```

#### **2단계: 도구 시스템 초기화**
```python
# 모든 도구 클래스를 인스턴스화
self._all_tools: dict[type[Tool], Tool] = {
    tool_class: tool_class(self)
    for tool_class in ToolRegistry().get_all_tool_classes()
}

# 도구 이름 목록 생성
tool_names = [tool.get_name_from_cls() for tool in self._all_tools.values()]
```

#### **3단계: Context & Mode 적용**
```python
# Context 및 Mode에 따른 도구 필터링
tool_inclusion_definitions: list[ToolInclusionDefinition] = [
    self.serena_config,
    self._context
]

# 기본 도구 세트 생성 및 필터링
self._base_tool_set = ToolSet.default().apply(*tool_inclusion_definitions)
self._exposed_tools = AvailableTools([
    t for t in self._all_tools.values()
    if self._base_tool_set.includes_name(t.get_name())
])
```

#### **4단계: 언어 서버 초기화**
```python
# 백그라운드에서 언어 서버 초기화
def init_language_server() -> None:
    with LogTime("Language server initialization", logger=log):
        self.reset_language_server()
        assert self.language_server is not None

if self.is_using_language_server():
    self.issue_task(init_language_server)
```

### **프로젝트 관리 시스템**

#### **프로젝트 활성화 과정**
```python
def _activate_project(self, project: Project) -> None:
    """
    프로젝트를 활성화하고 관련 컴포넌트들을 초기화합니다.

    Args:
        project: 활성화할 Project 인스턴스
    """
    log.info(f"Activating {project.project_name} at {project.project_root}")

    # 프로젝트 설정
    self._active_project = project
    self._update_active_tools()

    # 프로젝트별 인스턴스 초기화
    self.memories_manager = MemoriesManager(project.project_root)
    self.lines_read = LinesRead()

    # 백그라운드에서 언어 서버 시작
    if self.is_using_language_server():
        self.issue_task(init_language_server)
```

#### **다중 프로젝트 지원**
- **프로젝트 등록**: `add_project_from_path()`를 통한 자동 등록
- **프로젝트 전환**: `activate_project_from_path_or_name()`으로 전환
- **프로젝트 구성**: 각 프로젝트별 `.serena/project.yml` 설정
- **프로젝트 격리**: 각 프로젝트의 독립적 메모리 및 캐시 관리

### **도구 조정 시스템**

#### **활성 도구 관리**
```python
def _update_active_tools(self) -> None:
    """
    현재 Context와 Mode에 따라 활성 도구들을 업데이트합니다.
    """
    # 기본 도구 세트에 모드 적용
    tool_set = self._base_tool_set.apply(*self._modes)

    # 활성 프로젝트의 설정 적용
    if self._active_project is not None:
        tool_set = tool_set.apply(self._active_project.project_config)

        # 읽기 전용 모드인 경우 편집 도구 제외
        if self._active_project.project_config.read_only:
            tool_set = tool_set.without_editing_tools()

    # 활성 도구 목록 업데이트
    self._active_tools = {
        tool_class: tool_instance
        for tool_class, tool_instance in self._all_tools.items()
        if tool_set.includes_name(tool_instance.get_name())
    }
```

#### **도구 실행 파이프라인**
```python
def apply_ex(self, log_call: bool = True, catch_exceptions: bool = True, **kwargs) -> str:
    """
    도구를 실행하고 오류 처리를 수행합니다.

    Args:
        log_call: 로그 기록 여부
        catch_exceptions: 예외 포착 여부
        **kwargs: 도구에 전달할 매개변수들

    Returns:
        도구 실행 결과 문자열
    """

    def task() -> str:
        # 1. 도구 활성 상태 확인
        if not self.is_active():
            return f"Error: Tool '{self.get_name_from_cls()}' is not active"

        # 2. 프로젝트 맥락 검증
        if not isinstance(self, ToolMarkerDoesNotRequireActiveProject):
            if self.agent._active_project is None:
                return "Error: No active project"

        # 3. 언어 서버 상태 확인
        if self.agent.is_using_language_server() and not self.agent.is_language_server_running():
            log.info("Language server is not running. Starting it ...")
            self.agent.reset_language_server()

        # 4. 실제 도구 실행
        try:
            result = apply_fn(**kwargs)
        except SolidLSPException as e:
            # LSP 관련 오류인 경우 언어 서버 재시작 후 재시도
            if e.is_language_server_terminated():
                self.agent.reset_language_server()
                result = apply_fn(**kwargs)
            else:
                raise

        # 5. 도구 사용 통계 기록
        self.agent.record_tool_usage_if_enabled(kwargs, result, self)

        return result

    # 비동기 태스크로 실행
    future = self.agent.issue_task(task, name=self.__class__.__name__)
    return future.result(timeout=self.agent.serena_config.tool_timeout)
```

### **메모리 시스템 관리**

#### **MemoriesManager 구현**
```python
class MemoriesManager:
    """
    프로젝트별 메모리 파일을 관리하는 클래스입니다.
    """

    def __init__(self, project_root: str):
        self._memory_dir = Path(get_serena_managed_in_project_dir(project_root)) / "memories"
        self._memory_dir.mkdir(parents=True, exist_ok=True)

    def save_memory(self, name: str, content: str) -> str:
        """메모리를 마크다운 파일로 저장합니다."""
        memory_file_path = self._get_memory_file_path(name)
        with open(memory_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Memory {name} written."

    def load_memory(self, name: str) -> str:
        """저장된 메모리를 읽어옵니다."""
        memory_file_path = self._get_memory_file_path(name)
        if not memory_file_path.exists():
            return f"Memory file {name} not found"
        with open(memory_file_path, encoding="utf-8") as f:
            return f.read()
```

### **언어 서버 관리**

#### **언어 서버 초기화**
```python
def reset_language_server(self) -> None:
    """
    언어 서버를 재시작합니다.
    """
    # 기존 언어 서버 중지
    if self.is_language_server_running():
        assert self.language_server is not None
        log.info(f"Stopping the current language server at {self.language_server.repository_root_path} ...")
        self.language_server.stop()
        self.language_server = None

    # 새로운 언어 서버 인스턴스화 및 시작
    assert self._active_project is not None
    self.language_server = self._active_project.create_language_server(
        log_level=self.serena_config.log_level,
        ls_timeout=ls_timeout,
        trace_lsp_communication=self.serena_config.trace_lsp_communication,
        ls_specific_settings=self.serena_config.ls_specific_settings,
    )
    log.info(f"Starting the language server for {self._active_project.project_name}")
    self.language_server.start()

    if not self.language_server.is_running():
        raise RuntimeError(f"Failed to start the language server for {self._active_project.project_name}")
```

### **비동기 태스크 처리**

#### **ThreadPoolExecutor 활용**
```python
def __init__(self, ...):
    # 단일 스레드 기반 태스크 실행기 생성
    # 이는 선형적인 태스크 실행을 보장하기 위함
    self._task_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="SerenaAgentExecutor")
    self._task_executor_lock = threading.Lock()
    self._task_executor_task_index = 1

def issue_task(self, task: Callable[[], Any], name: str | None = None) -> Future:
    """
    태스크를 실행기에 제출하여 비동기로 실행합니다.

    Args:
        task: 실행할 함수
        name: 로깅을 위한 태스크 이름

    Returns:
        Future 객체
    """
    with self._task_executor_lock:
        task_name = f"Task-{self._task_executor_task_index}[{name or task.__name__}]"
        self._task_executor_task_index += 1

        def task_execution_wrapper() -> Any:
            with LogTime(task_name, logger=log):
                return task()

        log.info(f"Scheduling {task_name}")
        return self._task_executor.submit(task_execution_wrapper)
```

### **설정 시스템 통합**

#### **동적 설정 적용**
```python
def create_system_prompt(self) -> str:
    """
    현재 Context와 Mode에 기반한 시스템 프롬프트를 생성합니다.
    """
    available_markers = self._exposed_tools.tool_marker_names
    log.info("Generating system prompt with available_tools=(see exposed tools), available_markers=%s", available_markers)

    system_prompt = self.prompt_factory.create_system_prompt(
        context_system_prompt=self._format_prompt(self._context.prompt),
        mode_system_prompts=[self._format_prompt(mode.prompt) for mode in self._modes],
        available_tools=self._exposed_tools.tool_names,
        available_markers=available_markers,
    )
    log.info("System prompt:\n%s", system_prompt)
    return system_prompt
```

### **오류 처리 및 복구**

#### **종합적인 오류 처리**
```python
def apply_ex(self, **kwargs):
    try:
        result = apply_fn(**kwargs)
    except SolidLSPException as e:
        # LSP 관련 오류인 경우 언어 서버 재시작 후 재시도
        if e.is_language_server_terminated():
            log.error(f"Language server terminated while executing tool ({e}). Restarting the language server and retrying ...")
            self.agent.reset_language_server()
            result = apply_fn(**kwargs)
        else:
            raise
    except Exception as e:
        # 일반적인 오류 처리
        if not catch_exceptions:
            raise
        msg = f"Error executing tool: {e}"
        log.error(f"Error executing tool: {e}", exc_info=e)
        result = msg

    # 언어 서버 캐시 저장
    try:
        if self.agent.language_server is not None:
            self.agent.language_server.save_cache()
    except Exception as e:
        log.error(f"Error saving language server cache: {e}")

    return result
```

## 📊 Agent State Management

### **에이전트 상태 추적**
```python
def get_current_config_overview(self) -> str:
    """
    현재 에이전트의 전체 설정 상태를 반환합니다.
    """
    result_str = "Current configuration:\n"
    result_str += f"Serena version: {serena_version()}\n"
    result_str += f"Loglevel: {self.serena_config.log_level}\n"

    if self._active_project is not None:
        result_str += f"Active project: {self._active_project.project_name}\n"
    else:
        result_str += "No active project\n"

    result_str += "Available projects:\n" + "\n".join(list(self.serena_config.project_names)) + "\n"
    result_str += f"Active context: {self._context.name}\n"
    result_str += f"Active modes: {', '.join([mode.name for mode in self.get_active_modes()])}\n"
    result_str += f"Active tools ({len(self._active_tools)}): {', '.join(self.get_active_tool_names())}\n"

    return result_str
```

## 🔧 Advanced Features

### **GUI 및 Dashboard 통합**
```python
# GUI 로그 뷰어 초기화 (플랫폼별 지원)
if self.serena_config.gui_log_window_enabled:
    if platform.system() == "Darwin":
        log.warning("GUI log window is not supported on macOS")
    else:
        from serena.gui_log_viewer import GuiLogViewer
        self._gui_log_viewer = GuiLogViewer("dashboard", title="Serena Logs")
        self._gui_log_viewer.start()

# 웹 대시보드 초기화
if self.serena_config.web_dashboard:
    self._dashboard_thread, port = SerenaDashboardAPI(
        get_memory_log_handler(), tool_names, agent=self, tool_usage_stats=self._tool_usage_stats
    ).run_in_thread()
    dashboard_url = f"http://127.0.0.1:{port}/dashboard/index.html"
    log.info("Serena web dashboard started at %s", dashboard_url)
```

### **도구 사용 통계 수집**
```python
# 도구 사용 통계 기록 (설정된 경우)
if self.serena_config.record_tool_usage_stats:
    token_count_estimator = RegisteredTokenCountEstimator[self.serena_config.token_count_estimator]
    log.info(f"Tool usage statistics recording is enabled with token count estimator: {token_count_estimator.name}.")
    self._tool_usage_stats = ToolUsageStats(token_count_estimator)
```

## 🎯 핵심 설계 원칙

### **1. 모듈성 (Modularity)**
- 각 기능별 독립적 컴포넌트
- 플러그인 아키텍처 지원
- 확장 가능한 도구 시스템

### **2. 신뢰성 (Reliability)**
- 포괄적인 오류 처리
- 자동 복구 메커니즘
- 상세한 로깅 시스템

### **3. 성능 최적화 (Performance)**
- 비동기 처리
- 캐싱 전략
- 자원 효율적 관리

### **4. 확장성 (Extensibility)**
- 새로운 도구 쉽게 추가
- 새로운 언어 지원 가능
- 커스텀 Context/Mode 지원

## 📈 Performance Characteristics

- **초기화 시간**: 2-5초 (설정 및 언어 서버 로딩)
- **메모리 사용량**: 100-500MB (프로젝트 크기 의존)
- **도구 실행 시간**: 50-500ms (작업 복잡도 의존)
- **프로젝트 전환 시간**: 1-3초 (언어 서버 재시작 포함)

---

*SerenaAgent는 SerenaMCP의 핵심 두뇌로, 복잡한 코딩 작업을 지능적으로 처리하고 관리하는 정교한 오케스트레이션 시스템입니다.*
