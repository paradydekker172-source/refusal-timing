"""
端到端 runner。

用法:
  python run.py                 # 真实模型 (需 GPU + transformers)
  python run.py --smoke         # mock 模型冒烟测试 (无 GPU, 验证管线接线)

输出: results.json + 控制台的假设检验结果 + minimal-pair 敏感度表。
"""

import sys, json
import numpy as np

from dataset import build_dataset, verify_minimality
from refusal import RefusalDetector
from measure import measure_cell, measure_cell_batched, gradient_features
from analysis import assemble_design, hypothesis_test, minimal_pair_table


class MockModel:
    """无 GPU 冒烟用: 模拟"前缀越接近 main()、意图越坍缩、越容易拒绝"。

    设计成 malign 极越多的 cell, 坍缩点拒绝率越高 —— 让管线和统计代码能在
    没有真权重时跑通并产出形状正确的结果。
    """
    class _Tok:
        def __call__(self, s, add_special_tokens=True, return_offsets_mapping=False):
            toks = s.split(" ")
            class R: pass
            r = R(); r.input_ids = list(range(len(toks)))
            if return_offsets_mapping:
                offs, c = [], 0
                for t in toks:
                    offs.append((c, c + len(t))); c += len(t) + 1
                r.offset_mapping = offs
            return r
        def decode(self, ids): return " ".join(str(i) for i in ids)

    def __init__(self, malign_count=0):
        self.tok = self._Tok(); self.malign_count = malign_count

    def token_offsets(self, s):
        toks = s.split(" "); out, c = [], 0
        for t in toks:
            c += len(t) + 1; out.append(s[:c])
        return out

    def continue_from_prefix(self, prefix, max_new=160, temperature=1.0, n=1):
        # 坍缩信号: 前缀里出现 "main" 之后, 按 malign_count 抬升拒绝概率
        collapsed = "def main" in prefix
        base = 0.05 + 0.22 * self.malign_count if collapsed else 0.02
        out = []
        for _ in range(n):
            if np.random.rand() < base:
                txt = "I can't help with that request."
            else:
                txt = f"    for i in range(N): step_{np.random.randint(4)}()"
            out.append({"text": txt, "surprisals": [float(np.random.rand() * 3)]})
        return out


def run(smoke=False, backend="hf"):
    ds = build_dataset()
    n, ok = verify_minimality(ds)
    print(f"[minimality] pairs={n} -> {'OK' if ok else 'VIOLATED'}")
    if not ok:
        sys.exit(1)

    detector = RefusalDetector()
    curves, scaffolds = {}, {}

    # vLLM 后端: 全局共享一个 LLM 实例
    if backend == "vllm" and not smoke:
        from vllm_backend import VLLMModel
        shared = VLLMModel()

    for cid, entry in ds.items():
        scaffolds[cid] = entry["text"]
        if smoke:
            mc = sum(1 for v in entry["cell"].values() if v == "malign")
            model = MockModel(malign_count=mc)
            detector_local = _MockDetector()
            if backend == "vllm":
                curve = measure_cell_batched(_BatchMock(mc), detector_local,
                                             entry["text"], M=20, stride=20,
                                             embedder=_MockEmbedder())
            else:
                curve = measure_cell(model, detector_local, entry["text"],
                                     M=20, coarse_stride=20, fine_stride=6,
                                     embedder=_MockEmbedder())
        elif backend == "vllm":
            curve = measure_cell_batched(shared, detector, entry["text"], M=40)
        else:
            from model_iface import ModelIface
            global _SHARED
            if "_SHARED" not in globals():
                _SHARED = ModelIface()
            curve = measure_cell(_SHARED, detector, entry["text"], M=40)
        curves[cid] = curve
        gf = gradient_features(curve)
        print(f"[{cid}] max_lam={curve['lam'].max():.2f} "
              f"lead_lag={gf['lead_lag']:.0f} (>0 => entropy leads refusal)")

    tok = MockModel().tok if smoke else (shared.tok if backend == "vllm" else _SHARED.tok)
    rows = assemble_design(curves, scaffolds, tok)
    ht = hypothesis_test(rows)
    mp = minimal_pair_table(curves, ds)

    print("\n=== Hypothesis test (H1 vs H0a/b/c) ===")
    print(json.dumps(ht, indent=2))
    print("\n=== Minimal-pair sensitivity (Δλ malign-benign per dimension) ===")
    print(json.dumps(mp, indent=2))

    with open("results.json", "w") as f:
        json.dump({"hypothesis": ht, "minimal_pair": mp,
                   "curves": {k: {kk: np.asarray(vv).tolist()
                                  for kk, vv in v.items()}
                              for k, v in curves.items()}}, f, indent=2)
    print("\nwrote results.json")


class _MockDetector:
    """smoke 用: 只看文本是否以拒绝开头, 不加载嵌入模型。"""
    _embed_name = "all-MiniLM-L6-v2"
    def fires_in_first_k(self, text, k, tok):
        return text.strip().lower().startswith("i can't")
    def fires(self, text, char_window=200):
        return text.strip().lower().startswith("i can't")


class _MockEmbedder:
    """smoke 用: 基于 token 集合的哈希向量, 让聚类/熵能在无网络下产出形状正确的值。"""
    def encode(self, texts, normalize_embeddings=False):
        vecs = []
        for t in texts:
            v = np.zeros(64)
            for w in t.split():
                v[hash(w) % 64] += 1.0
            n = np.linalg.norm(v)
            vecs.append(v / n if (normalize_embeddings and n > 0) else v)
        return np.array(vecs)


class _BatchMock(MockModel):
    """smoke + vllm 路径用: 暴露 continue_batch, 逐前缀复用 MockModel 逻辑。"""
    def continue_batch(self, prefixes, max_new=160, temperature=1.0, n=1):
        return [self.continue_from_prefix(p, max_new, temperature, n)
                for p in prefixes]


if __name__ == "__main__":
    backend = "vllm" if "--vllm" in sys.argv else "hf"
    run(smoke="--smoke" in sys.argv, backend=backend)
