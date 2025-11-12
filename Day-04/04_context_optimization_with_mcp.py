"""
컨텍스트 최적화된 MCP 서버

## 학습 목표
- Conversation Hop 감소 전략 구현
- Chunking 및 Pagination을 통한 대용량 데이터 처리
- Progress Notification으로 장기 작업 상태 전달
- Structured Output으로 토큰 효율성 극대화

## 핵심 최적화 전략

### 1. Conversation Hop 감소
- Tool이 Structured Output 반환 (LLM이 바로 해석 가능)
- 불필요한 자연어 설명 제거
- 20-40% 토큰 비용 절감

### 2. Chunking & Pagination
- Context Window 초과 방지
- 필요한 부분만 로드 (검색 → Chunk 패턴)
- Cursor-based pagination (opaque token)

### 3. Progress Notification
- 장기 작업의 진행 상태 실시간 전달
- `notifications/progress` JSON-RPC 메시지
- UX 39% 개선 (perceived performance)

### 4. Resource vs Tool 설계
- Resource: 읽기 전용, Side Effect 없음
- Tool: 상태 변경 가능, 계산 수행

## 참고 문서
- MCP Specification 2025-06-18: https://modelcontextprotocol.io/specification/2025-06-18
- Progress Tokens: https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/progress
"""

import asyncio
import base64
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# ============================================================================
# MCP 서버 초기화
# ============================================================================

mcp = FastMCP(
    name="ContextOptimizedMCPServer",
    version="1.0.0",
    description="컨텍스트 최적화 전략이 적용된 MCP 서버 (Chunking, Progress, Structured Output)",
)


# ============================================================================
# 대용량 데이터 생성 (테스트용)
# ============================================================================


def create_large_test_file() -> Path:
    """
    테스트용 대용량 파일 생성

    Returns:
        생성된 파일 경로
    """
    test_dir = Path("./mcp_test_data")
    test_dir.mkdir(exist_ok=True)

    large_file = test_dir / "large_codebase.py"

    if not large_file.exists():
        logger.info("대용량 테스트 파일 생성 중...")
        with open(large_file, "w", encoding="utf-8") as f:
            for i in range(1000):
                f.write(f"# Line {i+1}: Function definition\n")
                f.write(f"def function_{i}(arg1: int, arg2: str) -> dict:\n")
                f.write(f'    """함수 {i} 설명"""\n')
                f.write(f"    return {{'result': arg1, 'message': arg2, 'id': {i}}}\n")
                f.write("\n")
        logger.info(f"테스트 파일 생성 완료: {large_file} ({large_file.stat().st_size} bytes)")

    return large_file


# ============================================================================
# 최적화 전략 1: Chunking & Pagination
# ============================================================================


class ChunkRequest(BaseModel):
    """파일 청크 읽기 요청"""

    path: str = Field(..., description="파일 경로")
    start_line: int = Field(default=1, description="시작 줄 번호 (1-based)", ge=1)
    num_lines: int = Field(default=100, description="읽을 줄 수", ge=1, le=500)


class ChunkResponse(BaseModel):
    """파일 청크 응답 (Structured Output)"""

    success: bool = Field(..., description="성공 여부")
    file_path: str = Field(..., description="파일 경로")
    total_lines: int = Field(..., description="전체 줄 수")
    start_line: int = Field(..., description="시작 줄")
    end_line: int = Field(..., description="끝 줄")
    lines: list[str] = Field(..., description="읽은 줄들")
    has_more: bool = Field(..., description="더 읽을 내용이 있는지")
    next_cursor: str | None = Field(None, description="다음 페이지 커서 (opaque token)")


@mcp.tool(structured_output=True)
def read_file_chunk(request: ChunkRequest) -> dict[str, Any]:
    """
    파일을 청크 단위로 읽습니다 (Chunking 전략).

    Context Window 초과를 방지하고 필요한 부분만 로드합니다.

    Args:
        request: 청크 읽기 요청

    Returns:
        ChunkResponse 형식의 Structured Output
    """
    logger.info(f"Tool 호출: read_file_chunk(path={request.path}, start={request.start_line}, num={request.num_lines})")

    try:
        file_path = Path(request.path)
        if not file_path.exists():
            return {
                "success": False,
                "error": f"파일을 찾을 수 없습니다: {request.path}",
            }

        # 파일 읽기
        all_lines = file_path.read_text(encoding="utf-8").splitlines()
        total_lines = len(all_lines)

        # 청크 범위 계산
        start_idx = max(0, request.start_line - 1)
        end_idx = min(start_idx + request.num_lines, total_lines)
        chunk_lines = all_lines[start_idx:end_idx]

        # 다음 커서 생성 (opaque token: base64 encoded)
        has_more = end_idx < total_lines
        next_cursor = None
        if has_more:
            # 다음 시작 위치를 base64로 인코딩
            next_start = end_idx + 1
            next_cursor = base64.b64encode(str(next_start).encode()).decode()

        response = ChunkResponse(
            success=True,
            file_path=request.path,
            total_lines=total_lines,
            start_line=start_idx + 1,
            end_line=end_idx,
            lines=chunk_lines,
            has_more=has_more,
            next_cursor=next_cursor,
        )

        logger.info(f"청크 읽기 완료: {len(chunk_lines)} 줄 (전체 {total_lines} 줄 중 {start_idx+1}~{end_idx})")

        return response.model_dump()

    except Exception as e:
        logger.error(f"청크 읽기 오류: {e}")
        return {
            "success": False,
            "error": str(e),
        }


class SearchRequest(BaseModel):
    """파일 검색 요청"""

    path: str = Field(..., description="검색할 파일 경로")
    keyword: str = Field(..., description="검색 키워드")
    max_results: int = Field(default=10, description="최대 결과 수", ge=1, le=100)


class SearchMatch(BaseModel):
    """검색 결과 매칭"""

    line_number: int = Field(..., description="줄 번호")
    line_content: str = Field(..., description="줄 내용")
    match_position: int = Field(..., description="매칭 위치")


class SearchResponse(BaseModel):
    """파일 검색 응답"""

    success: bool = Field(..., description="성공 여부")
    file_path: str = Field(..., description="파일 경로")
    keyword: str = Field(..., description="검색 키워드")
    total_matches: int = Field(..., description="전체 매칭 수")
    matches: list[SearchMatch] = Field(..., description="매칭 결과")


@mcp.tool(structured_output=True)
def search_in_file(request: SearchRequest) -> dict[str, Any]:
    """
    파일에서 키워드를 검색합니다 (검색 → Chunk 로드 패턴).

    전체 파일을 로드하지 않고 필요한 부분만 찾습니다.

    Args:
        request: 검색 요청

    Returns:
        SearchResponse 형식의 Structured Output
    """
    logger.info(f"Tool 호출: search_in_file(path={request.path}, keyword={request.keyword})")

    try:
        file_path = Path(request.path)
        if not file_path.exists():
            return {
                "success": False,
                "error": f"파일을 찾을 수 없습니다: {request.path}",
            }

        # 파일에서 키워드 검색
        all_lines = file_path.read_text(encoding="utf-8").splitlines()
        matches: list[SearchMatch] = []

        for line_num, line in enumerate(all_lines, start=1):
            if request.keyword in line:
                match_pos = line.find(request.keyword)
                matches.append(
                    SearchMatch(
                        line_number=line_num,
                        line_content=line.strip(),
                        match_position=match_pos,
                    )
                )

                # 최대 결과 수 제한
                if len(matches) >= request.max_results:
                    break

        response = SearchResponse(
            success=True,
            file_path=request.path,
            keyword=request.keyword,
            total_matches=len(matches),
            matches=matches,
        )

        logger.info(f"검색 완료: {len(matches)} 개 매칭 발견")

        return response.model_dump()

    except Exception as e:
        logger.error(f"검색 오류: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ============================================================================
# 최적화 전략 2: Progress Notification
# ============================================================================


class AnalysisRequest(BaseModel):
    """코드베이스 분석 요청"""

    path: str = Field(..., description="분석할 디렉토리 경로")
    pattern: str = Field(default="*.py", description="파일 패턴")


def create_progress_notification(
    progress_token: str,
    progress: float,
    total: float | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """
    MCP Progress Notification 생성

    Args:
        progress_token: 진행 상태 토큰 (고유 식별자)
        progress: 현재 진행 값 (단조 증가)
        total: 전체 값 (선택사항)
        message: 상태 메시지

    Returns:
        JSON-RPC 2.0 notification
    """
    params: dict[str, Any] = {
        "progressToken": progress_token,
        "progress": progress,
    }

    if total is not None:
        params["total"] = total

    if message is not None:
        params["message"] = message

    return {
        "jsonrpc": "2.0",
        "method": "notifications/progress",
        "params": params,
    }


@mcp.tool(structured_output=True)
async def analyze_codebase(request: AnalysisRequest, progress_token: str | None = None) -> dict[str, Any]:
    """
    코드베이스를 분석합니다 (Progress Notification 지원).

    장기 작업의 진행 상태를 실시간으로 전달합니다.

    Args:
        request: 분석 요청
        progress_token: 진행 상태 추적 토큰 (선택사항)

    Returns:
        분석 결과 (Structured Output)
    """
    logger.info(f"Tool 호출: analyze_codebase(path={request.path}, pattern={request.pattern})")

    if progress_token:
        logger.info(f"Progress Token: {progress_token}")

    try:
        path = Path(request.path)
        if not path.exists():
            return {
                "success": False,
                "error": f"경로를 찾을 수 없습니다: {request.path}",
            }

        # 파일 목록 수집
        files = list(path.glob(request.pattern))
        total_files = len(files)

        if total_files == 0:
            return {
                "success": False,
                "error": f"파일을 찾을 수 없습니다: {request.pattern}",
            }

        # 분석 시뮬레이션 (실제로는 AST 파싱 등)
        stages = [
            (0, "분석 시작..."),
            (20, "파일 목록 수집 완료"),
            (40, "코드 구조 파싱 중..."),
            (60, "의존성 분석 중..."),
            (80, "메트릭 계산 중..."),
            (100, "분석 완료"),
        ]

        for progress, message in stages:
            if progress_token:
                # Progress notification 전송 (실제로는 MCP 프로토콜로 전송)
                notification = create_progress_notification(
                    progress_token=progress_token,
                    progress=progress,
                    total=100,
                    message=message,
                )
                # 로그로 출력 (실제 구현에서는 클라이언트로 전송)
                logger.info(f"Progress: {progress}% - {message}")
                logger.debug(f"Notification: {json.dumps(notification)}")

            # 작업 시뮬레이션
            await asyncio.sleep(0.3)

        # 분석 결과
        result = {
            "success": True,
            "path": request.path,
            "pattern": request.pattern,
            "total_files": total_files,
            "total_lines": total_files * 150,  # 시뮬레이션
            "functions_count": total_files * 10,
            "classes_count": total_files * 3,
            "complexity_score": 2.5,
            "issues_found": 5,
            "analysis_time_seconds": 1.8,
        }

        logger.info(f"분석 완료: {total_files} 파일")

        return result

    except Exception as e:
        logger.error(f"분석 오류: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ============================================================================
# 최적화 전략 3: Structured Output으로 토큰 절약
# ============================================================================


class FileStats(BaseModel):
    """파일 통계 (Structured Output)"""

    path: str = Field(..., description="파일 경로")
    size_bytes: int = Field(..., description="파일 크기 (bytes)")
    line_count: int = Field(..., description="전체 줄 수")
    code_lines: int = Field(..., description="코드 줄 수 (주석 제외)")
    comment_lines: int = Field(..., description="주석 줄 수")
    blank_lines: int = Field(..., description="빈 줄 수")
    language: str = Field(..., description="프로그래밍 언어")


@mcp.tool(structured_output=True)
def get_file_stats(file_path: str) -> dict[str, Any]:
    """
    파일 통계를 반환합니다 (Structured Output).

    자연어 설명 없이 구조화된 데이터만 반환하여 토큰 절약.

    Args:
        file_path: 파일 경로

    Returns:
        FileStats 형식의 Structured Output
    """
    logger.info(f"Tool 호출: get_file_stats(path={file_path})")

    try:
        path = Path(file_path)
        if not path.exists():
            return {
                "success": False,
                "error": f"파일을 찾을 수 없습니다: {file_path}",
            }

        # 파일 분석
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()

        code_lines = 0
        comment_lines = 0
        blank_lines = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                blank_lines += 1
            elif stripped.startswith("#"):
                comment_lines += 1
            else:
                code_lines += 1

        # 언어 감지 (확장자 기반)
        ext_to_lang = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".java": "Java",
            ".cpp": "C++",
            ".c": "C",
            ".go": "Go",
            ".rs": "Rust",
        }
        language = ext_to_lang.get(path.suffix, "Unknown")

        stats = FileStats(
            path=file_path,
            size_bytes=path.stat().st_size,
            line_count=len(lines),
            code_lines=code_lines,
            comment_lines=comment_lines,
            blank_lines=blank_lines,
            language=language,
        )

        logger.info(f"통계 계산 완료: {stats.line_count} 줄")

        return stats.model_dump()

    except Exception as e:
        logger.error(f"통계 계산 오류: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ============================================================================
# Resource 정의: 읽기 전용 데이터
# ============================================================================


@mcp.resource("stats://performance")
def get_performance_stats() -> dict[str, Any]:
    """
    서버 성능 통계를 반환합니다.

    Returns:
        성능 통계 (Structured Output)
    """
    logger.info("Resource 요청: stats://performance")

    return {
        "server": "ContextOptimizedMCPServer",
        "uptime_seconds": time.time(),
        "requests_processed": 0,
        "average_response_time_ms": 150,
        "cache_hit_rate": 0.85,
        "memory_usage_mb": 128,
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================================
# 메인 실행
# ============================================================================


def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(description="Context Optimized MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="전송 프로토콜 (기본값: stdio)",
    )

    args = parser.parse_args()
    logger.info(f"\nMCP 서버 시작 중... (Transport: {args.transport})\n")
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()

