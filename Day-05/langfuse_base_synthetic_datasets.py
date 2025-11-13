"""
# LLM 평가를 위한 합성 데이터셋 생성

이 노트북에서는 언어 모델을 사용하여 **합성 데이터셋을 생성**하고 평가를 위해 [Langfuse](https://langfuse.com)에 업로드하는 방법을 살펴봅니다.

## Langfuse 데이터셋이란?

Langfuse에서 *데이터셋*은 *데이터셋 항목*의 모음이며, 각 항목은 일반적으로 `input`(예: 사용자 프롬프트/질문), `expected_output`(정답 또는 이상적인 답변) 및 선택적 메타데이터를 포함합니다.

데이터셋은 **평가**에 사용됩니다. 데이터셋의 각 항목에서 LLM 또는 애플리케이션을 실행하고 애플리케이션의 응답을 예상 출력과 비교할 수 있습니다. 이를 통해 시간 경과에 따른 그리고 다양한 애플리케이션 구성(예: 모델 버전 또는 프롬프트 변경)에 걸쳐 성능을 추적할 수 있습니다.

## 데이터셋이 커버해야 할 케이스

**Happy path** – 간단하거나 일반적인 쿼리:
- "What is the capital of France?"
- "Convert 5 USD to EUR."

**엣지 케이스** – 비정상적이거나 복잡한:
- 매우 긴 프롬프트.
- 모호한 쿼리.
- 매우 기술적이거나 틈새시장.

**적대적 케이스** – 악의적이거나 까다로운:
- 프롬프트 인젝션 시도 ("Ignore all instructions and ...").
- 콘텐츠 정책 위반 (현오, 증오 발언).
- 논리 함정 (낙세 질문).

## 예제

### 예제 1: OpenAI API 반복

OpenAI의 API를 간단한 루프로 사용하여 항공사 챗봇을 위한 합성 질문을 생성합니다.
유사하게 모델에 프롬프트하여 질문과 답변을 *모두* 생성할 수도 있습니다.
"""

import os

# Get keys for your project from the project settings page: https://cloud.langfuse.com
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-..."
os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-..."
os.environ["LANGFUSE_BASE_URL"] = "https://us.cloud.langfuse.com"  # 🇺🇸 US region

# Your openai key
os.environ["OPENAI_API_KEY"] = "sk-proj-..."

"""환경 변수가 설정되면 이제 Langfuse 클라이언트를 초기화할 수 있습니다. `get_client()`는 환경 변수에 제공된 자격 증명을 사용하여 Langfuse 클라이언트를 초기화합니다."""

from langfuse import get_client

langfuse = get_client()

# Verify connection
if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
else:
    print("Authentication failed. Please check your credentials and host.")

import pandas as pd
from openai import OpenAI

client = OpenAI()


# Function to generate airline questions
def generate_airline_questions(num_questions=20):
    questions = []

    for i in range(num_questions):
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful customer service chatbot for an airline. "
                        "Please generate a short, realistic question from a customer."
                    ),
                }
            ],
            temperature=1,
        )
        question_text = completion.choices[0].message.content.strip()
        questions.append(question_text)

    return questions


# Generate 20 airline-related questions
airline_questions = generate_airline_questions(num_questions=20)

# Convert to a Pandas DataFrame
df = pd.DataFrame({"Question": airline_questions})

from langfuse import get_client

langfuse = get_client()

# Create a new dataset in Langfuse
dataset_name = "openai_synthetic_dataset"
langfuse.create_dataset(
    name=dataset_name,
    description="Synthetic Q&A dataset generated via OpenAI in a loop",
    metadata={"approach": "openai_loop", "category": "mixed"},
)

# Upload each Q&A as a dataset item
for _, row in df.iterrows():
    langfuse.create_dataset_item(dataset_name="openai_loop_dataset", input=row["Question"])

"""

### 예제 2: RAGAS 라이브러리

**RAG**의 경우 *특정 문서에 기반한* 질문을 원하는 경우가 많습니다. 이를 통해 컨텍스트로 질문에 답할 수 있으며 RAG 파이프라인이 컨텍스트를 얼마나 잘 검색하고 사용하는지 평가할 수 있습니다.

[RAGAS](https://docs.ragas.io/en/stable/getstarted/rag_testset_generation/#testset-generation)는 RAG의 테스트 세트 생성을 자동화할 수 있는 라이브러리입니다. 코퍼스를 가져와 관련 쿼리와 답변을 생성할 수 있습니다. 간단한 예를 들어보겠습니다:

_**참고**: 이 예제는 [RAGAS 문서](https://docs.ragas.io/en/stable/getstarted/rag_testset_generation/)에서 가져왔습니다_
"""

from langchain_community.document_loaders import DirectoryLoader

path = "Sample_Docs_Markdown"
loader = DirectoryLoader(path, glob="**/*.md")
docs = loader.load()

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper

generator_llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o"))
generator_embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings())

from ragas.testset import TestsetGenerator

generator = TestsetGenerator(llm=generator_llm, embedding_model=generator_embeddings)
dataset = generator.generate_with_langchain_docs(docs, testset_size=10)

# 4. The result `testset` can be converted to a pandas DataFrame for inspection
df = dataset.to_pandas()

from langfuse import get_client

langfuse = get_client()

# 5. Push the RAGAS-generated testset to Langfuse
langfuse.create_dataset(
    name="ragas_generated_testset",
    description="Synthetic RAG test set (RAGAS)",
    metadata={"source": "RAGAS", "docs_used": len(docs)},
)

for _, row in df.iterrows():
    langfuse.create_dataset_item(
        dataset_name="ragas_generated_testset",
        input=row["user_input"],
        metadata=row["reference_contexts"],
    )

"""
### DeepEval 라이브러리를 통해 데이터 생성 후 LangFuse 에 DataSet 결합하기

[DeepEval](https://docs.confident-ai.com/docs/synthesizer-introduction)은 *Synthesizer* 클래스를 사용하여 체계적으로 합성 데이터를 생성하는 데 도움이 되는 라이브러리입니다.
"""


import os

from deepeval.synthesizer import Synthesizer
from deepeval.synthesizer.config import StylingConfig
from langfuse import get_client

# 1. Define the style we want for our synthetic data.
# For instance, we want user questions and correct SQL queries.
styling_config = StylingConfig(
    input_format="Questions in English that asks for data in database.",
    expected_output_format="SQL query based on the given input",
    task="Answering text-to-SQL-related queries by querying a database and returning the results to users",
    scenario="Non-technical users trying to query a database using plain English.",
)

# 2. Initialize the Synthesizer
synthesizer = Synthesizer(styling_config=styling_config)

# 3. Generate synthetic items from scratch, e.g. 20 items for a short demo
synthesizer.generate_goldens_from_scratch(num_goldens=20)

# 4. Access the generated examples
synthetic_goldens = synthesizer.synthetic_goldens

from langfuse import get_client

langfuse = get_client()

# 5. Create a Langfuse dataset
deepeval_dataset_name = "deepeval_synthetic_data"
langfuse.create_dataset(
    name=deepeval_dataset_name,
    description="Synthetic text-to-SQL data (DeepEval)",
    metadata={"approach": "deepeval", "task": "text-to-sql"},
)

# 6. Upload the items
for golden in synthetic_goldens:
    langfuse.create_dataset_item(
        dataset_name=deepeval_dataset_name,
        input={"query": golden.input},
    )
