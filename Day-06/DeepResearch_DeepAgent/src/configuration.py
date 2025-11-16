"""DeepAgent 프레임워크를 사용하는 딥 리서치 에이전트의 설정입니다.

이 모듈은 DeepAgent 기반 연구 시스템을 위한 설정 관리를 제공하며,
DeepAgent 전용 매개변수로 원래 설정을 확장합니다.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SearchAPI(str, Enum):
    """검색 API 제공자 옵션입니다."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    TAVILY = "tavily"
    NONE = "none"


class MCPConfig(BaseModel):
    """MCP (Model Context Protocol) 설정입니다."""

    url: Optional[str] = None
    tools: list[str] = Field(default_factory=list)
    auth_required: bool = False


class DeepAgentConfiguration(BaseModel):
    """DeepAgent 기반 딥 리서치 에이전트를 위한 설정입니다.

    이 설정은 동적 할당 및 스킬 관리를 위한 DeepAgent 전용 매개변수로
    원래 DeepResearch 설정을 확장합니다.
    """

    # 모델 설정
    main_model: str = Field(
        default="openai:gpt-4.1",
        description="메인 오케스트레이터 모델",
    )
    researcher_model: Optional[str] = Field(
        default=None,
        description="연구자 서브에이전트용 모델 (None일 경우 main_model을 상속)",
    )
    summarization_model: str = Field(
        default="openai:gpt-4.1",
        description="요약 작업용 모델",
    )
    summarization_model_max_tokens: int = Field(
        default=4000,
        description="요약 모델의 최대 토큰 수",
    )

    # 검색 설정
    search_api: SearchAPI = Field(
        default=SearchAPI.TAVILY,
        description="사용할 검색 API 제공자",
    )
    max_content_length: int = Field(
        default=50000,
        description="웹 컨텐츠에서 포함할 최대 문자 수",
    )

    # MCP 설정
    mcp_config: Optional[MCPConfig] = Field(
        default=None,
        description="추가 도구를 위한 MCP 서버 설정",
    )

    # DeepAgent 전용 설정
    max_parallel_researchers: int = Field(
        default=5,
        ge=1,
        le=10,
        description="병렬로 생성할 최대 연구자 수",
    )
    max_researcher_iterations: int = Field(
        default=10,
        ge=1,
        le=20,
        description="최종화 전 최대 연구 반복 횟수",
    )
    enable_critique_phase: bool = Field(
        default=False,
        description="품질 검증을 위한 비평가 서브에이전트 활성화 여부",
    )
    compression_threshold_tokens: int = Field(
        default=150000,
        description="압축을 시작하는 토큰 임계값",
    )

    # 재시도 설정
    max_structured_output_retries: int = Field(
        default=3,
        description="구조화된 출력 파싱을 위한 최대 재시도 횟수",
    )

    # 백엔드 설정
    use_persistent_backend: bool = Field(
        default=False,
        description="상태 기반 대신 지속적인 파일시스템 백엔드 사용 여부",
    )
    workspace_root: Optional[str] = Field(
        default=None,
        description="지속적인 파일시스템 백엔드를 위한 루트 디렉토리",
    )

    @classmethod
    def from_runnable_config(cls, config: dict) -> "DeepAgentConfiguration":
        """LangGraph runnable config로부터 설정을 생성합니다.

        Args:
            config: 런타임 설정 딕셔너리

        Returns:
            DeepAgentConfiguration 인스턴스
        """
        # config가 None인 경우 기본 설정 사용
        if config is None:
            config = {}
        configurable = config.get("configurable", {})

        return cls(
            main_model=configurable.get("main_model", cls.model_fields["main_model"].default),
            researcher_model=configurable.get("researcher_model"),
            summarization_model=configurable.get(
                "summarization_model", cls.model_fields["summarization_model"].default
            ),
            search_api=configurable.get("search_api", cls.model_fields["search_api"].default),
            max_parallel_researchers=configurable.get(
                "max_parallel_researchers",
                cls.model_fields["max_parallel_researchers"].default,
            ),
            max_researcher_iterations=configurable.get(
                "max_researcher_iterations",
                cls.model_fields["max_researcher_iterations"].default,
            ),
            enable_critique_phase=configurable.get(
                "enable_critique_phase",
                cls.model_fields["enable_critique_phase"].default,
            ),
            mcp_config=configurable.get("mcp_config"),
        )

    def to_runnable_config(self) -> dict:
        """LangGraph runnable config 형식으로 변환합니다.

        Returns:
            LangGraph config 매개변수에 적합한 딕셔너리
        """
        return {
            "configurable": {
                "main_model": self.main_model,
                "researcher_model": self.researcher_model,
                "summarization_model": self.summarization_model,
                "search_api": self.search_api.value,
                "max_parallel_researchers": self.max_parallel_researchers,
                "max_researcher_iterations": self.max_researcher_iterations,
                "enable_critique_phase": self.enable_critique_phase,
                "mcp_config": self.mcp_config.model_dump() if self.mcp_config else None,
            }
        }


# 기본 설정 인스턴스
DEFAULT_CONFIG = DeepAgentConfiguration()
