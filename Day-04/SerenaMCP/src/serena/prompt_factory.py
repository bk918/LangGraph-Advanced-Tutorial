"""
serena/prompt_factory.py - 프롬프트 팩토리 확장

이 파일은 `interprompt` 라이브러리의 `PromptFactory`를 확장하여
Serena 에이전트의 특정 요구사항에 맞게 프롬프트 템플릿을 관리하고 렌더링하는
`SerenaPromptFactory` 클래스를 정의합니다.

주요 기능:
- 다중 프롬프트 디렉토리 지원: 사용자의 홈 디렉토리에 있는 커스텀 프롬프트와
  패키지 내의 기본 프롬프트를 모두 로드하여, 사용자가 쉽게 프롬프트를
  재정의(override)하고 확장할 수 있도록 합니다.

아키텍처 노트:
- 이 클래스는 `serena.generated.generated_prompt_factory.PromptFactory`를 상속받습니다.
  이 부모 클래스는 `interprompt`의 자동 생성 기능을 통해 만들어지며,
  YAML 파일에 정의된 각 프롬프트에 대한 타입-안전(type-safe) 렌더링 메서드를 제공합니다.
- `__init__` 메서드에서 프롬프트 디렉토리 목록을 `super().__init__`에 전달함으로써,
  `interprompt`의 프롬프트 로딩 메커니즘을 활용하여 계층적인 프롬프트 관리를 구현합니다.
  (사용자 정의 프롬프트가 기본 프롬프트보다 우선순위를 가집니다.)
"""

import os

from serena.constants import PROMPT_TEMPLATES_DIR_IN_USER_HOME, PROMPT_TEMPLATES_DIR_INTERNAL
from serena.generated.generated_prompt_factory import PromptFactory


class SerenaPromptFactory(PromptFactory):
    """
    프롬프트 템플릿과 프롬프트 목록을 검색하고 렌더링하는 클래스입니다.
    """

    def __init__(self) -> None:
        """
        SerenaPromptFactory를 초기화합니다.

        사용자 홈 디렉토리의 프롬프트와 패키지 내부의 기본 프롬프트 디렉토리를
        모두 사용하도록 상위 클래스를 초기화합니다. 이를 통해 사용자는
        기본 프롬프트를 쉽게 재정의하거나 확장할 수 있습니다.
        """
        os.makedirs(PROMPT_TEMPLATES_DIR_IN_USER_HOME, exist_ok=True)
        super().__init__(prompts_dir=[PROMPT_TEMPLATES_DIR_IN_USER_HOME, PROMPT_TEMPLATES_DIR_INTERNAL])