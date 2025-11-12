"""
serena/util/thread.py - 스레드 및 타임아웃 관련 유틸리티

이 파일은 스레드를 사용하여 함수를 실행하고, 지정된 시간 내에 완료되지 않으면
타임아웃 처리하는 기능을 제공합니다.

주요 클래스:
- TimeoutException: 함수 실행이 타임아웃되었을 때 발생하는 커스텀 예외.
- ExecutionResult: 함수 실행의 결과를 상태(성공, 타임아웃, 예외)와 함께 캡슐화하는 제네릭 클래스.

주요 함수:
- execute_with_timeout: 주어진 함수를 별도의 스레드에서 실행하고, 타임아웃을 적용합니다.

아키텍처 노트:
- `threading.Thread`를 사용하여 대상 함수를 백그라운드에서 실행하고, `thread.join(timeout)`을
  호출하여 타임아웃을 구현합니다. 이 방식은 외부 라이브러리 없이 파이썬 표준 라이브러리만으로
  간단하게 타임아웃을 처리할 수 있게 해줍니다.
- `ExecutionResult` 클래스는 함수 실행의 다양한 결과(성공 값, 타임아웃 예외, 기타 예외)를
  하나의 객체로 일관되게 처리할 수 있도록 하여, 호출하는 쪽의 코드 복잡성을 줄여줍니다.
- 이 유틸리티는 잠재적으로 오래 걸릴 수 있는 작업(예: 네트워크 요청, 복잡한 계산)을
  안전하게 호출하고, 전체 시스템이 멈추는 것을 방지하는 데 사용됩니다.
"""

import threading
from collections.abc import Callable
from enum import Enum
from typing import Generic, TypeVar

from sensai.util.string import ToStringMixin


class TimeoutException(Exception):
    """
    함수 실행이 지정된 시간을 초과했을 때 발생하는 예외.

    Attributes:
        timeout (float): 설정되었던 타임아웃 시간(초).
    """

    def __init__(self, message: str, timeout: float) -> None:
        super().__init__(message)
        self.timeout = timeout


T = TypeVar("T")


class ExecutionResult(Generic[T], ToStringMixin):
    """
    함수 실행의 결과를 상태와 함께 캡슐화하는 제네릭 클래스.

    이 클래스는 함수 실행의 성공, 타임아웃, 또는 예외 발생 상태를
    일관된 방식으로 처리할 수 있도록 돕습니다.

    Attributes:
        result_value (T | None): 함수 실행이 성공했을 때의 반환 값.
        status (ExecutionResult.Status | None): 실행의 현재 상태 (SUCCESS, TIMEOUT, EXCEPTION).
        exception (Exception | None): 타임아웃 또는 다른 예외가 발생했을 때의 예외 객체.
    """

    class Status(Enum):
        """함수 실행의 상태를 나타내는 열거형."""

        SUCCESS = "success"
        TIMEOUT = "timeout"
        EXCEPTION = "error"

    def __init__(self) -> None:
        """ExecutionResult 인스턴스를 초기화합니다."""
        self.result_value: T | None = None
        self.status: ExecutionResult.Status | None = None
        self.exception: Exception | None = None

    def set_result_value(self, value: T) -> None:
        """실행 결과를 성공 상태로 설정합니다."""
        self.result_value = value
        self.status = ExecutionResult.Status.SUCCESS

    def set_timed_out(self, exception: TimeoutException) -> None:
        """실행 결과를 타임아웃 상태로 설정합니다."""
        self.exception = exception
        self.status = ExecutionResult.Status.TIMEOUT

    def set_exception(self, exception: Exception) -> None:
        """실행 결과를 예외 발생 상태로 설정합니다."""
        self.exception = exception
        self.status = ExecutionResult.Status.EXCEPTION


def execute_with_timeout(func: Callable[[], T], timeout: float, function_name: str) -> ExecutionResult[T]:
    """
    지정된 타임아웃 시간 내에 함수를 실행합니다.

    함수를 별도의 데몬 스레드에서 실행하고, 메인 스레드에서는 `timeout` 시간만큼 대기합니다.
    시간이 초과되면 스레드는 계속 실행될 수 있지만, 함수는 타임아웃 처리된 결과를 즉시 반환합니다.

    Args:
        func (Callable[[], T]): 실행할 함수 (인자 없음).
        timeout (float): 타임아웃 시간 (초).
        function_name (str): 오류 메시지에 사용할 함수의 이름.

    Returns:
        ExecutionResult[T]: 함수의 실행 결과(성공, 타임아웃, 예외)를 담은 객체.
    """
    execution_result: ExecutionResult[T] = ExecutionResult()

    def target() -> None:
        """스레드에서 실행될 대상 함수."""
        try:
            value = func()
            execution_result.set_result_value(value)
        except Exception as e:
            execution_result.set_exception(e)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        # 스레드가 여전히 살아있으면 타임아웃으로 간주합니다.
        timeout_exception = TimeoutException(f"'{function_name}' 실행이 {timeout}초 후 타임아웃되었습니다.", timeout)
        execution_result.set_timed_out(timeout_exception)

    return execution_result