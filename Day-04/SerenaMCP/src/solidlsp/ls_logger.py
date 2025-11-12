"""
solidlsp/ls_logger.py - SolidLSP 로거 모듈

이 모듈은 `solidlsp` 라이브러리 전체에서 사용될 로깅 관련 클래스를 제공합니다.
로그 메시지를 구조화된 형식(JSON)으로 출력하는 기능을 지원합니다.
"""

import inspect
import logging
from datetime import datetime

from pydantic import BaseModel


class LogLine(BaseModel):
    """
    SolidLSP 로그의 한 줄을 나타냅니다.
    로그 정보를 구조화된 데이터로 관리하기 위한 Pydantic 모델입니다.
    """

    time: str
    level: str
    caller_file: str
    caller_name: str
    caller_line: int
    message: str


class LanguageServerLogger:
    """
    SolidLSP를 위한 로거 클래스.

    표준 `logging` 모듈을 래핑하여, JSON 형식 출력 옵션과
    호출자 정보(파일, 함수, 줄 번호)를 자동으로 포함하는 기능을 제공합니다.
    """

    def __init__(self, json_format: bool = False, log_level: int = logging.INFO) -> None:
        self.logger = logging.getLogger("solidlsp")
        self.logger.setLevel(log_level)
        self.json_format = json_format

    def log(self, debug_message: str, level: int, sanitized_error_message: str = "", stacklevel: int = 2) -> None:
        """
        로거를 사용하여 디버그 및 정제된 메시지를 기록합니다.

        Args:
            debug_message (str): 기록할 주 메시지.
            level (int): 로그 레벨 (예: logging.INFO).
            sanitized_error_message (str): 민감한 정보가 제거된 오류 메시지 (현재 사용되지 않음).
            stacklevel (int): 올바른 호출자 정보를 얻기 위한 스택 레벨.
        """
        debug_message = debug_message.replace("'", '"').replace("\n", " ")
        sanitized_error_message = sanitized_error_message.replace("'", '"').replace("\n", " ")

        # 호출자 정보 수집
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        caller_file = calframe[1][1].split("/")[-1]
        caller_line = calframe[1][2]
        caller_name = calframe[1][3]

        if self.json_format:
            # 디버그 로그 라인 구성
            debug_log_line = LogLine(
                time=str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                level=logging.getLevelName(level),
                caller_file=caller_file,
                caller_name=caller_name,
                caller_line=caller_line,
                message=debug_message,
            )

            self.logger.log(
                level=level,
                msg=debug_log_line.json(),
                stacklevel=stacklevel,
            )
        else:
            self.logger.log(level, debug_message, stacklevel=stacklevel)