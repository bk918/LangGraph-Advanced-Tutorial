"""
serena/analytics.py - 도구 사용 통계 및 토큰 수 추정

이 파일은 Serena 에이전트의 도구 사용 통계를 기록하고, 텍스트의 토큰 수를 추정하는 기능을 담당합니다.
주요 컴포넌트는 다음과 같습니다:
- TokenCountEstimator: 텍스트의 토큰 수를 추정하는 추상 базо 클래스.
- TiktokenCountEstimator: `tiktoken` 라이브러리를 사용하여 토큰 수를 근사적으로 계산합니다.
- AnthropicTokenCount: Anthropic API를 사용하여 정확한 토큰 수를 계산합니다.
- RegisteredTokenCountEstimator: 사전 등록된 토큰 추정기들을 관리하는 열거형 클래스.
- ToolUsageStats: 각 도구의 호출 횟수, 입력/출력 토큰 수를 기록하고 관리합니다.

주요 특징:
- 다양한 토큰 추정 전략 지원 (근사치, 정확한 값).
- 스레드 안전성을 고려한 통계 기록.
- 도구별 상세 사용 통계 제공.

아키텍처 노트:
- `TokenCountEstimator`는 전략 패턴(Strategy Pattern)을 사용하여 구현되었습니다.
  이를 통해 새로운 토큰 계산 방식을 쉽게 추가할 수 있습니다.
- `ToolUsageStats`는 각 SerenaAgent 인스턴스에 연결되어, 에이전트 세션 동안의 도구 사용량을 추적합니다.
- 통계 데이터는 동시성 문제를 방지하기 위해 `threading.Lock`을 사용하여 보호됩니다.
"""
from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from collections import defaultdict
from copy import copy
from dataclasses import asdict, dataclass
from enum import Enum

from anthropic.types import MessageParam, MessageTokensCount
from dotenv import load_dotenv

log = logging.getLogger(__name__)


class TokenCountEstimator(ABC):
    """
    텍스트의 토큰 수를 추정하기 위한 추상 базо 클래스(ABC).

    이 클래스는 다양한 토큰 수 추정 전략을 구현하기 위한 인터페이스를 정의합니다.
    서브클래스는 `estimate_token_count` 메서드를 반드시 구현해야 합니다.
    """

    @abstractmethod
    def estimate_token_count(self, text: str) -> int:
        """
        주어진 텍스트의 토큰 수를 추정합니다.

        Args:
            text (str): 토큰 수를 계산할 텍스트.

        Returns:
            int: 추정된 토큰 수.
        """


class TiktokenCountEstimator(TokenCountEstimator):
    """
    `tiktoken` 라이브러리를 사용하여 토큰 수를 근사적으로 계산하는 추정기.

    이 클래스는 OpenAI의 `tiktoken`을 사용하여 빠르고 로컬에서 토큰 수를 계산합니다.
    초기화 시 지정된 모델에 대한 인코딩을 다운로드할 수 있습니다.
    """

    def __init__(self, model_name: str = "gpt-4o"):
        """
        `TiktokenCountEstimator`를 초기화합니다.

        처음 초기화될 때 토크나이저를 다운로드하므로 시간이 걸릴 수 있습니다.

        Args:
            model_name (str): `tiktoken.model`에서 사용 가능한 모델 이름.
        """
        import tiktoken

        log.info(f"모델 {model_name}에 대한 tiktoken 인코딩을 로드합니다. 처음 실행 시 시간이 걸릴 수 있습니다.")
        self._encoding = tiktoken.encoding_for_model(model_name)

    def estimate_token_count(self, text: str) -> int:
        """
        `tiktoken`을 사용하여 텍스트의 토큰 수를 계산합니다.

        Args:
            text (str): 토큰 수를 계산할 텍스트.

        Returns:
            int: 계산된 토큰 수.
        """
        return len(self._encoding.encode(text))


class AnthropicTokenCount(TokenCountEstimator):
    """
    Anthropic API를 사용하여 정확한 토큰 수를 계산하는 추정기.

    이 클래스는 Anthropic의 공식 API를 호출하여 토큰 수를 계산합니다.
    토큰 수 계산 자체는 무료이지만, API 속도 제한이 적용되며 API 키가 필요합니다.
    API 키는 보통 환경 변수를 통해 설정됩니다.

    참고: https://docs.anthropic.com/en/docs/build-with-claude/token-counting
    """

    def __init__(self, model_name: str = "claude-sonnet-4-20250514", api_key: str | None = None):
        """
        `AnthropicTokenCount`를 초기화합니다.

        Args:
            model_name (str): 사용할 Anthropic 모델 이름.
            api_key (str | None): Anthropic API 키. None일 경우, 환경 변수에서 로드합니다.
        """
        import anthropic

        self._model_name = model_name
        if api_key is None:
            load_dotenv()
        self._anthropic_client = anthropic.Anthropic(api_key=api_key)

    def _send_count_tokens_request(self, text: str) -> MessageTokensCount:
        """
        Anthropic API에 토큰 수 계산 요청을 보냅니다.

        Args:
            text (str): 토큰 수를 계산할 텍스트.

        Returns:
            MessageTokensCount: API로부터 반환된 토큰 수 정보 객체.
        """
        return self._anthropic_client.messages.count_tokens(
            model=self._model_name,
            messages=[MessageParam(role="user", content=text)],
        )

    def estimate_token_count(self, text: str) -> int:
        """
        Anthropic API를 통해 텍스트의 입력 토큰 수를 계산합니다.

        Args:
            text (str): 토큰 수를 계산할 텍스트.

        Returns:
            int: 계산된 입력 토큰 수.
        """
        return self._send_count_tokens_request(text).input_tokens


_registered_token_estimator_instances_cache: dict[RegisteredTokenCountEstimator, TokenCountEstimator] = {}


class RegisteredTokenCountEstimator(Enum):
    """
    사전에 등록된 토큰 수 추정기들을 관리하는 열거형 클래스.

    이 클래스는 사용 가능한 토큰 추정기들을 열거형으로 정의하고,
    필요 시 해당 추정기의 인스턴스를 생성하고 캐싱하는 역할을 합니다.
    """

    TIKTOKEN_GPT4O = "TIKTOKEN_GPT4O"
    ANTHROPIC_CLAUDE_SONNET_4 = "ANTHROPIC_CLAUDE_SONNET_4"

    @classmethod
    def get_valid_names(cls) -> list[str]:
        """
        등록된 모든 토큰 수 추정기의 이름 목록을 가져옵니다.

        Returns:
            list[str]: 추정기 이름의 목록.
        """
        return [estimator.name for estimator in cls]

    def _create_estimator(self) -> TokenCountEstimator:
        """
        열거형 멤버에 해당하는 토큰 추정기 인스턴스를 생성합니다.

        Returns:
            TokenCountEstimator: 생성된 토큰 추정기 인스턴스.

        Raises:
            ValueError: 알 수 없는 토큰 추정기일 경우 발생합니다.
        """
        match self:
            case RegisteredTokenCountEstimator.TIKTOKEN_GPT4O:
                return TiktokenCountEstimator(model_name="gpt-4o")
            case RegisteredTokenCountEstimator.ANTHROPIC_CLAUDE_SONNET_4:
                return AnthropicTokenCount(model_name="claude-sonnet-4-20250514")
            case _:
                raise ValueError(f"알 수 없는 토큰 수 추정기: {self.value}")

    def load_estimator(self) -> TokenCountEstimator:
        """
        토큰 추정기 인스턴스를 로드합니다. 인스턴스가 캐시에 없으면 새로 생성합니다.

        Returns:
            TokenCountEstimator: 로드되거나 생성된 토큰 추정기 인스턴스.
        """
        estimator_instance = _registered_token_estimator_instances_cache.get(self)
        if estimator_instance is None:
            estimator_instance = self._create_estimator()
            _registered_token_estimator_instances_cache[self] = estimator_instance
        return estimator_instance


class ToolUsageStats:
    """
    도구 사용 통계를 기록하고 관리하는 클래스.

    이 클래스는 각 도구의 호출 횟수, 총 입력 토큰, 총 출력 토큰을 추적합니다.
    통계는 스레드 안전(thread-safe) 방식으로 기록됩니다.
    """

    def __init__(self, token_count_estimator: RegisteredTokenCountEstimator = RegisteredTokenCountEstimator.TIKTOKEN_GPT4O):
        """
        `ToolUsageStats`를 초기화합니다.

        Args:
            token_count_estimator (RegisteredTokenCountEstimator): 사용할 토큰 수 추정기.
        """
        self._token_count_estimator = token_count_estimator.load_estimator()
        self._token_estimator_name = token_count_estimator.value
        self._tool_stats: dict[str, ToolUsageStats.Entry] = defaultdict(ToolUsageStats.Entry)
        self._tool_stats_lock = threading.Lock()

    @property
    def token_estimator_name(self) -> str:
        """
        사용된 등록된 토큰 수 추정기의 이름을 가져옵니다.

        Returns:
            str: 토큰 추정기 이름.
        """
        return self._token_estimator_name

    @dataclass(kw_only=True)
    class Entry:
        """
        단일 도구에 대한 사용 통계를 저장하는 데이터 클래스.

        Attributes:
            num_times_called (int): 도구가 호출된 횟수.
            input_tokens (int): 누적 입력 토큰 수.
            output_tokens (int): 누적 출력 토큰 수.
        """

        num_times_called: int = 0
        input_tokens: int = 0
        output_tokens: int = 0

        def update_on_call(self, input_tokens: int, output_tokens: int) -> None:
            """
            단일 호출에 사용된 토큰 수로 통계 항목을 업데이트합니다.

            Args:
                input_tokens (int): 해당 호출의 입력 토큰 수.
                output_tokens (int): 해당 호출의 출력 토큰 수.
            """
            self.num_times_called += 1
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens

    def _estimate_token_count(self, text: str) -> int:
        """내부 토큰 추정기를 사용하여 텍스트의 토큰 수를 계산합니다."""
        return self._token_count_estimator.estimate_token_count(text)

    def get_stats(self, tool_name: str) -> ToolUsageStats.Entry:
        """
        특정 도구에 대한 현재 사용 통계의 복사본을 가져옵니다.

        Args:
            tool_name (str): 통계를 가져올 도구의 이름.

        Returns:
            ToolUsageStats.Entry: 해당 도구의 통계 정보.
        """
        with self._tool_stats_lock:
            return copy(self._tool_stats[tool_name])

    def record_tool_usage(self, tool_name: str, input_str: str, output_str: str) -> None:
        """
        도구 사용 내역을 기록합니다.

        입력 및 출력 문자열의 토큰 수를 계산하고 해당 도구의 통계를 업데이트합니다.

        Args:
            tool_name (str): 사용된 도구의 이름.
            input_str (str): 도구에 전달된 입력 문자열.
            output_str (str): 도구에서 반환된 출력 문자열.
        """
        input_tokens = self._estimate_token_count(input_str)
        output_tokens = self._estimate_token_count(output_str)
        with self._tool_stats_lock:
            entry = self._tool_stats[tool_name]
            entry.update_on_call(input_tokens, output_tokens)

    def get_tool_stats_dict(self) -> dict[str, dict[str, int]]:
        """
        모든 도구의 통계를 딕셔너리 형태로 가져옵니다.

        Returns:
            dict[str, dict[str, int]]: 각 도구 이름에 대한 통계 딕셔너리.
        """
        with self._tool_stats_lock:
            return {name: asdict(entry) for name, entry in self._tool_stats.items()}

    def clear(self) -> None:
        """
        기록된 모든 도구 사용 통계를 초기화합니다.
        """
        with self._tool_stats_lock:
            self._tool_stats.clear()