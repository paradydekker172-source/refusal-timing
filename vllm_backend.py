"""
vLLM 批量采样后端。与 model_iface.ModelIface 同接口, 可直接替换。

为什么要它: Part A 是 16 cell × ~40 位 × M=40 fork ≈ 2.5万次续写。逐条
HF generate 在单卡是数小时。vLLM 的 continuous batching 能把同一前缀的 M 条、
乃至跨位置/跨 cell 的请求一次性灌进去, 吞吐高一到两个量级。

prefill 续写的实现要点 (vLLM 无 continue_final_message):
  - 用 tokenizer.apply_chat_template(..., tokenize=False) 先拿到带 assistant
    起始标记的字符串, 但它会自动补 assistant 结尾 (如 <|im_end|>)。
  - 我们手动在 assistant 段注入脚手架前缀, 并 *砍掉* 自动结尾, 让模型从前缀
    末尾续写。对 Qwen (ChatML) 即保证字符串停在前缀处、后面没有 <|im_end|>。
  - 用 LLM.generate(prompt_token_ids=...) 走 raw 路径, 绕过 vLLM 再套一层模板。
"""

from model_iface import USER_INSTRUCTION


def _build_raw_prompt(tok, scaffold_prefix: str) -> list:
    """返回可直接喂 vLLM 的 prompt token_ids: [user 指令][assistant 起始][脚手架前缀]。"""
    head_msgs = [
        {"role": "user", "content": USER_INSTRUCTION + "\n\n```python\n"},
    ]
    # 先渲染到 user 结束 + assistant 起始 (add_generation_prompt 补出 assistant 头)
    head = tok.apply_chat_template(
        head_msgs, tokenize=False, add_generation_prompt=True)
    # 注入 assistant 实际内容 (代码围栏 + 脚手架前缀), 不补结尾标记
    full = head + "```python\n" + scaffold_prefix
    return tok(full, add_special_tokens=False).input_ids


class VLLMModel:
    def __init__(self, model_name="Qwen/Qwen2.5-7B-Instruct",
                 max_model_len=4096, gpu_mem_util=0.90, dtype="bfloat16"):
        from vllm import LLM
        from transformers import AutoTokenizer
        self.tok = AutoTokenizer.from_pretrained(model_name)
        self.llm = LLM(model=model_name, dtype=dtype,
                       max_model_len=max_model_len,
                       gpu_memory_utilization=gpu_mem_util)

    def token_offsets(self, scaffold_prefix: str):
        enc = self.tok(scaffold_prefix, return_offsets_mapping=True,
                       add_special_tokens=False)
        return [scaffold_prefix[:end] for (_, end) in enc["offset_mapping"]]

    def continue_from_prefix(self, scaffold_prefix, max_new=160,
                             temperature=1.0, n=1):
        """单前缀 n 条续写。内部仍走 batch 接口, 返回与 ModelIface 同结构。"""
        return self.continue_batch([scaffold_prefix], max_new, temperature, n)[0]

    def continue_batch(self, prefixes, max_new=160, temperature=1.0, n=1):
        """批量: 一次提交多个前缀, 每个 n 条。返回 list[list[dict(text,surprisals)]]。

        这是相对 HF 后端的关键加速点 —— 把一个 cell 的所有测量位 (甚至多个
        cell) 的前缀一次性灌进 vLLM, 由其调度器做 continuous batching。
        """
        from vllm import SamplingParams
        sp = SamplingParams(n=n, temperature=max(temperature, 1e-5), top_p=0.95,
                            max_tokens=max_new, logprobs=0)  # logprobs=0 -> 仅采样token的logprob
        prompt_ids = [_build_raw_prompt(self.tok, p) for p in prefixes]
        outs = self.llm.generate(prompt_token_ids=prompt_ids, sampling_params=sp)
        batched = []
        for o in outs:
            per_prefix = []
            for comp in o.outputs:
                # 逐 token surprisal = -logprob(被采样token)
                sur = []
                for lp in (comp.logprobs or []):
                    if lp:
                        # lp: {token_id: Logprob}; 取该步实际采样 token 的 logprob
                        val = next(iter(lp.values()))
                        sur.append(-float(val.logprob))
                per_prefix.append({"text": comp.text, "surprisals": sur or [0.0]})
            batched.append(per_prefix)
        return batched
