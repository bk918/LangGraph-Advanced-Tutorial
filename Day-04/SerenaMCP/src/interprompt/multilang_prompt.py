"""
InterPrompt 다국어 프롬프트 관리 시스템

이 파일은 InterPrompt 패키지의 다국어 프롬프트 시스템을 구현합니다.
여러 언어로 된 프롬프트 템플릿과 리스트를 관리하고, 언어별 폴백 처리 기능을 제공합니다.

주요 컴포넌트:
- PromptTemplate: 단일 프롬프트 템플릿 (다국어 지원)
- PromptList: 프롬프트 리스트 (다국어 지원)
- MultiLangPromptTemplate: 다국어 프롬프트 템플릿 관리
- MultiLangPromptList: 다국어 프롬프트 리스트 관리
- MultiLangPromptCollection: 다국어 프롬프트 컬렉션 (파일 기반)
- LanguageFallbackMode: 언어 폴백 처리 모드

주요 기능:
- 언어별 프롬프트 템플릿 관리
- YAML 파일로부터 프롬프트 로딩
- 폴백 모드를 통한 유연한 언어 처리
- 타입 안전성을 위한 제네릭 기반 설계

아키텍처:
- Generic 기반의 타입 안전한 컨테이너 사용
- Enum을 통한 폴백 모드 정의
- 빌더 패턴을 활용한 프롬프트 컬렉션 구성
- 파일 시스템 기반의 영속성 관리
"""

import logging
import os
from enum import Enum
from typing import Any, Generic, Literal, TypeVar

import yaml
from sensai.util.string import ToStringMixin

from .jinja_template import JinjaTemplate, ParameterizedTemplateInterface

log = logging.getLogger(__name__)


class PromptTemplate(ToStringMixin, ParameterizedTemplateInterface):
    """
    단일 언어 프롬프트 템플릿 클래스

    Jinja2 기반의 템플릿 문자열을 관리하고 렌더링하는 기능을 제공합니다.
    이름과 템플릿 문자열로 구성되며, 파라미터화된 템플릿을 지원합니다.

    주요 기능:
    - Jinja2 템플릿 렌더링
    - 파라미터 추출 및 관리
    - 문자열 변환 기능

    Attributes:
        name (str): 프롬프트 템플릿의 이름
        _jinja_template (JinjaTemplate): 내부 Jinja2 템플릿 인스턴스
    """
    def __init__(self, name: str, jinja_template_string: str) -> None:
        """
        프롬프트 템플릿을 초기화합니다.

        주어진 이름과 Jinja2 템플릿 문자열로 새로운 프롬프트 템플릿을 생성합니다.
        템플릿 문자열의 앞뒤 공백을 자동으로 제거합니다.

        Args:
            name (str): 프롬프트 템플릿의 고유 이름
            jinja_template_string (str): Jinja2 템플릿 문자열 (예: "Hello {{name}}!")

        Example:
            >>> template = PromptTemplate("greeting", "Hello {{name}}!")
            >>> template.name
            'greeting'
        """
        self.name = name
        self._jinja_template = JinjaTemplate(jinja_template_string.strip())

    def _tostring_exclude_private(self) -> bool:
        """
        문자열 변환 시 private 속성 제외 여부를 결정합니다.

        ToStringMixin을 위한 메서드로, private 속성들을 문자열 변환에서
        제외하여 깔끔한 출력이 되도록 합니다.

        Returns:
            bool: True (private 속성 제외)
        """
        return True

    def render(self, **params: Any) -> str:
        """
        템플릿을 주어진 파라미터로 렌더링합니다.

        내부 Jinja2 템플릿을 사용하여 파라미터들을 치환한 결과를 반환합니다.
        파라미터가 누락된 경우 Jinja2에서 자동으로 오류를 발생시킵니다.

        Args:
            **params: 템플릿에서 사용할 파라미터들 (키워드 인자)

        Returns:
            str: 렌더링된 템플릿 결과 문자열

        Example:
            >>> template = PromptTemplate("greeting", "Hello {{name}}!")
            >>> result = template.render(name="World")
            >>> print(result)
            "Hello World!"
        """
        return self._jinja_template.render(**params)

    def get_parameters(self) -> list[str]:
        """
        템플릿에서 사용되는 파라미터 이름들의 리스트를 반환합니다.

        내부 Jinja2 템플릿에서 추출된 파라미터들을 반환합니다.
        반환되는 리스트는 알파벳순으로 정렬되어 있습니다.

        Returns:
            list[str]: 파라미터 이름들의 정렬된 리스트

        Example:
            >>> template = PromptTemplate("greeting", "Hello {{name}}, you have {{count}} messages")
            >>> template.get_parameters()
            ['count', 'name']
        """
        return self._jinja_template.get_parameters()


class PromptList:
    """
    문자열 아이템들의 리스트를 관리하는 클래스

    여러 개의 문자열 아이템을 목록 형태로 관리하며, 각 아이템을
    적절한 형식으로 출력하는 기능을 제공합니다.

    주요 기능:
    - 문자열 아이템들의 자동 정리 (strip)
    - 불릿 포인트 형태의 문자열 변환
    - 줄바꿈 처리 및 들여쓰기 관리

    Attributes:
        items (list[str]): 정제된 문자열 아이템들의 리스트
    """

    def __init__(self, items: list[str]) -> None:
        """
        프롬프트 리스트를 초기화합니다.

        주어진 아이템 리스트의 각 문자열을 정리하여 저장합니다.
        각 아이템의 앞뒤 공백을 자동으로 제거합니다.

        Args:
            items (list[str]): 원본 문자열 아이템들의 리스트

        Example:
            >>> prompt_list = PromptList(["Item 1", "Item 2", "Item 3"])
            >>> prompt_list.items
            ['Item 1', 'Item 2', 'Item 3']
        """
        self.items = [x.strip() for x in items]

    def to_string(self) -> str:
        """
        리스트를 불릿 포인트 형태의 문자열로 변환합니다.

        각 아이템을 " * " 접두사가 붙은 형태로 변환하며,
        줄바꿈이 포함된 아이템의 경우 적절한 들여쓰기를 적용합니다.

        Returns:
            str: 불릿 포인트 형태로 포맷팅된 문자열

        Example:
            >>> prompt_list = PromptList(["Line 1", "Line 2\nwith break"])
            >>> print(prompt_list.to_string())
             * Line 1
             * Line 2
               with break
        """
        bullet = " * "
        indent = " " * len(bullet)
        items = [x.replace("\n", "\n" + indent) for x in self.items]
        return "\n * ".join(items)


T = TypeVar("T")
DEFAULT_LANG_CODE = "default"
"""
기본 언어 코드

다국어 시스템에서 단일 언어 사용 시 기본값으로 사용되는 언어 코드입니다.
"""


class LanguageFallbackMode(Enum):
    """
    언어 폴백 처리 모드를 정의하는 열거형

    요청된 언어로 된 아이템이 없을 때 어떤 동작을 할지 정의합니다.
    다국어 시스템에서 유연한 언어 처리를 위해 사용됩니다.
    """

    ANY = "any"
    """
    임의의 언어로 된 아이템 반환

    요청된 언어로 된 아이템이 없으면 등록된 첫 번째 언어의 아이템을 반환합니다.
    다국어 환경에서 최대한의 호환성을 제공하는 모드입니다.
    """

    EXCEPTION = "exception"
    """
    예외 발생 모드

    요청된 언어로 된 아이템이 없으면 KeyError 예외를 발생시킵니다.
    엄격한 언어 검증이 필요한 경우에 사용됩니다.
    """

    USE_DEFAULT_LANG = "use_default_lang"
    """
    기본 언어 사용 모드

    요청된 언어로 된 아이템이 없으면 기본 언어(DEFAULT_LANG_CODE)의
    아이템을 반환합니다. 가장 일반적으로 사용되는 폴백 전략입니다.
    """


class _MultiLangContainer(Generic[T], ToStringMixin):
    """
    다국어 아이템 컨테이너 클래스

    동일한 의미를 가지지만 서로 다른 언어로 표현된 아이템들을 관리하는
    제네릭 기반 컨테이너입니다. 단일 언어 사용을 위해 기본 언어 코드를
    항상 사용할 수도 있습니다.

    주요 기능:
    - 언어별 아이템 등록 및 조회
    - 타입 안전성을 위한 제네릭 지원
    - 폴백 모드를 통한 유연한 언어 처리
    - ToStringMixin을 통한 디버깅 지원

    Type Variables:
        T: 컨테이너에 저장될 아이템의 타입

    Attributes:
        name (str): 컨테이너의 이름 (디버깅용)
        _lang2item (dict[str, T]): 언어 코드 -> 아이템 매핑
    """

    def __init__(self, name: str) -> None:
        """
        다국어 컨테이너를 초기화합니다.

        주어진 이름으로 새로운 컨테이너를 생성하고, 내부 언어-아이템
        매핑을 위한 빈 딕셔너리를 초기화합니다.

        Args:
            name (str): 컨테이너의 이름 (디버깅 및 로깅용)

        Example:
            >>> container = _MultiLangContainer("greetings")
            >>> container.name
            'greetings'
        """
        self.name = name
        self._lang2item: dict[str, T] = {}
        """언어 코드에서 아이템으로의 매핑 딕셔너리"""

    def _tostring_excludes(self) -> list[str]:
        """
        문자열 변환에서 제외할 속성들을 반환합니다.

        ToStringMixin을 위한 메서드로, 내부 상태를 직접 노출하지 않도록
        _lang2item을 제외합니다.

        Returns:
            list[str]: 제외할 속성 이름들의 리스트
        """
        return ["lang2item"]

    def _tostring_additional_entries(self) -> dict[str, Any]:
        """
        문자열 변환에 추가할 정보들을 반환합니다.

        ToStringMixin을 위한 메서드로, 등록된 언어 코드들을
        추가 정보로 제공합니다.

        Returns:
            dict[str, Any]: 추가 정보 딕셔너리
        """
        return dict(languages=list(self._lang2item.keys()))

    def get_language_codes(self) -> list[str]:
        """
        컨테이너에 등록된 언어 코드들의 리스트를 반환합니다.

        현재 컨테이너에 아이템이 등록된 모든 언어 코드들을
        반환합니다. 반환되는 리스트는 특정 순서가 보장되지 않습니다.

        Returns:
            list[str]: 등록된 언어 코드들의 리스트

        Example:
            >>> container.add_item("Hello", "en")
            >>> container.add_item("안녕", "ko")
            >>> container.get_language_codes()
            ['en', 'ko']
        """
        return list(self._lang2item.keys())

    def add_item(self, item: T, lang_code: str = DEFAULT_LANG_CODE, allow_overwrite: bool = False) -> None:
        """
        컨테이너에 아이템을 추가합니다.

        동일한 의미를 가지지만 다른 언어로 표현된 아이템을 컨테이너에 등록합니다.
        기본적으로 중복 등록을 허용하지 않으며, 필요시 allow_overwrite를 True로 설정하면
        기존 아이템을 덮어쓸 수 있습니다.

        Args:
            item (T): 추가할 아이템
            lang_code (str): 아이템을 등록할 언어 코드. 기본값은 DEFAULT_LANG_CODE
            allow_overwrite (bool): 기존 아이템을 덮어쓸지 여부

        Raises:
            KeyError: allow_overwrite가 False이고 동일한 언어로 이미 아이템이 등록된 경우

        Example:
            >>> container = _MultiLangContainer("greetings")
            >>> container.add_item("Hello", "en")
            >>> container.add_item("안녕", "ko")
            >>> container.add_item("Bonjour", "fr", allow_overwrite=True)
        """
        if not allow_overwrite and lang_code in self._lang2item:
            raise KeyError(f"Item for language '{lang_code}' already registered for name '{self.name}'")
        self._lang2item[lang_code] = item

    def has_item(self, lang_code: str = DEFAULT_LANG_CODE) -> bool:
        """
        주어진 언어 코드로 된 아이템이 있는지 확인합니다.

        컨테이너에 특정 언어로 된 아이템이 등록되어 있는지 확인합니다.

        Args:
            lang_code (str): 확인할 언어 코드

        Returns:
            bool: 아이템이 존재하면 True, 없으면 False

        Example:
            >>> container.add_item("Hello", "en")
            >>> container.has_item("en")
            True
            >>> container.has_item("ko")
            False
        """
        return lang_code in self._lang2item

    def get_item(self, lang: str = DEFAULT_LANG_CODE, fallback_mode: LanguageFallbackMode = LanguageFallbackMode.EXCEPTION) -> T:
        """
        주어진 언어로 된 아이템을 반환합니다.

        지정된 언어로 된 아이템을 조회하며, 아이템이 없으면 폴백 모드에 따라
        적절한 처리를 수행합니다. 폴백 모드는 LanguageFallbackMode 열거형을 통해
        정의되며, 예외 발생, 임의 언어 사용, 기본 언어 사용 등의 전략을 제공합니다.

        Args:
            lang (str): 조회할 언어 코드
            fallback_mode (LanguageFallbackMode): 아이템이 없을 때의 처리 전략

        Returns:
            T: 요청된 언어 또는 폴백 전략에 따른 아이템

        Raises:
            KeyError: 폴백 모드가 EXCEPTION이고 아이템이 없는 경우

        Examples:
            >>> container.add_item("Hello", "en")
            >>> container.add_item("안녕", "default")

            # 기본 언어 조회
            >>> container.get_item("en")
            'Hello'

            # 폴백 모드: 기본 언어 사용
            >>> container.get_item("ko", LanguageFallbackMode.USE_DEFAULT_LANG)
            '안녕'

            # 폴백 모드: 임의 언어 사용
            >>> container.get_item("fr", LanguageFallbackMode.ANY)
            'Hello'  # 또는 '안녕' (등록된 첫 번째 아이템)
        """
        try:
            return self._lang2item[lang]
        except KeyError as outer_e:
            if fallback_mode == LanguageFallbackMode.EXCEPTION:
                raise KeyError(f"Item for language '{lang}' not found for name '{self.name}'") from outer_e
            if fallback_mode == LanguageFallbackMode.ANY:
                try:
                    return next(iter(self._lang2item.values()))
                except StopIteration as e:
                    raise KeyError(f"No items registered for any language in container '{self.name}'") from e
            if fallback_mode == LanguageFallbackMode.USE_DEFAULT_LANG:
                try:
                    return self._lang2item[DEFAULT_LANG_CODE]
                except KeyError as e:
                    raise KeyError(
                        f"Item not found neither for {lang=} nor for the default language '{DEFAULT_LANG_CODE}' in container '{self.name}'"
                    ) from e

    def __len__(self) -> int:
        """
        컨테이너에 등록된 아이템의 개수를 반환합니다.

        현재 컨테이너에 등록된 언어-아이템 쌍의 개수를 반환합니다.

        Returns:
            int: 등록된 아이템의 개수

        Example:
            >>> container.add_item("Hello", "en")
            >>> container.add_item("안녕", "ko")
            >>> len(container)
            2
        """
        return len(self._lang2item)


class MultiLangPromptTemplate(ParameterizedTemplateInterface):
    """
    다국어 프롬프트 템플릿 관리 클래스

    여러 언어로 된 프롬프트 템플릿들을 관리하는 클래스입니다.
    모든 언어의 템플릿은 동일한 파라미터 구조를 가져야 합니다.
    _MultiLangContainer를 사용하여 타입 안전한 언어별 템플릿 관리를 제공합니다.

    주요 기능:
    - 언어별 프롬프트 템플릿 등록 및 관리
    - 파라미터 일관성 검증
    - 폴백 모드를 통한 유연한 언어 처리
    - 타입 안전성을 위한 제네릭 기반 설계

    Attributes:
        _prompts_container (_MultiLangContainer[PromptTemplate]): 내부 프롬프트 컨테이너

    Note:
        모든 언어의 프롬프트 템플릿은 반드시 동일한 파라미터 구조를 가져야 합니다.
        파라미터 불일치 시 ValueError가 발생합니다.
    """

    def __init__(self, name: str) -> None:
        """
        다국어 프롬프트 템플릿을 초기화합니다.

        주어진 이름으로 새로운 다국어 프롬프트 템플릿 관리자를 생성하고,
        내부에 _MultiLangContainer를 초기화합니다.

        Args:
            name (str): 프롬프트 템플릿의 이름

        Example:
            >>> template = MultiLangPromptTemplate("greeting")
            >>> template.name
            'greeting'
        """
        self._prompts_container = _MultiLangContainer[PromptTemplate](name)

    def __len__(self) -> int:
        """
        등록된 프롬프트 템플릿의 개수를 반환합니다.

        현재 등록된 언어-프롬프트 템플릿 쌍의 개수를 반환합니다.

        Returns:
            int: 등록된 프롬프트 템플릿의 개수

        Example:
            >>> template.add_prompt_template(PromptTemplate("greeting", "Hello {{name}}!"), "en")
            >>> template.add_prompt_template(PromptTemplate("greeting", "안녕 {{name}}!"), "ko")
            >>> len(template)
            2
        """
        return len(self._prompts_container)

    @property
    def name(self) -> str:
        """
        프롬프트 템플릿의 이름을 반환합니다.

        Returns:
            str: 프롬프트 템플릿의 이름
        """
        return self._prompts_container.name

    def add_prompt_template(
        self, prompt_template: PromptTemplate, lang_code: str = DEFAULT_LANG_CODE, allow_overwrite: bool = False
    ) -> None:
        """
        새로운 언어에 대한 프롬프트 템플릿을 추가합니다.

        지정된 언어 코드로 새로운 프롬프트 템플릿을 등록합니다.
        모든 언어의 템플릿은 동일한 파라미터 구조를 가져야 하므로,
        새로 추가되는 템플릿의 파라미터는 기존 템플릿과 일치해야 합니다.

        Args:
            prompt_template (PromptTemplate): 추가할 프롬프트 템플릿
            lang_code (str): 프롬프트 템플릿을 등록할 언어 코드
            allow_overwrite (bool): 기존 항목을 덮어쓸지 여부

        Raises:
            ValueError: 새 템플릿의 파라미터가 기존 템플릿과 일치하지 않는 경우
            KeyError: allow_overwrite가 False이고 동일 언어로 이미 템플릿이 등록된 경우

        Example:
            >>> en_template = PromptTemplate("greeting", "Hello {{name}}!")
            >>> ko_template = PromptTemplate("greeting", "안녕 {{name}}!")
            >>> template.add_prompt_template(en_template, "en")
            >>> template.add_prompt_template(ko_template, "ko")
        """
        incoming_parameters = prompt_template.get_parameters()
        if len(self) > 0:
            parameters = self.get_parameters()
            if parameters != incoming_parameters:
                raise ValueError(
                    f"Cannot add prompt template for language '{lang_code}' to MultiLangPromptTemplate '{self.name}'"
                    f"because the parameters are inconsistent: {parameters} vs {prompt_template.get_parameters()}"
                )

        self._prompts_container.add_item(prompt_template, lang_code, allow_overwrite)

    def get_prompt_template(
        self, lang_code: str = DEFAULT_LANG_CODE, fallback_mode: LanguageFallbackMode = LanguageFallbackMode.EXCEPTION
    ) -> PromptTemplate:
        """
        지정된 언어로 된 프롬프트 템플릿을 반환합니다.

        언어 코드와 폴백 모드를 사용하여 적절한 프롬프트 템플릿을 조회합니다.
        내부적으로 _MultiLangContainer의 get_item 메서드를 사용합니다.

        Args:
            lang_code (str): 조회할 언어 코드
            fallback_mode (LanguageFallbackMode): 아이템이 없을 때의 처리 전략

        Returns:
            PromptTemplate: 요청된 언어의 프롬프트 템플릿

        Raises:
            KeyError: 폴백 모드가 EXCEPTION이고 템플릿이 없는 경우

        Example:
            >>> template.add_prompt_template(PromptTemplate("greeting", "Hello {{name}}!"), "en")
            >>> en_template = template.get_prompt_template("en")
            >>> result = en_template.render(name="World")
            "Hello World!"
        """
        return self._prompts_container.get_item(lang_code, fallback_mode)

    def get_parameters(self) -> list[str]:
        """
        모든 프롬프트 템플릿의 공통 파라미터들을 반환합니다.

        등록된 모든 프롬프트 템플릿이 동일한 파라미터 구조를 가져야 하므로,
        첫 번째 템플릿의 파라미터를 반환합니다. 템플릿이 하나도 등록되지 않은
        경우 RuntimeError를 발생시킵니다.

        Returns:
            list[str]: 파라미터 이름들의 정렬된 리스트

        Raises:
            RuntimeError: 프롬프트 템플릿이 하나도 등록되지 않은 경우

        Example:
            >>> template.add_prompt_template(PromptTemplate("greeting", "Hello {{name}}!"), "en")
            >>> template.get_parameters()
            ['name']
        """
        if len(self) == 0:
            raise RuntimeError(
                f"No prompt templates registered for MultiLangPromptTemplate '{self.name}', make sure to register a prompt template before accessing the parameters"
            )
        first_prompt_template = next(iter(self._prompts_container._lang2item.values()))
        return first_prompt_template.get_parameters()

    def render(
        self,
        params: dict[str, Any],
        lang_code: str = DEFAULT_LANG_CODE,
        fallback_mode: LanguageFallbackMode = LanguageFallbackMode.EXCEPTION,
    ) -> str:
        """
        지정된 언어로 된 프롬프트 템플릿을 파라미터로 렌더링합니다.

        언어 코드와 폴백 모드를 사용하여 적절한 프롬프트 템플릿을 조회하고,
        주어진 파라미터로 렌더링한 결과를 반환합니다.

        Args:
            params (dict[str, Any]): 템플릿 렌더링에 사용할 파라미터들
            lang_code (str): 사용할 언어 코드
            fallback_mode (LanguageFallbackMode): 아이템이 없을 때의 처리 전략

        Returns:
            str: 렌더링된 프롬프트 템플릿 문자열

        Example:
            >>> template.add_prompt_template(PromptTemplate("greeting", "Hello {{name}}!"), "en")
            >>> result = template.render({"name": "World"}, "en")
            >>> print(result)
            "Hello World!"
        """
        prompt_template = self.get_prompt_template(lang_code, fallback_mode)
        return prompt_template.render(**params)

    def has_item(self, lang_code: str = DEFAULT_LANG_CODE) -> bool:
        """
        지정된 언어로 된 프롬프트 템플릿이 있는지 확인합니다.

        컨테이너에 특정 언어로 된 프롬프트 템플릿이 등록되어 있는지 확인합니다.

        Args:
            lang_code (str): 확인할 언어 코드

        Returns:
            bool: 프롬프트 템플릿이 존재하면 True, 없으면 False

        Example:
            >>> template.add_prompt_template(PromptTemplate("greeting", "Hello {{name}}!"), "en")
            >>> template.has_item("en")
            True
            >>> template.has_item("ko")
            False
        """
        return self._prompts_container.has_item(lang_code)


class MultiLangPromptList(_MultiLangContainer[PromptList]):
    """
    다국어 프롬프트 리스트 관리 클래스

    PromptList를 상속한 _MultiLangContainer를 사용하여
    여러 언어로 된 프롬프트 리스트들을 관리합니다.

    Note:
        _MultiLangContainer[PromptList]의 모든 기능을 그대로 상속받아 사용합니다.
        추가적인 메서드가 필요하지 않으므로 pass로 구현됩니다.
    """
    pass


class MultiLangPromptCollection:
    """
    다국어 프롬프트 컬렉션 관리 클래스

    여러 언어로 된 프롬프트 템플릿과 프롬프트 리스트의 컬렉션을 관리하는 메인 클래스입니다.
    초기화 시점에 주어진 디렉토리의 YAML 파일들로부터 모든 데이터를 직접 읽어옵니다.
    따라서 프롬프트 컬렉션당 하나의 디렉토리를 관리하는 것을 가정합니다.

    YAML 파일 형식:
    ```yaml
    lang: <language_code>  # 선택사항, 기본값은 "default"
    prompts:
      <prompt_name>:
        <prompt_template_string>  # Jinja2 템플릿 문자열
      <prompt_list_name>: [<prompt_string_1>, <prompt_string_2>, ...]
    ```

    주요 기능:
    - YAML 파일로부터 다국어 프롬프트 자동 로딩
    - 다중 디렉토리 지원 (우선순위 기반)
    - 이름 충돌 처리 및 검증
    - 폴백 모드를 통한 유연한 언어 처리

    주요 특징:
    - 여러 언어의 프롬프트 템플릿은 반드시 동일한 Jinja2 파라미터 구조를 가져야 합니다
    - 동일 언어 내에서 프롬프트 이름은 유니크해야 합니다
    - 첫 번째 디렉토리에서 이름 충돌 시 오류 발생, 이후 디렉토리에서는 스킵

    Attributes:
        _multi_lang_prompt_templates (dict[str, MultiLangPromptTemplate]): 프롬프트 템플릿 컬렉션
        _multi_lang_prompt_lists (dict[str, MultiLangPromptList]): 프롬프트 리스트 컬렉션
        fallback_mode (LanguageFallbackMode): 언어 폴백 처리 모드

    Note:
        다국어 프롬프트 템플릿의 Jinja2 파라미터는 모든 언어에서 동일해야 합니다.
        파라미터 불일치 시 예외가 발생합니다.
    """

    def __init__(self, prompts_dir: str | list[str], fallback_mode: LanguageFallbackMode = LanguageFallbackMode.EXCEPTION) -> None:
        """
        다국어 프롬프트 컬렉션을 초기화합니다.

        주어진 디렉토리(또는 디렉토리 리스트)로부터 YAML 파일들을 읽어와
        프롬프트 템플릿과 리스트를 로드합니다. 여러 디렉토리가 제공되면
        왼쪽부터 오른쪽으로 우선순위를 적용합니다.

        Args:
            prompts_dir (str | list[str]): 프롬프트 파일들이 있는 디렉토리 경로.
                리스트가 제공되면 왼쪽부터 오른쪽으로 우선순위를 적용하며,
                원하는 템플릿을 포함하는 첫 번째 디렉토리가 우선됩니다.
            fallback_mode (LanguageFallbackMode): 요청된 언어로 프롬프트가 없을 때의
                폴백 처리 모드. 초기화 후에도 변경 가능합니다.

        동작 방식:
        1. 첫 번째 디렉토리에서 이름 충돌 검사와 함께 프롬프트 로드
        2. 이후 디렉토리들은 기존 프롬프트에 우선하여 로드 (충돌 시 스킵)
        3. 모든 디렉토리에서 내부 충돌은 검증하지 않음 (올바른 구조 가정)

        Example:
            >>> # 단일 디렉토리
            >>> collection = MultiLangPromptCollection("/path/to/prompts")

            >>> # 다중 디렉토리 (우선순위: base > custom)
            >>> collection = MultiLangPromptCollection(["/base/prompts", "/custom/prompts"])

            >>> # 기본 언어 사용 폴백 모드
            >>> collection = MultiLangPromptCollection("/prompts", LanguageFallbackMode.USE_DEFAULT_LANG)
        """
        self._multi_lang_prompt_templates: dict[str, MultiLangPromptTemplate] = {}
        self._multi_lang_prompt_lists: dict[str, MultiLangPromptList] = {}
        if isinstance(prompts_dir, str):
            prompts_dir = [prompts_dir]

        # 디렉토리별 프롬프트 로드 (왼쪽부터 우선순위 적용)
        # 첫 번째 디렉토리에서 이름 충돌 시 오류 발생 (오류 방지 목적)
        # 이후 디렉토리들에서는 충돌 시 새로운 값 무시
        # 이후 디렉토리들에 대한 내부 충돌 검사는 하지 않음 (올바른 구조 가정)
        first_prompts_dir, fallback_prompt_dirs = prompts_dir[0], prompts_dir[1:]
        self._load_from_disc(first_prompts_dir, on_name_collision="raise")
        for fallback_prompt_dir in fallback_prompt_dirs:
            # 이미 로드된 프롬프트가 우선순위 가짐
            self._load_from_disc(fallback_prompt_dir, on_name_collision="skip")

        self.fallback_mode = fallback_mode

    def _add_prompt_template(
        self,
        name: str,
        template_str: str,
        lang_code: str = DEFAULT_LANG_CODE,
        on_name_collision: Literal["skip", "overwrite", "raise"] = "raise",
    ) -> None:
        """
        :param name: name of the prompt template
        :param template_str: the Jinja template string
        :param lang_code: the language code for which to add the prompt template.
        :param on_name_collision: how to deal with name/lang_code collisions
        """
        allow_overwrite = False
        prompt_template = PromptTemplate(name, template_str)
        mlpt = self._multi_lang_prompt_templates.get(name)
        if mlpt is None:
            mlpt = MultiLangPromptTemplate(name)
            self._multi_lang_prompt_templates[name] = mlpt
        if mlpt.has_item(lang_code):
            if on_name_collision == "raise":
                raise KeyError(f"Prompt '{name}' for {lang_code} already exists!")
            if on_name_collision == "skip":
                log.debug(f"Skipping prompt '{name}' since it already exists.")
                return
            elif on_name_collision == "overwrite":
                allow_overwrite = True
        mlpt.add_prompt_template(prompt_template, lang_code=lang_code, allow_overwrite=allow_overwrite)

    def _add_prompt_list(
        self,
        name: str,
        prompt_list: list[str],
        lang_code: str = DEFAULT_LANG_CODE,
        on_name_collision: Literal["skip", "overwrite", "raise"] = "raise",
    ) -> None:
        """
        :param name: name of the prompt list
        :param prompt_list: a list of prompts
        :param lang_code: the language code for which to add the prompt list.
        :param on_name_collision: how to deal with name/lang_code collisions
        """
        allow_overwrite = False
        multilang_prompt_list = self._multi_lang_prompt_lists.get(name)
        if multilang_prompt_list is None:
            multilang_prompt_list = MultiLangPromptList(name)
            self._multi_lang_prompt_lists[name] = multilang_prompt_list
        if multilang_prompt_list.has_item(lang_code):
            if on_name_collision == "raise":
                raise KeyError(f"Prompt '{name}' for {lang_code} already exists!")
            if on_name_collision == "skip":
                log.debug(f"Skipping prompt '{name}' since it already exists.")
                return
            elif on_name_collision == "overwrite":
                allow_overwrite = True
        multilang_prompt_list.add_item(PromptList(prompt_list), lang_code=lang_code, allow_overwrite=allow_overwrite)

    def _load_from_disc(self, prompts_dir: str, on_name_collision: Literal["skip", "overwrite", "raise"] = "raise") -> None:
        """Loads all prompt templates and prompt lists from yaml files in the given directory.

        :param prompts_dir:
        :param on_name_collision: how to deal with name/lang_code collisions
        """
        for fn in os.listdir(prompts_dir):
            if not fn.endswith((".yml", ".yaml")):
                log.debug(f"Skipping non-YAML file: {fn}")
                continue
            path = os.path.join(prompts_dir, fn)
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            try:
                prompts_data = data["prompts"]
            except KeyError as e:
                raise KeyError(f"Invalid yaml structure (missing 'prompts' key) in file {path}") from e

            lang_code = prompts_data.get("lang", DEFAULT_LANG_CODE)
            # add the data to the collection
            for prompt_name, prompt_template_or_list in prompts_data.items():
                if isinstance(prompt_template_or_list, list):
                    self._add_prompt_list(prompt_name, prompt_template_or_list, lang_code=lang_code, on_name_collision=on_name_collision)
                elif isinstance(prompt_template_or_list, str):
                    self._add_prompt_template(
                        prompt_name, prompt_template_or_list, lang_code=lang_code, on_name_collision=on_name_collision
                    )
                else:
                    raise ValueError(
                        f"Invalid prompt type for {prompt_name} in file {path} (should be str or list): {prompt_template_or_list}"
                    )

    def get_prompt_template_names(self) -> list[str]:
        return list(self._multi_lang_prompt_templates.keys())

    def get_prompt_list_names(self) -> list[str]:
        return list(self._multi_lang_prompt_lists.keys())

    def __len__(self) -> int:
        return len(self._multi_lang_prompt_templates)

    def get_multilang_prompt_template(self, prompt_name: str) -> MultiLangPromptTemplate:
        """The MultiLangPromptTemplate object for the given prompt name. For single-language use cases, you should use the `get_prompt_template` method instead."""
        return self._multi_lang_prompt_templates[prompt_name]

    def get_multilang_prompt_list(self, prompt_name: str) -> MultiLangPromptList:
        return self._multi_lang_prompt_lists[prompt_name]

    def get_prompt_template(
        self,
        prompt_name: str,
        lang_code: str = DEFAULT_LANG_CODE,
    ) -> PromptTemplate:
        """The PromptTemplate object for the given prompt name and language code."""
        return self.get_multilang_prompt_template(prompt_name).get_prompt_template(lang_code=lang_code, fallback_mode=self.fallback_mode)

    def get_prompt_template_parameters(self, prompt_name: str) -> list[str]:
        """The parameters of the PromptTemplate object for the given prompt name."""
        return self.get_multilang_prompt_template(prompt_name).get_parameters()

    def get_prompt_list(self, prompt_name: str, lang_code: str = DEFAULT_LANG_CODE) -> PromptList:
        """The PromptList object for the given prompt name and language code."""
        return self.get_multilang_prompt_list(prompt_name).get_item(lang_code)

    def _has_prompt_list(self, prompt_name: str, lang_code: str = DEFAULT_LANG_CODE) -> bool:
        multi_lang_prompt_list = self._multi_lang_prompt_lists.get(prompt_name)
        if multi_lang_prompt_list is None:
            return False
        return multi_lang_prompt_list.has_item(lang_code)

    def _has_prompt_template(self, prompt_name: str, lang_code: str = DEFAULT_LANG_CODE) -> bool:
        multi_lang_prompt_template = self._multi_lang_prompt_templates.get(prompt_name)
        if multi_lang_prompt_template is None:
            return False
        return multi_lang_prompt_template.has_item(lang_code)

    def render_prompt_template(
        self,
        prompt_name: str,
        params: dict[str, Any],
        lang_code: str = DEFAULT_LANG_CODE,
    ) -> str:
        """Renders the prompt template for the given prompt name and language code."""
        return self.get_prompt_template(prompt_name, lang_code=lang_code).render(**params)
