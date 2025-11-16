"""딥 리서치 에이전트 서브에이전트 및 오케스트레이터를 위한 프롬프트입니다."""

from prompts.compressor import COMPRESSOR_SYSTEM_PROMPT
from prompts.critic import CRITIC_SYSTEM_PROMPT
from prompts.orchestrator import ORCHESTRATOR_SYSTEM_PROMPT, format_orchestrator_prompt
from prompts.researcher import RESEARCHER_SYSTEM_PROMPT

__all__ = [
    "ORCHESTRATOR_SYSTEM_PROMPT",
    "RESEARCHER_SYSTEM_PROMPT",
    "COMPRESSOR_SYSTEM_PROMPT",
    "CRITIC_SYSTEM_PROMPT",
    "format_orchestrator_prompt",
]
