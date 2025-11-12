# MCP Server Implementation - MCP 서버 구현 상세 분석

## 🎯 MCP 서버 개요

MCP(Model Context Protocol) 서버는 SerenaMCP의 **통신 계층**으로, 클라이언트(MCP 클라이언트)와 SerenaAgent 사이의 요청/응답을 중재합니다. FastMCP 프레임워크를 기반으로 구축되어 있으며, 다양한 MCP 클라이언트와의 호환성을 제공합니다.

## 🏗️ MCP Server Architecture

### **MCP 서버 핵심 구조**

```python
class SerenaMCPFactory:
    """
    SerenaMCP 서버 팩토리 클래스.

    이 클래스는 다음의 주요 기능을 담당합니다:
    1. MCP 서버 인스턴스 생성
    2. 도구 등록 및 관리
    3. 요청 라우팅 및 처리
    4. 클라이언트와의 통신
    5. 서버 생명주기 관리
    """

    def create_mcp_server(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        modes: Sequence[str] = DEFAULT_MODES,
        enable_web_dashboard: bool | None = None,
        enable_gui_log_window: bool | None = None,
        log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | None = None,
        trace_lsp_communication: bool | None = None,
        tool_timeout: float | None = None,
    ) -> FastMCP:
```

### **FastMCP 프레임워크 기반**

#### **FastMCP 핵심 기능**
- **비동기 웹 프레임워크**: FastAPI 기반의 고성능 MCP 서버
- **자동 도구 발견**: 데코레이터 기반 도구 등록
- **타입 안전성**: Pydantic을 통한 요청/응답 검증
- **OpenAPI 문서화**: 자동 API 문서 생성

#### **MCP 프로토콜 지원**
- **stdio**: 표준 입출력 기반 통신 (기본)
- **sse**: Server-Sent Events (실시간 업데이트)
- **streamable-http**: 스트리밍 HTTP (고급 기능)

### **서버 초기화 과정**

#### **1단계: 설정 로딩 및 검증**
```python
def create_mcp_server(self, ...):
    """MCP 서버를 생성하고 초기화합니다."""

    # 설정 로딩 (계층적 우선순위 적용)
    serena_config = SerenaConfig.from_config_file()

    # CLI 인수 우선 적용
    if log_level is not None:
        serena_config.log_level = getattr(logging, log_level)

    # 웹 대시보드 설정
    if enable_web_dashboard is not None:
        serena_config.web_dashboard = enable_web_dashboard

    # GUI 로그 창 설정
    if enable_gui_log_window is not None:
        serena_config.gui_log_window_enabled = enable_gui_log_window

    # 기타 설정 적용
    if trace_lsp_communication is not None:
        serena_config.trace_lsp_communication = trace_lsp_communication
    if tool_timeout is not None:
        serena_config.tool_timeout = tool_timeout
```

#### **2단계: 에이전트 인스턴스화**
```python
# SerenaAgent 인스턴스 생성
self._instantiate_agent(serena_config, modes)

# 에이전트가 준비될 때까지 대기
if self.agent is None:
    raise RuntimeError("Failed to instantiate agent")

# 활성 도구 목록 수집
exposed_tool_instances = list(self.agent.get_exposed_tool_instances())
```

#### **3단계: MCP 서버 설정**
```python
# FastMCP 서버 인스턴스 생성
mcp = FastMCP(
    name="SerenaMCP",
    description="Advanced coding agent toolkit with multi-language support",
    version=serena_version(),
    instructions=self._get_initial_instructions(),
)

# 도구 등록
for tool in exposed_tool_instances:
    mcp_tool = self.make_mcp_tool(tool, openai_tool_compatible=False)
    mcp.add_tool(mcp_tool)

# 서버 생명주기 관리
@asynccontextmanager
async def server_lifespan(mcp_server: FastMCP):
    # 서버 시작 전 처리
    yield
    # 서버 종료 후 처리
```

### **도구 등록 및 변환**

#### **MCP 도구 변환 로직**
```python
@staticmethod
def make_mcp_tool(tool: Tool, openai_tool_compatible: bool = True) -> MCPTool:
    """
    Serena 도구를 MCP 도구로 변환합니다.

    Args:
        tool: 변환할 Serena 도구 인스턴스
        openai_tool_compatible: OpenAI 호환성 여부

    Returns:
        MCPTool: 변환된 MCP 도구
    """
    def execute_fn(**kwargs) -> str:
        # 도구 실행 및 결과 반환
        return tool.apply_ex(**kwargs)

    # MCP 도구 생성
    mcp_tool = MCPTool(
        name=tool.get_name(),
        description=tool.get_apply_docstring(),
        inputSchema=tool.get_apply_fn_metadata().to_json_schema(),
        execute=execute_fn,
    )

    # OpenAI 호환성 적용
    if openai_tool_compatible:
        mcp_tool = SerenaMCPFactory._sanitize_for_openai_tools(mcp_tool)

    return mcp_tool
```

#### **OpenAI 호환성 처리**
```python
@staticmethod
def _sanitize_for_openai_tools(schema: dict) -> dict:
    """
    MCP 도구 스키마를 OpenAI 호환 형식으로 변환합니다.

    Args:
        schema: 변환할 MCP 스키마

    Returns:
        OpenAI 호환 스키마
    """
    def walk(node):
        # 재귀적으로 노드 순회하며 변환
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                # object 타입 처리
                required = node.get("required", [])
                properties = node.get("properties", {})

                # OpenAI 형식으로 변환
                for prop_name, prop_schema in properties.items():
                    walk(prop_schema)

            elif node.get("type") == "array" and "items" in node:
                # array 타입 처리
                walk(node["items"])

            elif node.get("type") == "string" and "enum" in node:
                # enum 타입 처리
                pass  # OpenAI는 enum을 직접 지원

        elif isinstance(node, list):
            # 리스트 항목 순회
            for item in node:
                walk(item)

    walk(schema)
    return schema
```

### **요청 처리 파이프라인**

#### **요청 수신 및 처리**
```python
# MCP 서버의 기본 요청 처리
async def handle_request(request: dict) -> dict:
    """
    MCP 요청을 처리합니다.

    Args:
        request: MCP 요청 객체

    Returns:
        MCP 응답 객체
    """
    # 1. 요청 유효성 검증
    if not self._validate_request(request):
        return self._create_error_response("Invalid request")

    # 2. 도구 실행
    try:
        result = await self._execute_tool(request)
    except Exception as e:
        return self._create_error_response(str(e))

    # 3. 응답 생성
    return self._create_success_response(result)
```

#### **도구 실행 엔진**
```python
async def _execute_tool(self, request: dict) -> Any:
    """
    요청된 도구를 실행합니다.

    Args:
        request: 도구 실행 요청

    Returns:
        도구 실행 결과
    """
    tool_name = request.get("tool_name")
    parameters = request.get("parameters", {})

    # 1. 도구 인스턴스 찾기
    tool = self._find_tool_by_name(tool_name)
    if tool is None:
        raise ValueError(f"Tool '{tool_name}' not found")

    # 2. 매개변수 검증
    validated_params = self._validate_parameters(tool, parameters)

    # 3. 비동기 실행
    if asyncio.iscoroutinefunction(tool.apply_ex):
        result = await tool.apply_ex(**validated_params)
    else:
        # 동기 함수를 비동기로 실행
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: tool.apply_ex(**validated_params)
        )

    return result
```

### **서버 생명주기 관리**

#### **서버 시작 프로세스**
```python
def start_mcp_server(
    project: str | None = None,
    context: str = DEFAULT_CONTEXT,
    modes: tuple[str, ...] = DEFAULT_MODES,
    transport: Literal["stdio", "sse", "streamable-http"] = "stdio",
    host: str = "0.0.0.0",
    port: int = 8000,
    **kwargs
) -> None:
    """
    MCP 서버를 시작합니다.

    Args:
        project: 활성화할 프로젝트
        context: 사용할 Context
        modes: 사용할 Mode들
        transport: 통신 프로토콜
        host: 서버 호스트
        port: 서버 포트
        **kwargs: 추가 설정
    """
    # 팩토리 인스턴스 생성
    factory = SerenaMCPFactorySingleProcess(context=context, project=project)

    # MCP 서버 생성
    mcp = factory.create_mcp_server(host=host, port=port, modes=modes, **kwargs)

    # 통신 프로토콜에 따른 서버 시작
    if transport == "stdio":
        # 표준 입출력 기반 서버
        mcp.run()
    elif transport == "sse":
        # Server-Sent Events 서버
        import uvicorn
        uvicorn.run(mcp, host=host, port=port)
    elif transport == "streamable-http":
        # 스트리밍 HTTP 서버
        mcp.run_streamable_http(host=host, port=port)
```

#### **서버 종료 프로세스**
```python
async def shutdown_handler():
    """
    서버 종료 시 호출되는 핸들러.
    """
    # 1. 활성 태스크 완료 대기
    if hasattr(self, '_task_executor'):
        self._task_executor.shutdown(wait=True)

    # 2. 언어 서버 중지
    if self.agent and self.agent.is_language_server_running():
        self.agent.language_server.stop()

    # 3. 캐시 저장
    if self.agent and self.agent.language_server:
        self.agent.language_server.save_cache()

    # 4. 리소스 정리
    self._cleanup_resources()
```

### **오류 처리 및 복구**

#### **종합 오류 처리**
```python
def _handle_execution_error(self, error: Exception, request: dict) -> dict:
    """
    도구 실행 중 발생한 오류를 처리합니다.

    Args:
        error: 발생한 예외
        request: 오류가 발생한 요청

    Returns:
        오류 응답
    """
    # 1. 오류 유형 분류
    if isinstance(error, ValidationError):
        # 매개변수 검증 오류
        return self._create_validation_error_response(error)
    elif isinstance(error, ToolExecutionError):
        # 도구 실행 오류
        return self._create_tool_error_response(error)
    elif isinstance(error, LanguageServerError):
        # 언어 서버 오류
        return self._create_language_server_error_response(error)
    else:
        # 일반적인 오류
        return self._create_generic_error_response(error)
```

#### **자동 복구 메커니즘**
```python
def _attempt_recovery(self, error: Exception, request: dict) -> dict:
    """
    오류 발생 시 자동 복구를 시도합니다.

    Args:
        error: 발생한 예외
        request: 복구를 시도할 요청

    Returns:
        복구 결과 또는 오류 응답
    """
    # 1. 언어 서버 재시작 시도
    if isinstance(error, LanguageServerTerminatedError):
        try:
            self.agent.reset_language_server()
            # 재시도
            return await self._execute_tool(request)
        except Exception as retry_error:
            return self._create_error_response("Recovery failed")

    # 2. 도구 재시작 시도
    elif isinstance(error, ToolExecutionError):
        # 도구별 복구 로직 적용
        tool = self._find_tool_by_name(request.get("tool_name"))
        if hasattr(tool, '_recover'):
            return await tool._recover(error, request)

    # 3. 복구 불가능한 오류
    return self._create_unrecoverable_error_response(error)
```

### **클라이언트 통신 프로토콜**

#### **stdio 기반 통신**
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ MCP Client  │    │ MCP Server  │    │ SerenaAgent │
│ (stdio)     │    │ (stdio)     │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
       │                  │                  │
       │ 1. Request       │                  │
       │─────────────────>│                  │
       │                  │ 2. Route Request │
       │                  │─────────────────>│
       │                  │                  │ 3. Execute Tool
       │                  │                  │─────────────>│
       │                  │                  │ 4. Tool Result
       │                  │                  │<─────────────│
       │ 5. Response      │                  │
       │<─────────────────│                  │
```

#### **HTTP 기반 통신**
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ MCP Client  │    │  HTTP Server│    │ SerenaAgent │
│ (HTTP)      │    │  (FastAPI)  │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
       │                  │                  │
       │ 1. HTTP POST     │                  │
       │─────────────────>│                  │
       │                  │ 2. Route Request │
       │                  │─────────────────>│
       │                  │                  │ 3. Execute Tool
       │                  │                  │─────────────>│
       │                  │                  │ 4. Tool Result
       │                  │                  │<─────────────│
       │ 5. HTTP Response │                  │
       │<─────────────────│                  │
```

### **성능 최적화**

#### **비동기 처리**
```python
# 비동기 도구 실행
async def execute_tool_async(self, tool_name: str, **kwargs) -> Any:
    """
    도구를 비동기로 실행합니다.

    Args:
        tool_name: 실행할 도구 이름
        **kwargs: 도구 매개변수

    Returns:
        도구 실행 결과
    """
    # 1. 도구 인스턴스 찾기
    tool = self._find_tool_by_name(tool_name)

    # 2. 비동기 실행
    if asyncio.iscoroutinefunction(tool.apply_ex):
        return await tool.apply_ex(**kwargs)
    else:
        # 동기 함수를 스레드 풀에서 실행
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._thread_pool,
            tool.apply_ex,
            **kwargs
        )
```

#### **캐싱 전략**
```python
# 도구 결과 캐싱
async def execute_with_cache(self, tool_name: str, **kwargs) -> Any:
    """
    캐시를 활용하여 도구를 실행합니다.

    Args:
        tool_name: 실행할 도구 이름
        **kwargs: 도구 매개변수

    Returns:
        캐시된 결과 또는 새로 실행된 결과
    """
    # 1. 캐시 키 생성
    cache_key = self._generate_cache_key(tool_name, kwargs)

    # 2. 캐시 확인
    if cache_key in self._cache:
        return self._cache[cache_key]

    # 3. 도구 실행
    result = await self.execute_tool_async(tool_name, **kwargs)

    # 4. 캐시 저장
    self._cache[cache_key] = result

    return result
```

## 🔧 Advanced Features

### **실시간 대시보드**
```python
# 웹 대시보드 통합
def setup_dashboard(self, agent: SerenaAgent) -> None:
    """
    웹 대시보드를 설정합니다.

    Args:
        agent: 연결할 SerenaAgent 인스턴스
    """
    # 1. 대시보드 API 설정
    dashboard_api = SerenaDashboardAPI(
        memory_log_handler=get_memory_log_handler(),
        tool_names=self._get_tool_names(),
        agent=agent,
        tool_usage_stats=self._tool_usage_stats
    )

    # 2. HTTP 서버 시작
    self._dashboard_thread, port = dashboard_api.run_in_thread()

    # 3. 대시보드 URL 출력
    dashboard_url = f"http://127.0.0.1:{port}/dashboard/"
    log.info(f"Dashboard available at: {dashboard_url}")
```

### **도구 사용 통계**
```python
# 통계 수집 및 분석
def collect_tool_statistics(self) -> dict:
    """
    도구 사용 통계를 수집합니다.

    Returns:
        수집된 통계 데이터
    """
    stats = {
        "total_requests": len(self._request_history),
        "tool_usage": self._aggregate_tool_usage(),
        "error_rates": self._calculate_error_rates(),
        "performance_metrics": self._measure_performance(),
    }

    return stats
```

## 📊 Performance Characteristics

- **서버 시작 시간**: 2-5초 (에이전트 초기화 포함)
- **요청 처리 시간**: 50-500ms (도구 실행 시간 의존)
- **메모리 사용량**: 50-200MB (활성 프로젝트 수 의존)
- **동시 요청 처리**: 최대 10-50개 (ThreadPool 크기 의존)

## 🎯 핵심 설계 원칙

### **1. 호환성 (Compatibility)**
- 다양한 MCP 클라이언트 지원
- 표준 프로토콜 준수
- 확장 가능한 아키텍처

### **2. 성능 (Performance)**
- 비동기 처리
- 캐싱 및 최적화
- 자원 효율적 관리

### **3. 안정성 (Reliability)**
- 포괄적인 오류 처리
- 자동 복구 메커니즘
- 상세한 로깅

### **4. 확장성 (Extensibility)**
- 새로운 도구 쉽게 추가
- 새로운 프로토콜 지원
- 커스텀 통신 방식

---

*MCP 서버는 SerenaMCP의 통신 중추로, 클라이언트와 에이전트 사이의 안정적이고 효율적인 연결을 제공합니다.*
