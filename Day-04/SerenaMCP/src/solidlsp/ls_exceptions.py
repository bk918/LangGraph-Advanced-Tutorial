"""
solidlsp/ls_exceptions.py - SolidLSP 예외 클래스

이 모듈은 `solidlsp` 프레임워크에서 발생하는 사용자 정의 예외들을 포함합니다.
"""


class SolidLSPException(Exception):
    """
    SolidLSP 프레임워크의 기본 예외 클래스.

    모든 `solidlsp` 관련 오류는 이 예외를 상속받아, 일관된 오류 처리를 가능하게 합니다.
    원인이 되는(cause) 예외를 포함할 수 있어, 오류 추적에 용이합니다.
    """

    def __init__(self, message: str, cause: Exception | None = None):
        """
        주어진 메시지로 예외를 초기화합니다.

        :param message: 예외를 설명하는 메시지
        :param cause: 이 예외를 발생시킨 원본 예외 (있는 경우).
            요청 처리 중 발생한 예외의 경우, 일반적으로 다음과 같습니다:
                * LSP 서버가 반환한 오류에 대한 LSPError
                * 언어 서버가 예기치 않게 종료되어 발생한 오류에 대한 LanguageServerTerminatedException.
        """
        self.cause = cause
        super().__init__(message)

    def is_language_server_terminated(self):
        """
        :return: 원인 예외가 LanguageServerTerminatedException의 인스턴스인 경우,
            언어 서버가 종료되어 예외가 발생했으면 True를 반환합니다.
        """
        from .ls_handler import LanguageServerTerminatedException

        return isinstance(self.cause, LanguageServerTerminatedException)

    def __str__(self) -> str:
        """
        예외의 문자열 표현을 반환합니다.
        """
        s = super().__str__()
        if self.cause:
            if "\n" in s:
                s += "\n"
            else:
                s += " "
            s += f"(원인: {self.cause})"
        return s

"""