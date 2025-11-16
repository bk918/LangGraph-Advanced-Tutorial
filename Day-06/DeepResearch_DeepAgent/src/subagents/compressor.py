"""압축기 스킬 서브에이전트 설정입니다."""

from prompts.compressor import COMPRESSOR_SYSTEM_PROMPT


def create_compressor_subagent_config(date: str) -> dict:
    """DeepAgent를 위한 압축기 서브에이전트 설정을 생성합니다.

    Args:
        date: 프롬프트 포맷팅을 위한 현재 날짜 문자열

    Returns:
        DeepAgent용 SubAgent 설정 딕셔너리
    """
    # 압축기는 파일시스템 도구만 사용합니다 (미들웨어에서 제공)
    # ls, read_file, write_file 외에 추가 도구는 필요하지 않습니다

    return {
        "name": "compressor",
        "description": (
            "여러 연구 노트 파일 (이전 세션 포함)을 읽고 포괄적이고 잘 구성된 종합을 생성하는 연구 종합 전문가입니다. "
            "모든 연구자가 작업을 완료하고 결과를 /output/notes/에 저장한 후 이 에이전트를 사용하세요. "
            "압축기는 /output/notes/의 모든 노트 (이전 세션의 오래된 노트 포함)를 읽고, 중복을 제거하며, "
            "/output/compressed_research.md에 응집력 있는 종합을 생성합니다. "
            "최적 용도: 병렬 연구 결과 종합, 세션 간 연구 병합, 정보 중복 제거, "
            "다양한 출처를 일관된 서사로 구성."
        ),
        "system_prompt": COMPRESSOR_SYSTEM_PROMPT.format(date=date),
        "tools": [],  # 파일시스템 미들웨어 도구만 사용
    }
