"""
InterPrompt 프롬프트 팩토리 시스템

이 파일은 InterPrompt 패키지의 프롬프트 팩토리 시스템을 구현합니다.
자동 생성되는 프롬프트 팩토리 클래스들의 베이스 클래스와 생성 유틸리티를 제공합니다.

주요 컴포넌트:
- PromptFactoryBase: 자동 생성되는 프롬프트 팩토리 클래스들의 베이스
- autogenerate_prompt_factory_module: 프롬프트 팩토리 모듈 자동 생성 함수

주요 기능:
- 다국어 프롬프트 컬렉션 관리
- 자동 코드 생성을 통한 타입 안전한 프롬프트 접근
- 언어별 폴백 처리 지원

아키텍처:
- 빌더 패턴을 활용한 프롬프트 팩토리 자동 생성
- MultiLangPromptCollection을 통한 다국어 지원
- 동적 메서드 생성을 통한 타입 안전성
"""

import logging
import os
from typing import Any

from .multilang_prompt import DEFAULT_LANG_CODE, LanguageFallbackMode, MultiLangPromptCollection, PromptList

log = logging.getLogger(__name__)


class PromptFactoryBase:
    """
    자동 생성되는 프롬프트 팩토리 클래스들의 베이스 클래스

    이 클래스는 autogenerate_prompt_factory_module 함수를 통해
    자동 생성되는 프롬프트 팩토리 클래스들의 공통 기능을 제공합니다.
    각 애플리케이션에서 프롬프트 템플릿과 리스트를 검색하고 렌더링하는
    중앙 엔트리 포인트 역할을 합니다.

    주요 기능:
    - 다국어 프롬프트 컬렉션 초기화
    - 프롬프트 템플릿 렌더링
    - 프롬프트 리스트 조회
    - 타입 안전한 메서드 제공

    Attributes:
        lang_code (str): 사용할 언어 코드
        _prompt_collection (MultiLangPromptCollection): 내부 프롬프트 컬렉션

    Note:
        이 클래스는 직접 인스턴스화하지 말고, autogenerate_prompt_factory_module을
        통해 생성된 구체 클래스를 사용하세요.
    """

    def __init__(self, prompts_dir: str | list[str], lang_code: str = DEFAULT_LANG_CODE, fallback_mode=LanguageFallbackMode.EXCEPTION):
        """
        프롬프트 팩토리 베이스를 초기화합니다.

        주어진 프롬프트 디렉토리로부터 MultiLangPromptCollection을 생성하고,
        지정된 언어 코드와 폴백 모드로 초기화합니다.

        Args:
            prompts_dir (str | list[str]): 프롬프트 템플릿과 리스트가 있는 디렉토리.
                리스트가 제공되면 왼쪽부터 오른쪽으로 우선순위를 적용합니다.
            lang_code (str): 프롬프트 템플릿과 리스트를 조회할 언어 코드.
                단일 언어 사용 시 'default'로 설정하세요.
            fallback_mode (LanguageFallbackMode): 요청된 언어로 프롬프트가 없을 때의
                폴백 처리 모드. 단일 언어 사용 시 무관합니다.

        Example:
            >>> # 단일 디렉토리 사용
            >>> factory = PromptFactoryBase("/path/to/prompts", "en")
            >>>
            >>> # 다중 디렉토리 사용 (우선순위 적용)
            >>> factory = PromptFactoryBase(["/base/prompts", "/custom/prompts"], "ko")
            >>>
            >>> # 기본 언어 사용 폴백
            >>> factory = PromptFactoryBase("/prompts", "en", LanguageFallbackMode.USE_DEFAULT_LANG)
        """
        self.lang_code = lang_code
        self._prompt_collection = MultiLangPromptCollection(prompts_dir, fallback_mode=fallback_mode)

    def _render_prompt(self, prompt_name: str, params: dict[str, Any]) -> str:
        """
        프롬프트 템플릿을 파라미터로 렌더링합니다.

        내부적으로 self 파라미터를 제거하고 프롬프트 컬렉션을 통해
        지정된 프롬프트 템플릿을 렌더링합니다.

        Args:
            prompt_name (str): 렌더링할 프롬프트 템플릿의 이름
            params (dict[str, Any]): 템플릿 렌더링에 사용할 파라미터

        Returns:
            str: 렌더링된 프롬프트 템플릿 문자열

        Note:
            이 메서드는 자동 생성되는 프롬프트 팩토리 클래스에서
            내부적으로 사용되며 직접 호출하지 않습니다.
        """
        del params["self"]
        return self._prompt_collection.render_prompt_template(prompt_name, params, lang_code=self.lang_code)

    def _get_prompt_list(self, prompt_name: str) -> PromptList:
        """
        지정된 이름의 프롬프트 리스트를 반환합니다.

        프롬프트 컬렉션에서 지정된 이름의 프롬프트 리스트를 조회합니다.

        Args:
            prompt_name (str): 조회할 프롬프트 리스트의 이름

        Returns:
            PromptList: 요청된 프롬프트 리스트

        Note:
            이 메서드는 자동 생성되는 프롬프트 팩토리 클래스에서
            내부적으로 사용되며 직접 호출하지 않습니다.
        """
        return self._prompt_collection.get_prompt_list(prompt_name, self.lang_code)


def autogenerate_prompt_factory_module(prompts_dir: str, target_module_path: str) -> None:
    """
    주어진 프롬프트 디렉토리를 위한 프롬프트 팩토리 모듈을 자동 생성합니다.

    생성된 PromptFactory 클래스는 애플리케이션에서 프롬프트 템플릿과 리스트를
    검색하고 렌더링하는 중앙 엔트리 포인트 역할을 합니다. 각 프롬프트 템플릿과
    리스트마다 하나의 메서드를 포함하며, 단일 언어 및 다국어 사용 사례 모두에 유용합니다.

    생성되는 코드 구조:
    ```python
    class PromptFactory(PromptFactoryBase):
        def create_{template_name}(self, *, param1: Any, param2: Any) -> str:
            return self._render_prompt('{template_name}', locals())

        def get_list_{list_name}(self) -> PromptList:
            return self._get_prompt_list('{list_name}')
    ```

    Args:
        prompts_dir (str): 프롬프트 템플릿과 리스트가 포함된 디렉토리 경로
        target_module_path (str): 대상 모듈 파일(.py)의 경로

    Note:
        중요: 대상 모듈 파일이 덮어씌워집니다! 기존 내용은 백업하세요.

    Example:
        >>> # 프롬프트 디렉토리로부터 팩토리 생성
        >>> autogenerate_prompt_factory_module("/path/to/prompts", "my_prompts.py")
        >>>
        >>> # 생성된 모듈 사용
        >>> from my_prompts import PromptFactory
        >>> factory = PromptFactory("/path/to/prompts")
        >>> greeting = factory.create_greeting(name="World")
        >>> print(greeting)
        "Hello World!"

    동작 과정:
    1. 지정된 디렉토리에서 MultiLangPromptCollection 생성
    2. 모든 프롬프트 템플릿과 리스트 검색
    3. 각 항목에 대한 메서드 동적 생성
    4. 완전한 Python 모듈 코드 생성 및 파일 쓰기
    """
    generated_code = """
# ruff: noqa
# black: skip
# mypy: ignore-errors

# NOTE: This module is auto-generated from interprompt.autogenerate_prompt_factory_module, do not edit manually!

from interprompt.multilang_prompt import PromptList
from interprompt.prompt_factory import PromptFactoryBase
from typing import Any


class PromptFactory(PromptFactoryBase):
    \"""
    A class for retrieving and rendering prompt templates and prompt lists.
    \"""
"""
    # ---- add methods based on prompt template names and parameters and prompt list names ----
    prompt_collection = MultiLangPromptCollection(prompts_dir)

    for template_name in prompt_collection.get_prompt_template_names():
        template_parameters = prompt_collection.get_prompt_template_parameters(template_name)
        if len(template_parameters) == 0:
            method_params_str = ""
        else:
            method_params_str = ", *, " + ", ".join([f"{param}: Any" for param in template_parameters])
        generated_code += f"""
    def create_{template_name}(self{method_params_str}) -> str:
        return self._render_prompt('{template_name}', locals())
"""
    for prompt_list_name in prompt_collection.get_prompt_list_names():
        generated_code += f"""
    def get_list_{prompt_list_name}(self) -> PromptList:
        return self._get_prompt_list('{prompt_list_name}')
"""
    os.makedirs(os.path.dirname(target_module_path), exist_ok=True)
    with open(target_module_path, "w", encoding="utf-8") as f:
        f.write(generated_code)
    log.info(f"Prompt factory generated successfully in {target_module_path}")
