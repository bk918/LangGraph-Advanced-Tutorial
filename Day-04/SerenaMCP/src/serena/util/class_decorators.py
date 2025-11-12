"""
serena/util/class_decorators.py - 클래스 데코레이터 유틸리티

이 파일은 클래스에 적용할 수 있는 유용한 데코레이터들을 포함합니다.

주요 함수:
- singleton: 클래스를 싱글톤 패턴으로 만들어, 애플리케이션 내에서 단 하나의 인스턴스만
  생성되도록 보장하는 데코레이터입니다.

참고:
- 이 파일의 `singleton` 데코레이터는 `interprompt.class_decorators`에 있는 것과 동일한 복사본입니다.
  `serena` 패키지가 `interprompt`에 대한 의존성을 갖지 않도록 하기 위해 중복으로 유지합니다.
"""

from typing import Any


def singleton(cls: type[Any]) -> Any:
    """
    클래스를 싱글톤으로 만드는 데코레이터입니다.

    이 데코레이터가 적용된 클래스는 최초 호출 시에만 인스턴스를 생성하고,
    이후의 모든 호출에서는 기존에 생성된 인스턴스를 반환합니다.

    Args:
        cls (type[Any]): 싱글톤으로 만들 클래스.

    Returns:
        Any: 클래스의 유일한 인스턴스를 반환하는 함수.

    Example:
        @singleton
        class MySingletonClass:
            def __init__(self):
                print("인스턴스 생성")

        a = MySingletonClass()  # "인스턴스 생성" 출력
        b = MySingletonClass()  # 아무것도 출력되지 않음
        assert a is b
    """
    instance = None

    def get_instance(*args: Any, **kwargs: Any) -> Any:
        """클래스 인스턴스를 가져오거나, 없으면 새로 생성합니다."""
        nonlocal instance
        if instance is None:
            instance = cls(*args, **kwargs)
        return instance

    return get_instance