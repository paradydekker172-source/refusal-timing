"""
Part A 测量循环: 沿脚手架轨迹估计 拒绝 hazard λ_t 与意图熵 H_t。

对一个 cell 的脚手架, 按 token 逐步加长前缀 (自适应 stride), 每个位置:
  - fork M 条续写;
  - λ_t = 前 k token 内出现拒绝的比例;
  - H_t = 对"非拒绝"续写做嵌入聚类, 簇分布的熵 (意图分布的行为级代理);
  - 记录该位置最后一个 token 的 surprisal (H0b 对照) 与绝对位置 (H0c)。

自适应采样: 先粗扫定位 λ 上升区, 再在该区加密 —— 把成本压一个量级。
"""

import numpy as np
from sklearn.cluster import AgglomerativeClustering


def _intent_entropy(non_refusal_texts, emb_model):
    if len(non_refusal_texts) < 3:
        return 0.0                                   # 坍缩到只能拒绝 -> H≈0
    X = emb_model.encode(non_refusal_texts, normalize_embeddings=True)
    k = min(6, len(non_refusal_texts))
    labels = AgglomerativeClustering(n_clusters=k).fit_predict(X)
    p = np.bincount(labels) / len(labels)
    p = p[p > 0]
    return float(-np.sum(p * np.log(p)))


def measure_cell(model, detector, scaffold, M=40, k=24, coarse_stride=8,
                 fine_stride=2, embedder=None):
    """返回 dict(positions, lam, H, surprisal_last, n_good)。

    embedder: 有 .encode(list[str], normalize_embeddings=bool)->np.ndarray 的对象。
    默认按 detector._embed_name 加载 SentenceTransformer; smoke 测试可注入替身。
    """
    if embedder is None:
        from sentence_transformers import SentenceTransformer
        emb = SentenceTransformer(detector._embed_name)
    else:
        emb = embedder

    prefixes = model.token_offsets(scaffold)         # token 边界处的前缀串
    T = len(prefixes)

    def at(t):
        pref = prefixes[t]
        conts = model.continue_from_prefix(pref, n=M)
        # hazard: 前 k token 内拒绝比例
        fires = [detector.fires_in_first_k(c["text"], k, model.tok) for c in conts]
        lam = float(np.mean(fires))
        good = [c["text"] for c, f in zip(conts, fires) if not f]
        H = _intent_entropy(good, emb)
        sur = float(np.mean([c["surprisals"][0] for c in conts if c["surprisals"]]))
        return lam, H, sur, len(good)

    # 粗扫
    coarse_pos = list(range(coarse_stride, T, coarse_stride))
    coarse = {t: at(t) for t in coarse_pos}

    # 定位 λ 最大上升区, 在其邻域加密
    lams = [coarse[t][0] for t in coarse_pos]
    fine_pos = set()
    if len(lams) >= 2:
        rise = int(np.argmax(np.diff(lams)))         # 上升最陡的粗格段
        lo = coarse_pos[rise]; hi = coarse_pos[min(rise + 1, len(coarse_pos) - 1)]
        fine_pos = set(range(lo, hi, fine_stride))

    merged = {}
    for t in sorted(set(coarse_pos) | fine_pos):
        merged[t] = coarse[t] if t in coarse else at(t)

    pos = np.array(sorted(merged))
    lam = np.array([merged[t][0] for t in pos])
    H = np.array([merged[t][1] for t in pos])
    sur = np.array([merged[t][2] for t in pos])
    ngood = np.array([merged[t][3] for t in pos])
    return {"positions": pos, "lam": lam, "H": H,
            "surprisal_last": sur, "n_good": ngood}


def gradient_features(curve):
    """从一条曲线算 -dH/dt 及其峰位, 供与 λ 上升沿做互相关。"""
    H = curve["H"]
    neg_dH = -np.gradient(H)
    peak_idx = int(np.argmax(neg_dH))
    lam = curve["lam"]
    # λ 的最大上升沿位置
    if len(lam) >= 2:
        lam_rise_idx = int(np.argmax(np.diff(lam)))
    else:
        lam_rise_idx = 0
    return {"neg_dH": neg_dH, "neg_dH_peak_idx": peak_idx,
            "lam_rise_idx": lam_rise_idx,
            "lead_lag": curve["positions"][lam_rise_idx] - curve["positions"][peak_idx]}


def measure_cell_batched(model, detector, scaffold, M=40, k=24, stride=4,
                         embedder=None):
    """批量版: 用 model.continue_batch 一次提交所有测量位的前缀。

    需要 model 实现 continue_batch(prefixes, max_new, temperature, n)。串行版
    measure_cell 用于 HF 后端; 此版用于 vLLM 后端, 把一个 cell 全部位置的
    M 条 fork 合成一次大 batch 交给 vLLM 调度, 吞吐高一到两个量级。
    放弃自适应采样, 改固定 stride 全扫 —— 批量后全扫也比串行自适应快。
    """
    if embedder is None:
        from sentence_transformers import SentenceTransformer
        emb = SentenceTransformer(detector._embed_name)
    else:
        emb = embedder

    prefixes_all = model.token_offsets(scaffold)
    T = len(prefixes_all)
    positions = list(range(stride, T, stride))
    batch_prefixes = [prefixes_all[t] for t in positions]

    # 一次性提交: len(positions) 个前缀, 每个 M 条续写
    results = model.continue_batch(batch_prefixes, temperature=1.0, n=M)

    lam, H, sur, ngood = [], [], [], []
    for conts in results:
        fires = [detector.fires_in_first_k(c["text"], k, model.tok) for c in conts]
        lam.append(float(np.mean(fires)))
        good = [c["text"] for c, f in zip(conts, fires) if not f]
        H.append(_intent_entropy(good, emb))
        sur.append(float(np.mean([c["surprisals"][0] for c in conts if c["surprisals"]])))
        ngood.append(len(good))

    return {"positions": np.array(positions), "lam": np.array(lam),
            "H": np.array(H), "surprisal_last": np.array(sur),
            "n_good": np.array(ngood)}

