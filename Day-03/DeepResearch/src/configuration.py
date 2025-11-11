"""Deep Research 시스템을 위한 설정 관리.

Configuration을 별도 파일로 분리함으로써 얻는 이점들:

관심사 분리 (Separation of Concerns):
- 설정 관련 코드가 별도 파일에 있으므로 더 관리하기 쉽습니다
- 메인 로직과 설정이 분리되어 코드 가독성이 향상됩니다

재사용성 (Reusability):
- 여러 모듈에서 동일한 Configuration을 사용할 수 있습니다
- 다른 파일들에서도 쉽게 import하여 활용할 수 있습니다

테스트 용이성 (Testability):
- 설정을 독립적으로 테스트할 수 있습니다
- 테스트 시 다른 설정 값으로 쉽게 교체할 수 있습니다

유지보수성 (Maintainability):
- 설정 변경 시 메인 로직을 수정할 필요가 없습니다
- 설정 변경사항을 쉽게 추적할 수 있습니다

확장성 (Scalability):
- 새로운 설정이 필요할 때 쉽게 추가할 수 있습니다
- 환경별 설정 분리가 용이합니다 (개발/스테이징/프로덕션)

보안 (Security):
- 민감한 정보(API 키, 토큰 등)를 별도 파일에서 관리할 수 있습니다
- 설정 파일에 대한 접근 권한을 별도로 관리할 수 있습니다

성능 최적화 (Performance):
- 한 번 로드된 설정을 애플리케이션 전체에서 재사용할 수 있습니다
- 불필요한 재계산을 방지할 수 있습니다

개발 경험 개선 (Developer Experience):
- 설정 관련 자동 완성 및 타입 힌트가 더 정확해집니다
- 설정에 대한 문서를 별도로 작성하고 관리할 수 있습니다

팀 협업 (Team Collaboration):
- 여러 개발자가 설정과 로직을 동시에 작업할 수 있습니다
- 설정 변경사항만 별도로 리뷰할 수 있습니다

장기적 이점 (Long-term Benefits):
- 더 모듈화되고 구조화된 코드베이스를 만들 수 있습니다
- 새로운 기능 추가 시 기존 코드를 최소한으로 변경할 수 있습니다
- 기술 부채를 효과적으로 관리할 수 있습니다
"""

import os
from enum import Enum
from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field


class SearchAPI(Enum):
    """사용 가능한 검색 API 제공자 열거형."""

    OPENAI = "openai"
    TAVILY = "tavily"
    NONE = "none"


class MCPConfig(BaseModel):
    """Model Context Protocol (MCP) 서버 설정."""

    url: str | None = Field(
        default=None,
    )
    """MCP 서버의 URL"""
    tools: list[str] | None = Field(
        default=None,
    )
    """LLM에서 사용할 수 있도록 설정할 도구들"""
    auth_required: bool | None = Field(
        default=False,
    )
    """MCP 서버가 인증을 필요로 하는지 여부"""


class Configuration(BaseModel):
    """Deep Research 에이전트를 위한 주요 설정 클래스."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # 일반 설정
    max_structured_output_retries: int = Field(
        default=3, description="모델로부터 구조화된 출력 호출에 대한 최대 재시도 횟수"
    )
    allow_clarification: bool = Field(
        default=True,
        description="연구를 시작하기 전에 연구자가 사용자에게 설명을 요청할 수 있도록 허용할지 여부",
    )
    max_concurrent_research_units: int = Field(
        default=5,
        description="동시에 실행할 최대 연구 단위 수. 이는 연구자가 여러 하위 에이전트를 사용하여 연구를 수행할 수 있도록 합니다. 참고: 동시성을 높이면 속도 제한에 걸릴 수 있습니다.",
    )
    # 연구 설정
    search_api: SearchAPI = Field(
        default=SearchAPI.TAVILY,
        description="연구에 사용할 검색 API. 사용 가능: anthropic | openai | tavily | none. 참고: 선택한 검색 API를 연구자/압축 모델이 지원하는지 확인하세요.",
    )
    max_researcher_iterations: int = Field(
        default=6,
        description="연구 감독자의 최대 연구 반복 횟수. 이는 연구 감독자가 연구에 대해 성찰하고 후속 질문을 하는 횟수입니다.",
    )
    max_react_tool_calls: int = Field(
        default=10, description="단일 연구자 단계에서 수행할 최대 도구 호출 반복 횟수"
    )
    # 모델 설정
    summarization_model: str = Field(
        default="openai:gpt-4.1-mini",
        description="Tavily 검색 결과로부터 연구 결과를 요약하기 위한 모델",
    )
    summarization_model_max_tokens: int = Field(
        default=16000, description="요약 모델의 최대 출력 토큰 수"
    )
    max_content_length: int = Field(
        default=50000, description="요약 전 웹페이지 콘텐츠의 최대 문자 길이"
    )
    research_model: str = Field(
        default="openai:gpt-4.1",
        description="연구 수행을 위한 모델. 참고: 선택한 검색 API를 연구자 모델이 지원하는지 확인하세요.",
    )
    research_model_max_tokens: int = Field(
        default=16000, description="연구 모델의 최대 출력 토큰 수"
    )
    compression_model: str = Field(
        default="openai:gpt-4.1-mini",
        description="하위 에이전트로부터 연구 결과를 압축하기 위한 모델. 참고: 선택한 검색 API를 압축 모델이 지원하는지 확인하세요.",
    )
    compression_model_max_tokens: int = Field(
        default=16000, description="압축 모델의 최대 출력 토큰 수"
    )
    final_report_model: str = Field(
        default="openai:gpt-4.1",
        description="모든 연구 결과로부터 최종 보고서를 작성하기 위한 모델",
    )
    final_report_model_max_tokens: int = Field(
        default=12000, description="최종 보고서 모델의 최대 출력 토큰 수"
    )
    # MCP server configuration
    mcp_config: MCPConfig | None = Field(
        default=None,
        description="MCP 서버 설정",
    )
    mcp_prompt: str | None = Field(
        default=None,
        description="에이전트가 사용할 수 있는 MCP 도구에 대한 추가 지침",
    )

    @classmethod
    def from_runnable_config(cls, config: RunnableConfig | None = None) -> "Configuration":
        """RunnableConfig에서 Configuration 인스턴스를 생성합니다."""
        configurable = config.get("configurable", {}) if config else {}
        field_names = list(cls.model_fields.keys())
        values: dict[str, Any] = {
            field_name: os.environ.get(field_name.upper(), configurable.get(field_name))
            for field_name in field_names
        }
        return cls(**{k: v for k, v in values.items() if v is not None})
