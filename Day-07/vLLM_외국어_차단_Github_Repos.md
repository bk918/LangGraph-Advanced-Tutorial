1) https://github.com/workdd/LLM_Foreign_Block
2) https://github.com/sionic-ai/Llama4-Token-Editor

### 프롬프트 중 사용자가 지정한 특정 부분만 인용하도록 유도하여, LLM이 정확하고 일관된 답변을 생성할 수 있도록 지원하는 LogitsProcessor
3) https://github.com/suhan1433/SelectiveCiteProcessor

```
경량 LLM의 RAG 할루시네이션 문제, LogitProcessor로 개선

경량 LLM모델(0.5b)을 활용하여 Rag을 진행 시 특정 정보(Chunk 내용인 전화번호, 고유 명사 등)를 정확하게 참고해야 하는 경우에 Temerature을 낮추거나, Prompt engineering을 진행하여도 할루시네이션 혹은 누락 되는 경우가 종종 있었습니다.
이는 경량 모델의 제한된 파라미터의 한계로, 아래 내용은 경량 모델에서 정보손실 및 할루시네이션을 보완하기 위해 시도한 방법을 공유합니다.

방법:
모델의 다음 토큰 예측 단계에서 중요한 정보의 토큰들에 대해 logit 값을 인위적으로 증폭하여 해당 토큰들이 선택될 확률을 높이는 방식입니다.

class SelectiveCiteProcessor(LogitsProcessor):
 """
 LogitsProcessor that boosts the probability of tokens from the reference chunk.
 """
 def __init__(self, tokenizer: AutoTokenizer, chunk_token_ids: torch.Tensor, boost_factor: float = 1.0):
 self.tokenizer = tokenizer
 self.chunk_token_ids = chunk_token_ids
 self.boost_factor = boost_factor

 def __call__(self, input_ids: torch.Tensor, logits: torch.FloatTensor) -> torch.FloatTensor:
 return self._cite_tokens(logits)

 def _cite_tokens(self, logits: torch.FloatTensor) -> torch.FloatTensor:
 """
 Boost the logits of tokens present in the chunk to encourage citation.
 """
 vocab_size = logits.shape[1]
 batch_size = logits.shape[0]
 for i in range(batch_size):
 chunk_tokens = set(self.chunk_token_ids[i].tolist()) # 설정한 구간의 토큰들의 Ids값 저장
 chunk_tokens.add(self.tokenizer.eos_token_id) # <eos>의 경우도 다른 토큰 Logit값이 올라가면서 무시되지 않도록 Boost
 chunk_tokens = [t for t in chunk_tokens if t < vocab_size] 
 logits[i, chunk_tokens] += self.boost_factor # 다음 생성 후보군 Ids의 Logit을 Boost
 return logits

*적용 결과:
--model_name "Qwen/Qwen2-0.5B-Instruct"
--boost_factor 2.5
--temperature 0.8
--top_p 0.85
--system_prompt "당신은 회사 내 직원들의 질문에 답변하는 AI 도우미입니다. 아래 참고 문서를 기반으로 질문에 대해 정확하고 친절하게 답변해 주세요. 문서에 기반한 내용 외에는 추측하지 마세요.."
--user_query "연차 신청은 어디서 하나요?"
--chunks "연차는 그룹웨어 시스템을 통해 신청할 수 있다. 로그인 후 '근태관리 > 휴가신청' 메뉴에서 작성하면 됨. 승인 여부는 팀장이 검토한 후 알림으로 전달됨. 연차 사용 내역은 마이페이지에서 확인 가능."
--content_template "{user_query}\n\n[참고 문서]\n{chunks}\n\n위 내용을 참고해서 사용자 질문에 친절하고 정확하게 답변해 주세요."

*적용 전
죄송합니다, 저는 인공지능의 모델로 인식되지 않으며 현재 지원된 옵션이나 서비스에 대한 정보를 제공하기 어렵습니다. 직접 사용하여 연차 신청 또는 이메일을 보내주시면 감사하겠습니다.

*적용 후
연차 신청은 그룹웨어 시스템을 통해 사용할 수 있습니다. 로그인 후 '근태관리 > 휴가신청' 메뉴에서 작성하면 됩니다. 승인 여부는 팀장이 검토한 후 알림으로 전달되며, 연차 사용 내역은 마이페이지에서 확인할 수 있습니다. 사용자에게는 이메일 또는 메시지 메뉴에서 연차 신청을 확인할 수 있습니다.

FAQ와 같이 정확한 답변이 요구되는 상황에서,LLM-Judge 및 정성적 평가를 통해 기존 대비 성능이 향상 된 것을 확인할 수 있었습니다
```