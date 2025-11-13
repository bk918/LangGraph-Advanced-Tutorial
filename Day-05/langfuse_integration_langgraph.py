from langfuse import get_client

langfuse = get_client()

# 연결 확인
if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
else:
    print("Authentication failed. Please check your credentials and host.")

"""## 예제 1: LangGraph를 사용한 간단한 챗봇 앱

**이 섹션에서 수행할 작업:**

*   일반적인 질문에 답변할 수 있는 지원 챗봇을 LangGraph로 구축
*   Langfuse를 사용하여 챗봇의 입력과 출력을 추적

기본 챗봇으로 시작하여 다음 섹션에서 더 고급 멀티 에이전트 설정을 구축하면서 주요 LangGraph 개념을 소개합니다.

### 에이전트 생성

`StateGraph`를 생성하는 것부터 시작합니다. `StateGraph` 객체는 챗봇의 구조를 상태 머신으로 정의합니다. LLM과 챗봇이 호출할 수 있는 함수를 나타내는 노드를 추가하고, 봇이 이러한 함수 간에 어떻게 전환하는지 지정하는 엣지를 추가합니다.
"""

from typing import Annotated

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class State(TypedDict):
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)

llm = ChatOpenAI(model="gpt-4o", temperature=0.2)


# chatbot 노드 함수는 현재 State를 입력으로 받아 업데이트된 메시지 리스트를 반환합니다. 이것은 모든 LangGraph 노드 함수의 기본 패턴입니다.
def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages"])]}


# "chatbot" 노드를 추가합니다. 노드는 작업 단위를 나타냅니다. 일반적으로 일반 파이썬 함수입니다.
graph_builder.add_node("chatbot", chatbot)

# 진입점을 추가합니다. 이것은 그래프를 실행할 때마다 어디서 시작할지 알려줍니다.
graph_builder.set_entry_point("chatbot")

# 종료점을 설정합니다. 이것은 그래프에 "이 노드가 실행될 때마다 종료할 수 있습니다"라고 지시합니다.
graph_builder.set_finish_point("chatbot")

# 그래프를 실행하려면 그래프 빌더에서 "compile()"을 호출합니다. 이것은 상태에서 invoke할 수 있는 "CompiledGraph"를 생성합니다.
graph = graph_builder.compile()

"""### 호출에 Langfuse를 콜백으로 추가

이제 애플리케이션의 단계를 추적하기 위해 [LangChain용 Langfuse 콜백 핸들러](https://langfuse.com/integrations/frameworks/langchain)를 추가합니다: `config={"callbacks": [langfuse_handler]}`
"""

from langfuse.langchain import CallbackHandler

# Langchain용 Langfuse CallbackHandler 초기화 (추적용)
langfuse_handler = CallbackHandler()

for s in graph.stream(
    {"messages": [HumanMessage(content="What is Langfuse?")]},
    config={"callbacks": [langfuse_handler]},
):
    print(s)

"""
### LangGraph Server에서 Langfuse 사용

[LangGraph Server](https://langchain-ai.github.io/langgraph/concepts/langgraph_server/)를 사용할 때 Langfuse를 콜백으로 추가할 수 있습니다.

LangGraph Server를 사용하면 LangGraph Server가 그래프 호출을 자동으로 처리합니다. 따라서 그래프를 선언할 때 Langfuse 콜백을 추가해야 합니다.
"""

from typing import Annotated

from langchain_openai import ChatOpenAI
from langfuse.langchain import CallbackHandler
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class State(TypedDict):
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)

llm = ChatOpenAI(model="gpt-4o", temperature=0.2)


def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages"])]}


graph_builder.add_node("chatbot", chatbot)
graph_builder.set_entry_point("chatbot")
graph_builder.set_finish_point("chatbot")

# Langchain용 Langfuse CallbackHandler 초기화 (추적용)
langfuse_handler = CallbackHandler()

# 컴파일된 그래프에서 "with_config"를 호출합니다.
# "compile"과 유사하지만 콜백이 포함된 "CompiledGraph"를 반환합니다.
# 이렇게 하면 매번 수동으로 콜백을 추가하지 않고도 자동으로 그래프를 추적할 수 있습니다.
graph = graph_builder.compile().with_config({"callbacks": [langfuse_handler]})

"""## 예제 2: LangGraph를 사용한 멀티 에이전트 애플리케이션

**이 섹션에서 수행할 작업**:

*   2개의 실행 에이전트 구축: LangChain WikipediaAPIWrapper를 사용하여 Wikipedia를 검색하는 연구 에이전트 하나와 현재 시간을 알려주는 커스텀 도구를 사용하는 에이전트 하나
*   사용자 질문을 두 에이전트 중 하나에 위임하는 에이전트 슈퍼바이저 구축
*   슈퍼바이저와 실행 에이전트의 단계를 추적하기 위해 Langfuse 핸들러를 콜백으로 추가
"""

"""### 도구 생성

이 예제에서는 Wikipedia 연구를 수행하는 에이전트 하나와 현재 시간을 알려주는 에이전트 하나를 구축합니다.
아래에서 사용할 도구를 정의합니다:
"""

from datetime import datetime
from typing import Annotated

from langchain.tools import Tool
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper

# Wikipedia를 검색하는 도구를 정의합니다
wikipedia_tool = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())

# 현재 날짜/시간을 반환하는 새 도구를 정의합니다
datetime_tool = Tool(
    name="Datetime",
    func=lambda x: datetime.now().isoformat(),
    description="Returns the current datetime",
)

"""### 헬퍼 유틸리티

새 에이전트 워커 노드를 추가하는 것을 단순화하기 위해 아래에 헬퍼 함수를 정의합니다.
"""

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI


def create_agent(llm: ChatOpenAI, system_prompt: str, tools: list):
    # 각 워커 노드에는 이름과 일부 도구가 제공됩니다.
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                system_prompt,
            ),
            MessagesPlaceholder(variable_name="messages"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    agent = create_openai_tools_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools)
    return executor


def agent_node(state, agent, name):
    result = agent.invoke(state)
    return {"messages": [HumanMessage(content=result["output"], name=name)]}


"""### 에이전트 슈퍼바이저 생성

함수 호출을 사용하여 다음 워커 노드를 선택하거나 처리를 완료합니다.
"""

from langchain_core.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

members = ["Researcher", "CurrentTime"]
system_prompt = (
    "You are a supervisor tasked with managing a conversation between the"
    " following workers:  {members}. Given the following user request,"
    " respond with the worker to act next. Each worker will perform a"
    " task and respond with their results and status. When finished,"
    " respond with FINISH."
)
# 우리 팀 슈퍼바이저는 LLM 노드입니다. 처리할 다음 에이전트를 선택하고 작업이 완료되는 시점을 결정합니다
options = ["FINISH"] + members

# OpenAI 함수 호출을 사용하면 출력 파싱이 더 쉬워집니다
function_def = {
    "name": "route",
    "description": "Select the next role.",
    "parameters": {
        "title": "routeSchema",
        "type": "object",
        "properties": {
            "next": {
                "title": "Next",
                "anyOf": [
                    {"enum": options},
                ],
            }
        },
        "required": ["next"],
    },
}

# ChatPromptTemplate을 사용하여 프롬프트를 생성합니다
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
        (
            "system",
            "Given the conversation above, who should act next?"
            " Or should we FINISH? Select one of: {options}",
        ),
    ]
).partial(options=str(options), members=", ".join(members))

llm = ChatOpenAI(model="gpt-4o")

# Construction of the chain for the supervisor agent
supervisor_chain = (
    prompt
    | llm.bind_functions(functions=[function_def], function_call="route")
    | JsonOutputFunctionsParser()
)

"""### 그래프 구성"""

import functools
import operator
from collections.abc import Sequence
from typing import TypedDict

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import END, START, StateGraph


# 에이전트 상태는 그래프의 각 노드에 대한 입력입니다
class AgentState(TypedDict):
    # 주석은 그래프에 새 메시지가 항상 현재 상태에 추가된다고 알려줍니다
    messages: Annotated[Sequence[BaseMessage], operator.add]
    # 'next' 필드는 다음에 어디로 라우팅할지 나타냅니다
    next: str


# create_agent 헬퍼 함수를 사용하여 연구 에이전트를 추가합니다
research_agent = create_agent(
    llm,
    tools=[wikipedia_tool],
    system_prompt="You are a web researcher.",
)
research_node = functools.partial(agent_node, agent=research_agent, name="Researcher")

# create_agent 헬퍼 함수를 사용하여 시간 에이전트를 추가합니다
currenttime_agent = create_agent(
    llm,
    tools=[datetime_tool],
    system_prompt="You can tell the current time at",
)
currenttime_node = functools.partial(agent_node, agent=currenttime_agent, name="CurrentTime")

workflow = StateGraph(AgentState)

# "chatbot" 노드를 추가합니다. 노드는 작업 단위를 나타냅니다. 일반적으로 일반 파이썬 함수입니다.
workflow.add_node("Researcher", research_node)
workflow.add_node("CurrentTime", currenttime_node)
workflow.add_node("supervisor", supervisor_chain)

# 작업이 완료되면 워커가 항상 슈퍼바이저에게 "보고"하기를 원합니다
for member in members:
    workflow.add_edge(member, "supervisor")

# 조건부 엣지는 일반적으로 현재 그래프 상태에 따라 다른 노드로 라우팅하는 "if" 문을 포함합니다.
# 이러한 함수는 현재 그래프 상태를 수신하고 다음에 호출할 노드를 나타내는 문자열 또는 문자열 목록을 반환합니다.
conditional_map = {k: k for k in members}
conditional_map["FINISH"] = END
workflow.add_conditional_edges("supervisor", lambda x: x["next"], conditional_map)

# 진입점을 추가합니다. 이것은 그래프를 실행할 때마다 어디서 시작할지 알려줍니다.
workflow.add_edge(START, "supervisor")

# 그래프를 실행하려면 그래프 빌더에서 "compile()"을 호출합니다. 이것은 상태에서 invoke할 수 있는 "CompiledGraph"를 생성합니다.
graph_2 = workflow.compile()

"""### 호출에 Langfuse를 콜백으로 추가

[Langfuse 핸들러](https://langfuse.com/integrations/frameworks/langchain)를 콜백으로 추가합니다: `config={"callbacks": [langfuse_handler]}`
"""

from langfuse.langchain import CallbackHandler

# Langchain용 Langfuse CallbackHandler 초기화 (추적용)
langfuse_handler = CallbackHandler()

# Langfuse 핸들러를 콜백으로 추가: config={"callbacks": [langfuse_handler]}
# Langfuse에서 trace 이름으로 사용될 선택적 'run_name'을 설정할 수도 있습니다
for s in graph_2.stream(
    {"messages": [HumanMessage(content="How does photosynthesis work?")]},
    config={"callbacks": [langfuse_handler]},
):
    print(s)
    print("----")

# Langfuse 핸들러를 콜백으로 추가: config={"callbacks": [langfuse_handler]}
for s in graph_2.stream(
    {"messages": [HumanMessage(content="What time is it?")]},
    config={"callbacks": [langfuse_handler]},
):
    print(s)
    print("----")

"""
## Multi LangGraph 에이전트

하나의 LangGraph 에이전트가 하나 이상의 다른 LangGraph 에이전트를 사용하는 설정이 있습니다.
멀티 에이전트 실행에 대한 모든 해당 스팬을 하나의 단일 trace로 결합하려면 커스텀 `trace_id`를 전달할 수 있습니다.

먼저, 두 에이전트 모두 사용할 수 있는 trace_id를 생성하여 에이전트 실행을 하나의 Langfuse trace로 그룹화합니다.
"""

from langfuse import Langfuse, get_client
from langfuse.langchain import CallbackHandler

langfuse = get_client()

# 외부 시스템에서 결정론적 trace ID를 생성합니다
predefined_trace_id = Langfuse.create_trace_id()

# Langchain용 Langfuse CallbackHandler 초기화 (추적용)
langfuse_handler = CallbackHandler()

"""다음으로 서브 에이전트를 설정합니다."""

from typing import Annotated

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class State(TypedDict):
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)

llm = ChatOpenAI(model="gpt-4o", temperature=0.2)


def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages"])]}


graph_builder.add_node("chatbot", chatbot)
graph_builder.set_entry_point("chatbot")
graph_builder.set_finish_point("chatbot")
sub_agent = graph_builder.compile()

"""그런 다음, 질문에 답변하기 위해 research-sub-agent를 사용하는 도구를 설정합니다."""

from langchain_core.tools import tool


@tool
def langgraph_research(question):
    """다양한 주제에 대한 연구를 수행합니다."""

    with langfuse.start_as_current_span(
        name="🤖-sub-research-agent", trace_context={"trace_id": predefined_trace_id}
    ) as span:
        span.update_trace(input=question)

        response = sub_agent.invoke(
            {"messages": [HumanMessage(content=question)]}, config={"callbacks": [langfuse_handler]}
        )

        span.update_trace(output=response["messages"][1].content)

    return response["messages"][1].content


"""Set up a second simple LangGraph agent that uses the new `langgraph_research`."""

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4.1", temperature=0.2)

main_agent = create_agent(model=llm, tools=[langgraph_research])

user_question = "What is Langfuse?"

# trace_context와 함께 미리 정의된 trace ID를 사용합니다
with langfuse.start_as_current_span(
    name="🤖-main-agent", trace_context={"trace_id": predefined_trace_id}
) as span:
    span.update_trace(input=user_question)

    # LangChain 실행이 이 trace의 일부가 됩니다
    response = main_agent.invoke(
        {"messages": [{"role": "user", "content": user_question}]},
        config={"callbacks": [langfuse_handler]},
    )

    span.update_trace(output=response["messages"][1].content)

print(f"Trace ID: {predefined_trace_id}")  # 나중에 scoring에 사용합니다

"""
## trace에 점수 추가하기

[점수(Scores)](https://langfuse.com/docs/scores/overview)는 단일 관찰 또는 전체 trace를 평가하는 데 사용됩니다. 런타임에 커스텀 품질 검사를 구현하거나 사람이 개입하는(human-in-the-loop) 평가 프로세스를 용이하게 합니다.

아래 예제에서는 특정 스팬에 대한 `relevance`(숫자 점수)와 전체 trace에 대한 `feedback`(범주형 점수)의 점수를 매기는 방법을 보여줍니다. 이는 애플리케이션을 체계적으로 평가하고 개선하는 데 도움이 됩니다.

**→ [Langfuse의 커스텀 점수](https://langfuse.com/docs/scores/custom)에 대해 자세히 알아보기.**
"""

from langfuse import get_client

langfuse = get_client()

# 옵션 1: 컨텍스트 매니저에서 반환된 span 객체 사용
with langfuse.start_as_current_span(name="langgraph-request") as span:
    # ... LangGraph 실행 ...

    # span 객체를 사용하여 점수 매기기
    span.score_trace(
        name="user-feedback", value=1, data_type="NUMERIC", comment="This was correct, thank you"
    )

# 옵션 2: 컨텍스트 내에 있는 경우 langfuse.score_current_trace() 사용
with langfuse.start_as_current_span(name="langgraph-request") as span:
    # ... LangGraph 실행 ...

    # 현재 컨텍스트를 사용하여 점수 매기기
    langfuse.score_current_trace(name="user-feedback", value=1, data_type="NUMERIC")

# 옵션 3: 컨텍스트 외부에서 trace ID와 함께 create_score() 사용
langfuse.create_score(
    trace_id=predefined_trace_id,
    name="user-feedback",
    value=1,
    data_type="NUMERIC",
    comment="This was correct, thank you",
)

"""## Langfuse로 프롬프트 관리

[Langfuse 프롬프트 관리](https://langfuse.com/docs/prompts/example-langchain)를 사용하여 프롬프트를 효과적으로 관리하고 버전을 관리하세요. 이 예제에서는 SDK를 통해 사용된 프롬프트를 추가합니다. 그러나 프로덕션에서는 사용자가 SDK를 사용하는 대신 Langfuse UI를 통해 프롬프트를 업데이트하고 관리합니다.

Langfuse 프롬프트 관리는 기본적으로 프롬프트 CMS(콘텐츠 관리 시스템)입니다. 또는 Langfuse UI에서 프롬프트를 편집하고 버전을 관리할 수도 있습니다.

*   Langfuse 프롬프트 관리에서 프롬프트를 식별하는 `Name`
*   `{{input variables}}`를 포함한 프롬프트 템플릿이 있는 프롬프트
*   프롬프트를 기본값으로 즉시 사용하려면 `production`을 포함하는 `labels`
"""

from langfuse import get_client

langfuse = get_client()

langfuse.create_prompt(
    name="translator_system-prompt",
    prompt="You are a translator that translates every input text into Spanish.",
    labels=["production"],
)

"""![View prompt in Langfuse UI](https://langfuse.com/images/cookbook/integration-langgraph/integration_langgraph_prompt_example.png)

Use the utility method `.get_langchain_prompt()` to transform the Langfuse prompt into a string that can be used in Langchain.


**Context:** Langfuse declares input variables in prompt templates using double brackets (`{{input variable}}`). Langchain uses single brackets for declaring input variables in PromptTemplates (`{input variable}`). The utility method `.get_langchain_prompt()` replaces the double brackets with single brackets. In this example, however, we don't use any variables in our prompt.
"""

# Get current production version of prompt and transform the Langfuse prompt into a string that can be used in Langchain
langfuse_system_prompt = langfuse.get_prompt("translator_system-prompt")
langchain_system_prompt = langfuse_system_prompt.get_langchain_prompt()  # 이 부분이 중요함!

print(langchain_system_prompt)

"""Now we can use the new system prompt string to update our assistant."""

from typing import Annotated

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class State(TypedDict):
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)

llm = ChatOpenAI(model="gpt-4.1", temperature=0.2)

# 번역기 어시스턴트용 시스템 프롬프트를 추가합니다
system_prompt = {"role": "system", "content": langchain_system_prompt}


def chatbot(state: State):
    messages_with_system_prompt = [system_prompt] + state["messages"]
    response = llm.invoke(messages_with_system_prompt)
    return {"messages": [response]}


graph_builder.add_node("chatbot", chatbot)
graph_builder.set_entry_point("chatbot")
graph_builder.set_finish_point("chatbot")
graph = graph_builder.compile()

from langfuse.langchain import CallbackHandler

# Langchain용 Langfuse CallbackHandler 초기화 (추적용)
langfuse_handler = CallbackHandler()

# Langfuse 핸들러를 콜백으로 추가: config={"callbacks": [langfuse_handler]}
for s in graph.stream(
    {"messages": [HumanMessage(content="What is Langfuse?")]},
    config={"callbacks": [langfuse_handler]},
):
    print(s)

"""## LangGraph trace에 커스텀 스팬 추가하기

때때로 LangGraph trace에 커스텀 스팬을 추가하는 것이 유용할 수 있습니다. 이 [GitHub 토론 스레드](https://github.com/orgs/langfuse/discussions/2988#discussioncomment-11634600)에서 이를 수행하는 방법의 예제를 제공합니다.
"""
