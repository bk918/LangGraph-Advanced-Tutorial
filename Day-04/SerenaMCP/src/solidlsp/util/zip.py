"""
solidlsp/util/zip.py - 안전한 ZIP 압축 해제 유틸리티

이 파일은 ZIP 아카이브를 안전하게 압축 해제하기 위한 `SafeZipExtractor` 클래스를 제공합니다.
Windows의 긴 경로 문제, 권한 보존, 선택적 파일 필터링 등 일반적인 압축 해제 문제를 처리합니다.
"""

import fnmatch
import logging
import os
import sys
import zipfile
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class SafeZipExtractor:
    """
    ZIP 아카이브를 안전하게 압축 해제하기 위한 유틸리티 클래스.

    특징:
    - Windows에서 긴 파일 경로 처리
    - 압축 해제에 실패한 파일을 건너뛰고 나머지 파일 계속 진행
    - 필요한 디렉토리 자동 생성
    - 선택적 포함/제외 패턴 필터
    """

    def __init__(
        self,
        archive_path: Path,
        extract_dir: Path,
        verbose: bool = True,
        include_patterns: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
    ) -> None:
        """
        SafeZipExtractor를 초기화합니다.

        :param archive_path: ZIP 아카이브 파일 경로
        :param extract_dir: 파일이 압축 해제될 디렉토리
        :param verbose: 상태 메시지를 기록할지 여부
        :param include_patterns: 압축 해제할 파일에 대한 glob 패턴 목록 (None = 모든 파일)
        :param exclude_patterns: 건너뛸 파일에 대한 glob 패턴 목록
        """
        self.archive_path = Path(archive_path)
        self.extract_dir = Path(extract_dir)
        self.verbose = verbose
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or []

    def extract_all(self) -> None:
        """
        아카이브의 모든 파일을 압축 해제하고, 실패하는 파일은 건너뜁니다.
        """
        if not self.archive_path.exists():
            raise FileNotFoundError(f"아카이브를 찾을 수 없습니다: {self.archive_path}")

        if self.verbose:
            log.info(f"압축 해제 중: {self.archive_path} -> {self.extract_dir}")

        with zipfile.ZipFile(self.archive_path, "r") as zip_ref:
            for member in zip_ref.infolist():
                if self._should_extract(member.filename):
                    self._extract_member(zip_ref, member)
                elif self.verbose:
                    log.info(f"건너뜀: {member.filename}")

    def _should_extract(self, filename: str) -> bool:
        """
        포함/제외 패턴을 기반으로 파일을 압축 해제해야 하는지 확인합니다.

        :param filename: 아카이브의 파일 이름
        :return: 파일을 압축 해제해야 하면 True
        """
        # include_patterns가 설정된 경우, 하나 이상의 패턴과 일치하는 경우에만 압축 해제
        if self.include_patterns:
            if not any(fnmatch.fnmatch(filename, pattern) for pattern in self.include_patterns):
                return False

        # exclude_patterns가 설정된 경우, 패턴과 일치하면 건너뛰기
        if self.exclude_patterns:
            if any(fnmatch.fnmatch(filename, pattern) for pattern in self.exclude_patterns):
                return False

        return True

    def _extract_member(self, zip_ref: zipfile.ZipFile, member: zipfile.ZipInfo) -> None:
        """
        오류 처리와 함께 아카이브에서 단일 멤버를 압축 해제합니다.

        :param zip_ref: 열려 있는 ZipFile 객체
        :param member: 파일을 나타내는 ZipInfo 객체
        """
        try:
            target_path = self.extract_dir / member.filename

            # 디렉토리 구조가 존재하는지 확인
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Windows에서 긴 경로 처리
            final_path = self._normalize_path(target_path)

            # 파일 압축 해제
            with zip_ref.open(member) as source, open(final_path, "wb") as target:
                target.write(source.read())

            if self.verbose:
                log.info(f"압축 해제됨: {member.filename}")

        except Exception as e:
            log.error(f"{member.filename} 압축 해제 실패: {e}")

    @staticmethod
    def _normalize_path(path: Path) -> Path:
        """
        Windows에서 긴 경로를 처리하도록 경로를 조정합니다.

        :param path: 원본 경로
        :return: 정규화된 경로
        """
        if sys.platform.startswith("win"):
            return Path(rf"\\?{os.path.abspath(path)}")
        return path


# 사용 예시:
# extractor = SafeZipExtractor(
#     archive_path=Path("file.nupkg"),
#     extract_dir=Path("extract_dir"),
#     include_patterns=["*.dll", "*.xml"],
#     exclude_patterns=["*.pdb"]
# )
# extractor.extract_all()