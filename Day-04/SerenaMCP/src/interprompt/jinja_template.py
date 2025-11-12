"""
InterPrompt Jinja2 템플릿 엔진

이 파일은 InterPrompt 패키지의 Jinja2 템플릿 시스템을 구현합니다.
파라미터화된 템플릿을 생성하고 렌더링하는 기능을 제공합니다.

주요 컴포넌트:
- ParameterizedTemplateInterface: 파라미터화된 템플릿의 인터페이스
- _JinjaEnvProvider: Jinja2 환경을 싱글톤으로 관리하는 프로바이더
- JinjaTemplate: 구체적인 Jinja2 템플릿 구현체

아키텍처:
- 싱글톤 패턴을 사용하여 Jinja2 환경을 효율적으로 관리
- 템플릿 파싱 시점에 파라미터를 자동으로 추출
- 타입 안전성을 위한 제네릭 인터페이스 제공
"""

from typing import Any

import jinja2
import jinja2.meta
import jinja2.nodes
import jinja2.visitor

from interprompt.util.class_decorators import singleton


class ParameterizedTemplateInterface:
    """
    파라미터화된 템플릿의 추상 인터페이스

    이 인터페이스는 템플릿에서 사용되는 파라미터들을 조회할 수 있는
    표준 인터페이스를 정의합니다.
    """

    def get_parameters(self) -> list[str]:
        """
        템플릿에서 사용되는 파라미터 이름들의 리스트를 반환합니다.

        Returns:
            list[str]: 파라미터 이름들의 정렬된 리스트
        """
        ...


@singleton
class _JinjaEnvProvider:
    """
    Jinja2 환경을 싱글톤으로 관리하는 프로바이더 클래스

    이 클래스는 Jinja2.Environment 인스턴스를 싱글톤으로 생성하여
    메모리 효율성을 높이고, 전역 상태를 관리합니다.
    """

    def __init__(self) -> None:
        """
        Jinja2 환경 프로바이더를 초기화합니다.

        초기에는 환경이 생성되지 않은 상태이며, 첫 번째 요청 시점에
        기본 설정의 Jinja2.Environment를 생성합니다.
        """
        self._env: jinja2.Environment | None = None

    def get_env(self) -> jinja2.Environment:
        """
        Jinja2 환경 인스턴스를 반환합니다.

        환경이 아직 생성되지 않은 경우, 기본 설정으로 새로운 환경을
        생성하여 반환합니다. 이후 요청에서는 동일한 인스턴스를 반환합니다.

        Returns:
            jinja2.Environment: 싱글톤 Jinja2 환경 인스턴스
        """
        if self._env is None:
            self._env = jinja2.Environment()
        return self._env


class JinjaTemplate(ParameterizedTemplateInterface):
    """
    Jinja2 기반의 파라미터화된 템플릿 구현체

    이 클래스는 Jinja2 템플릿 엔진을 사용하여 문자열 템플릿을 처리하고,
    템플릿에서 사용되는 파라미터들을 자동으로 추출하는 기능을 제공합니다.

    주요 기능:
    - 템플릿 문자열 파싱 및 파라미터 추출
    - 파라미터를 사용한 템플릿 렌더링
    - 타입 안전성을 위한 인터페이스 구현

    Attributes:
        _template_string (str): 원본 템플릿 문자열
        _template (jinja2.Template): 컴파일된 Jinja2 템플릿
        _parameters (list[str]): 추출된 파라미터 이름들
    """

    def __init__(self, template_string: str) -> None:
        """
        Jinja2 템플릿을 초기화합니다.

        템플릿 문자열을 받아서 Jinja2 템플릿으로 컴파일하고,
        템플릿에서 사용되는 파라미터들을 자동으로 추출합니다.

        Args:
            template_string (str): Jinja2 템플릿 문자열 (예: "Hello {{name}}!")

        동작 과정:
        1. 싱글톤 Jinja2 환경에서 템플릿 컴파일
        2. AST 파싱을 통한 파라미터 추출
        3. 파라미터 이름 정렬
        """
        self._template_string = template_string
        self._template = _JinjaEnvProvider().get_env().from_string(self._template_string)
        parsed_content = self._template.environment.parse(self._template_string)
        self._parameters = sorted(jinja2.meta.find_undeclared_variables(parsed_content))

    def render(self, **params: Any) -> str:
        """
        템플릿을 주어진 파라미터로 렌더링합니다.

        추출된 파라미터들을 사용하여 Jinja2 템플릿을 렌더링합니다.
        파라미터가 누락된 경우 Jinja2에서 자동으로 오류를 발생시킵니다.

        Args:
            **params: 템플릿에서 사용할 파라미터들 (키워드 인자)

        Returns:
            str: 렌더링된 템플릿 결과 문자열

        Example:
            >>> template = JinjaTemplate("Hello {{name}}!")
            >>> result = template.render(name="World")
            >>> print(result)
            "Hello World!"

        Note:
            필요한 파라미터가 누락되면 Jinja2에서 UndefinedError를 발생시킵니다.
            파라미터가 필요한지 확인하려면 get_parameters() 메서드를 사용하세요.
        """
        return self._template.render(**params)

    def get_parameters(self) -> list[str]:
        """
        템플릿에서 추출된 파라미터 이름들의 리스트를 반환합니다.

        템플릿 문자열을 파싱하여 사용되는 모든 파라미터들의 이름을
        정렬된 리스트로 반환합니다. 파라미터의 타입은 알 수 없으며,
        원시 타입, 딕셔너리, 또는 딕셔너리와 유사한 객체가 될 수 있습니다.

        Returns:
            list[str]: 파라미터 이름들의 정렬된 리스트

        Note:
            파라미터 타입은 동적으로 결정되므로 정적으로 알 수 없습니다.
            가능한 타입들: str, int, float, dict, list, 또는 사용자 정의 객체
        """
        return self._parameters
