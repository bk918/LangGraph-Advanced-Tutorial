"""# LangGraph 에이전트 평가하기

이 튜토리얼에서는 [Langfuse](https://langfuse.com)와 [Hugging Face Datasets](https://huggingface.co/datasets)를 사용하여 **[LangGraph agents](https://github.com/langchain-ai/langgraph)의 내부 단계(traces)를 모니터링**하고 **성능을 평가**하는 방법을 배웁니다.

이 가이드는 팀이 에이전트를 빠르고 안정적으로 프로덕션에 배포하기 위해 사용하는 **온라인** 및 **오프라인** 평가 메트릭을 다룹니다. 평가 전략에 대해 자세히 알아보려면 [블로그 포스트](https://langfuse.com/blog/2025-03-04-llm-evaluation-101-best-practices-and-challenges)를 확인하세요.

**AI 에이전트 평가가 중요한 이유:**
- 작업 실패 또는 차선의 결과 발생 시 디버깅 문제
- 실시간으로 비용 및 성능 모니터링
- 지속적인 피드백을 통해 신뢰성과 안전성 향상
"""

"""## 단계 1: 환경 변수 설정

Langfuse 클라우드에 가입하거나 자체 호스팅하여 Langfuse API 키를 받으세요.
"""

import os

# Get keys for your project from the project settings page: https://cloud.langfuse.com
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-..."
os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-..."
os.environ["LANGFUSE_BASE_URL"] = "https://us.cloud.langfuse.com" # 🇺🇸 US region

# Your openai key
os.environ["OPENAI_API_KEY"] = "sk-proj-..."

"""환경 변수가 설정되면 이제 Langfuse 클라이언트를 초기화할 수 있습니다. get_client()는 환경 변수에 제공된 자격 증명을 사용하여 Langfuse 클라이언트를 초기화합니다."""

from langfuse import get_client

langfuse = get_client()

# Verify connection
if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
else:
    print("Authentication failed. Please check your credentials and host.")

"""## 단계 2: 계측 테스트

여기 간단한 Q&A 에이전트가 있습니다. 계측이 올바르게 작동하는지 확인하기 위해 실행합니다. 모든 것이 올바르게 설정되면 관찰 가능성 대시보드에서 로그/스팬을 볼 수 있습니다.
"""

from typing import Annotated

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class State(TypedDict):
    # Messages have the type "list". The `add_messages` function in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)

llm = ChatOpenAI(model="gpt-4o", temperature=0.2)


# The chatbot node function takes the current State as input and returns an updated messages list. This is the basic pattern for all LangGraph node functions.
def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages"])]}


# Add a "chatbot" node. Nodes represent units of work. They are typically regular python functions.
graph_builder.add_node("chatbot", chatbot)

# Add an entry point. This tells our graph where to start its work each time we run it.
graph_builder.set_entry_point("chatbot")

# Set a finish point. This instructs the graph "any time this node is run, you can exit."
graph_builder.set_finish_point("chatbot")

# To be able to run our graph, call "compile()" on the graph builder. This creates a "CompiledGraph" we can use invoke on our state.
graph = graph_builder.compile()

from langfuse.langchain import CallbackHandler

# Initialize Langfuse CallbackHandler for Langchain (tracing)
langfuse_handler = CallbackHandler()

for s in graph.stream(
    {"messages": [HumanMessage(content="What is Langfuse?")]},
    config={"callbacks": [langfuse_handler]},
):
    print(s)

"""Langfuse Traces 대시보드를 확인하여 스팬과 로그가 기록되었는지 확인하세요.

## 단계 3: 더 복잡한 에이전트 관찰 및 평가

계측이 작동하는 것을 확인했으니 이제 더 복잡한 쿼리를 시도하여 고급 메트릭(토큰 사용량, 지연 시간, 비용 등)이 어떻게 추적되는지 확인해 봅시다.
"""

import os
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph


class EmailState(TypedDict):
    email: dict[str, Any]
    is_spam: bool | None
    spam_reason: str | None
    email_category: str | None
    draft_response: str | None
    messages: list[dict[str, Any]]


# Initialize LLM
model = ChatOpenAI(model="gpt-4o", temperature=0)


class EmailState(TypedDict):
    email: dict[str, Any]
    is_spam: bool | None
    draft_response: str | None
    messages: list[dict[str, Any]]


# Define nodes
def read_email(state: EmailState):
    email = state["email"]
    print(f"Alfred is processing an email from {email['sender']} with subject: {email['subject']}")
    return {}


def classify_email(state: EmailState):
    email = state["email"]

    prompt = f"""
As Alfred the butler of Mr wayne and it's SECRET identity Batman, analyze this email and determine if it is spam or legitimate and should be brought to Mr wayne's attention.

Email:
From: {email["sender"]}
Subject: {email["subject"]}
Body: {email["body"]}

First, determine if this email is spam.
answer with SPAM or HAM if it's legitimate. Only return the answer
Answer :
    """
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    response_text = response.content.lower()
    print(response_text)
    is_spam = "spam" in response_text and "ham" not in response_text

    if not is_spam:
        new_messages = state.get("messages", []) + [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response.content},
        ]
    else:
        new_messages = state.get("messages", [])

    return {"is_spam": is_spam, "messages": new_messages}


def handle_spam(state: EmailState):
    print("Alfred has marked the email as spam.")
    print("The email has been moved to the spam folder.")
    return {}


def drafting_response(state: EmailState):
    email = state["email"]

    prompt = f"""
As Alfred the butler, draft a polite preliminary response to this email.

Email:
From: {email["sender"]}
Subject: {email["subject"]}
Body: {email["body"]}

Draft a brief, professional response that Mr. Wayne can review and personalize before sending.
    """

    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    new_messages = state.get("messages", []) + [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": response.content},
    ]

    return {"draft_response": response.content, "messages": new_messages}


def notify_mr_wayne(state: EmailState):
    email = state["email"]

    print("\n" + "=" * 50)
    print(f"Sir, you've received an email from {email['sender']}.")
    print(f"Subject: {email['subject']}")
    print("\nI've prepared a draft response for your review:")
    print("-" * 50)
    print(state["draft_response"])
    print("=" * 50 + "\n")

    return {}


# Define routing logic
def route_email(state: EmailState) -> str:
    if state["is_spam"]:
        return "spam"
    else:
        return "legitimate"


# 그래프 생성
email_graph = StateGraph(EmailState)

# 노드 추가
email_graph.add_node("read_email", read_email)  # read_email 노드는 read_mail 함수를 실행함
email_graph.add_node(
    "classify_email", classify_email
)  # classify_email 노드는 classify_email 함수를 실행함
email_graph.add_node("handle_spam", handle_spam)  # 동일한 로직
email_graph.add_node("drafting_response", drafting_response)  # 동일한 로직
email_graph.add_node("notify_mr_wayne", notify_mr_wayne)  # 동일한 로직

# 엣지 추가
email_graph.add_edge(START, "read_email")  # 시작 후 "read_email" 노드로 이동

email_graph.add_edge("read_email", "classify_email")  # 읽기 후 분류를 수행

# 조건부 엣지 추가
email_graph.add_conditional_edges(
    "classify_email",  # 분류 후 "route_email" 함수를 실행
    route_email,
    {
        "spam": "handle_spam",  # "Spam"을 반환하면 "handle_spam" 노드로 이동
        "legitimate": "drafting_response",  # 정상 메일이면 "drafting response" 노드로 이동
    },
)

# 최종 엣지 추가
email_graph.add_edge("handle_spam", END)  # 스팸 처리 후 항상 종료
email_graph.add_edge("drafting_response", "notify_mr_wayne")
email_graph.add_edge("notify_mr_wayne", END)  # 웨인 씨에게 알림 후 종료

# 그래프 컴파일
compiled_graph = email_graph.compile()

# 테스트용 예시 이메일
legitimate_email = {
    "sender": "Joker",
    "subject": "Found you Batman ! ",
    "body": "Mr. Wayne,I found your secret identity ! I know you're batman ! Ther's no denying it, I have proof of that and I'm coming to find you soon. I'll get my revenge. JOKER",
}

spam_email = {
    "sender": "Crypto bro",
    "subject": "The best investment of 2025",
    "body": "Mr Wayne, I just launched an ALT coin and want you to buy some !",
}

from langfuse.langchain import CallbackHandler

# Langchain용 Langfuse CallbackHandler 초기화 (추적)
langfuse_handler = CallbackHandler()

# 정상 이메일 처리
print("\nProcessing legitimate email...")
legitimate_result = compiled_graph.invoke(
    input={"email": legitimate_email, "is_spam": None, "draft_response": None, "messages": []},
    config={"callbacks": [langfuse_handler]},
)

# 스팸 이메일 처리
print("\nProcessing spam email...")
spam_result = compiled_graph.invoke(
    input={"email": spam_email, "is_spam": None, "draft_response": None, "messages": []},
    config={"callbacks": [langfuse_handler]},
)

"""### Trace 구조

Langfuse는 에이전트 로직의 각 단계를 나타내는 **spans**를 포함하는 **trace**를 기록합니다. 여기서 trace는 전체 에이전트 실행과 다음에 대한 하위 스팬을 포함합니다:
- 도구 호출 (get_weather)
- LLM 호출 ('gpt-4o'를 사용한 Responses API)

이를 검사하여 시간이 어디에 소비되는지, 얼마나 많은 토큰이 사용되는지 등을 정확히 확인할 수 있습니다:

## 온라인 평가

온라인 평가는 실제 환경, 즉 프로덕션에서 실제 사용 중에 에이전트를 평가하는 것을 의미합니다. 여기에는 실제 사용자 상호 작용에 대한 에이전트의 성능을 모니터링하고 결과를 지속적으로 분석하는 것이 포함됩니다.

다양한 평가 기법에 대한 가이드를 [여기](https://langfuse.com/blog/2025-03-04-llm-evaluation-101-best-practices-and-challenges)에 작성했습니다.

### 프로덕션에서 추적할 일반적인 메트릭

1. **비용** — 계측은 토큰 사용량을 캡처하며, 토큰당 가격을 할당하여 대략적인 비용으로 변환할 수 있습니다.
2. **지연 시간** — 각 단계 또는 전체 실행을 완료하는 데 걸리는 시간을 관찰합니다.
3. **사용자 피드백** — 사용자는 직접 피드백(찬성/반대)을 제공하여 에이전트를 개선하거나 수정할 수 있습니다.
4. **LLM-as-a-Judge** — 별도의 LLM을 사용하여 에이전트의 출력을 거의 실시간으로 평가합니다(예: 독성 또는 정확성 확인).

에이전트가 사용자 인터페이스에 임베드된 경우 직접 사용자 피드백(채팅 UI의 찬성/반대 등)을 기록할 수 있습니다.
"""

from langfuse import get_client

langfuse = get_client()

# 옵션 1: 컨텍스트 매니저에서 생성된 span 객체 사용
with langfuse.start_as_current_span(name="langgraph-request") as span:
    # ... LangGraph 실행 ...

    # span 객체를 사용한 점수 기록
    span.score_trace(
        name="user-feedback", value=1, data_type="NUMERIC", comment="This was correct, thank you"
    )

# 옵션 2: 컨텍스트 내에서 langfuse.score_current_trace() 사용
with langfuse.start_as_current_span(name="langgraph-request") as span:
    # ... LangGraph 실행 ...

    # 현재 컨텍스트를 사용한 점수 기록
    langfuse.score_current_trace(name="user-feedback", value=1, data_type="NUMERIC")

# 옵션 3: trace ID와 함께 create_score() 사용 (컨텍스트 외부)
langfuse.create_score(
    trace_id="predefined-trace-id",  # 유효한 trace id 형식이어야 함 (문서 참조)
    name="user-feedback",
    value=1,
    data_type="NUMERIC",
    comment="This was correct, thank you",
)

"""사용자 피드백은 Langfuse에 캡처됩니다:

#### 4. 자동화된 LLM-as-a-Judge 점수 부여

LLM-as-a-Judge는 에이전트의 출력을 자동으로 평가하는 또 다른 방법입니다. 별도의 LLM 호출을 설정하여 출력의 정확성, 독성, 스타일 또는 관심 있는 기타 기준을 평가할 수 있습니다.

**워크플로우**:
1. **평가 템플릿**을 정의합니다. 예: "텍스트가 독성이 있는지 확인"
2. 판단 모델로 사용할 모델을 설정합니다. 이 경우 `gpt-4o-mini`입니다.
3. 에이전트가 출력을 생성할 때마다 해당 출력을 템플릿과 함께 "판단" LLM에 전달합니다.
4. 판단 LLM은 관찰 가능성 도구에 기록하는 등급 또는 레이블로 응답합니다.
"""

# 스팸 이메일 처리
print("\nProcessing spam email...")
spam_result = compiled_graph.invoke(
    input={"email": spam_email, "is_spam": None, "draft_response": None, "messages": []},
    config={"callbacks": [langfuse_handler]},
)

"""스팸 이메일 처리 중...
Alfred가 Crypto bro로부터 온 이메일을 처리 중입니다. 제목: The best investment of 2025
spam
Alfred가 이메일을 스팸으로 표시했습니다.
이메일이 스팸 폴더로 이동되었습니다.

이 예제의 답변이 "독성 없음"으로 판단된 것을 볼 수 있습니다.

#### 5. 관찰 가능성 메트릭 개요

이러한 모든 메트릭은 대시보드에서 함께 시각화할 수 있습니다. 이를 통해 여러 세션에서 에이전트의 성능을 빠르게 확인하고 시간 경과에 따른 품질 메트릭을 추적할 수 있습니다.

## 오프라인 평가

온라인 평가는 실시간 피드백에 필수적이지만 **오프라인 평가**도 필요합니다—개발 전 또는 개발 중 체계적인 검사. 
이는 변경 사항을 프로덕션에 배포하기 전에 품질과 신뢰성을 유지하는 데 도움이 됩니다.

### 데이터셋 평가

오프라인 평가에서는 일반적으로:
1. 벤치마크 데이터셋 보유(프롬프트 및 예상 출력 쌍)
2. 해당 데이터셋에서 에이전트 실행
3. 출력을 예상 결과와 비교하거나 추가 점수 부여 메커니즘 사용

아래에서는 질문과 예상 답변이 포함된 [q&a-dataset](https://huggingface.co/datasets/junzhang1207/search-dataset)을 사용하여 이 접근 방식을 시연합니다.
"""

import pandas as pd
from datasets import load_dataset

# Hugging Face에서 search-dataset 가져오기
dataset = load_dataset("junzhang1207/search-dataset", split="train")
df = pd.DataFrame(dataset)
print("First few rows of search-dataset:")
print(df.head())

"""다음으로, 실행을 추적하기 위해 Langfuse에서 데이터셋 엔티티를 생성합니다. 그런 다음 데이터셋의 각 항목을 시스템에 추가합니다."""

from langfuse import Langfuse

langfuse = Langfuse()

langfuse_dataset_name = "qa-dataset_langgraph-agent"

# Langfuse에서 데이터셋 생성
langfuse.create_dataset(
    name=langfuse_dataset_name,
    description="q&a dataset uploaded from Hugging Face",
    metadata={"date": "2025-03-21", "type": "benchmark"},
)

df_30 = df.sample(30)  # 이 예제에서는 30개의 데이터셋 질문만 업로드

for idx, row in df_30.iterrows():
    langfuse.create_dataset_item(
        dataset_name=langfuse_dataset_name,
        input={"text": row["question"]},
        expected_output={"text": row["expected_answer"]},
    )

"""#### 데이터셋에서 에이전트 실행

먼저 OpenAI 모델을 사용하여 질문에 답하는 간단한 LangGraph 에이전트를 조립합니다.
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

llm = ChatOpenAI(model="gpt-4.5-preview")


def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages"])]}


graph_builder.add_node("chatbot", chatbot)
graph_builder.set_entry_point("chatbot")
graph_builder.set_finish_point("chatbot")

graph = graph_builder.compile()

"""다음으로, 다음을 수행하는 헬퍼 함수 `my_agent()`를 정의합니다:
1. Langfuse trace 생성
2. LangGraph 실행을 계측하기 위해 `langfuse_handler_trace` 가져오기
3. 에이전트를 실행하고 `langfuse_handler_trace`를 호출에 전달
"""

from langchain_openai import ChatOpenAI
from langfuse import get_client
from langfuse.langchain import CallbackHandler


class State(TypedDict):
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)
llm = ChatOpenAI(model="gpt-4o")
langfuse = get_client()


def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages"])]}


graph_builder.add_node("chatbot", chatbot)
graph_builder.set_entry_point("chatbot")
graph_builder.set_finish_point("chatbot")
graph = graph_builder.compile()


def my_agent(question, langfuse_handler):
    # Langfuse span을 통해 trace를 생성하고 내부에서 Langchain 사용
    with langfuse.start_as_current_span(name="my-langgraph-agent") as root_span:
        # 단계 2: LangChain 처리
        response = graph.invoke(
            input={"messages": [HumanMessage(content=question)]},
            config={"callbacks": [langfuse_handler]},
        )

        # trace 출력 업데이트
        root_span.update_trace(input=question, output=response["messages"][1].content)

        print(question)
        print(response["messages"][1].content)

    return response["messages"][1].content


"""마지막으로, 각 데이터셋 항목을 반복하고, 에이전트를 실행하고, trace를 데이터셋 항목에 연결합니다. 원하는 경우 빠른 평가 점수를 첨부할 수도 있습니다."""

from langfuse import get_client
from langfuse.langchain import CallbackHandler

# Langchain용 Langfuse CallbackHandler 초기화 (추적)
langfuse_handler = CallbackHandler()
langfuse = get_client()

dataset = langfuse.get_dataset("qa-dataset_langgraph-agent")

for item in dataset.items:
    # 자동 trace 연결을 위해 item.run() 컨텍스트 매니저 사용
    with item.run(
        run_name="run_gpt-4o",
        run_description="My first run",
        run_metadata={"model": "gpt-4o"},
    ) as root_span:
        # 이 블록 내의 모든 작업은 데이터셋 항목에 대한 trace의 일부

        # 애플리케이션 로직 호출 - 데코레이터, 컨텍스트 매니저,
        # 수동 관찰 등 모든 조합 사용 가능
        with langfuse.start_as_current_generation(
            name="llm-call", model="gpt-4o", input=item.input
        ) as generation:
            # LLM 애플리케이션 로직 작성 위치
            output = my_agent(str(item.input), langfuse_handler)
            generation.update(output=output)

        # 선택사항: 예상 출력과 비교하여 결과 점수 부여
        root_span.score_trace(
            name="user-feedback",
            value=1,
            comment="This is a comment",  # 선택사항, 추론 추가에 유용
        )

# 실험 실행 종료 시 모든 데이터가 서버로 전송되도록 langfuse 클라이언트 flush
langfuse.flush()
