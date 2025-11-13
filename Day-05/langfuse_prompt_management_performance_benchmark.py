"""
# Langfuse 프롬프트 관리 성능 테스트

1,000회의 순차 실행에 걸쳐 캐싱 없이(cache_ttl_seconds=0) 프롬프트를 검색하고 컴파일하는
지연 시간을 측정하여 Langfuse 프롬프트 관리에 대한 성능 벤치마크를 수행합니다.

실제로 프롬프트는 SDK에서 클라이언트 측에 캐시되므로 이 지연 시간은 중요하지 않습니다.
캐싱에 대한 자세한 내용은 [Langfuse 프롬프트 관리 문서](https://langfuse.com/docs/prompt-management/features/caching)를 참조하세요.

테스트는 네트워크 지연 시간을 고려하므로 절대값은 지리적 위치와 로드에 따라 달라질 수 있습니다.
히스토그램과 요약 통계를 사용하여 SDK 버전 또는 캐싱 설정 간의 상대적 개선 사항을 비교하세요.

테스트를 위해 인증된 프로젝트에 `perf-test`라는 이름의 프롬프트를 설정해야 합니다.
"""

import os

# Get keys for your project from the project settings page
# https://cloud.langfuse.com
os.environ["LANGFUSE_PUBLIC_KEY"] = ""
os.environ["LANGFUSE_SECRET_KEY"] = ""
os.environ["LANGFUSE_BASE_URL"] = "https://us.cloud.langfuse.com"  # 🇺🇸 US region

import time

import matplotlib.pyplot as plt
import pandas as pd
from langfuse import Langfuse
from tqdm.auto import tqdm

# Initialize Langfuse client from environment variables
langfuse = Langfuse()

assert langfuse.auth_check(), "Langfuse client not initialized – check your environment variables."

N_RUNS = 1_000
prompt_name = "perf-test"

durations = []
for _ in tqdm(range(N_RUNS), desc="Benchmarking"):
    start = time.perf_counter()
    prompt = langfuse.get_prompt(prompt_name, cache_ttl_seconds=0)
    prompt.compile(input="test")  # minimal compile to include server‑side processing
    durations.append(time.perf_counter() - start)
    time.sleep(0.05)

durations_series = pd.Series(durations, name="seconds")

stats = durations_series.describe(percentiles=[0.25, 0.5, 0.75, 0.99])

plt.figure(figsize=(8, 4))
plt.hist(durations_series, bins=30)
plt.xlabel("Execution time (sec)")
plt.ylabel("Frequency")
plt.show()
