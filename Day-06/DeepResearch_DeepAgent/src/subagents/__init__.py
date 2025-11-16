"""딥 리서치 에이전트를 위한 서브에이전트 설정입니다."""

from subagents.compressor import create_compressor_subagent_config
from subagents.critic import create_critic_subagent_config
from subagents.researcher import create_researcher_subagent_config

__all__ = [
    "create_researcher_subagent_config",
    "create_compressor_subagent_config",
    "create_critic_subagent_config",
]
