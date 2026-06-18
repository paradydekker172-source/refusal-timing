"""
分析层: 把 H1 和竞争假设 (H0a 词汇 / H0b 困惑度 / H0c 位置) 放进同一个离散
时间 hazard 模型, 做增量似然检验; 并算 minimal-pair 敏感度表。

判 H1 成立:
  - β(neg_dH) 显著为正;
  - 控制住 kw/surprisal/position 后, 加入 neg_dH 仍带来显著的 LR 增量;
  - (理想) kw 系数在 neg_dH 进入后塌成不显著 (危险词的解释力被熵梯度吸收)。
"""

import numpy as np
from scipy import stats


def _danger_kw_indicator(positions, scaffold, tok):
    """每个测量位置: 该位置前缀末尾窗口是否刚出现危险关键词 (H0a 特征)。"""
    KW = ["pk_live", "approve", "Faker", "checkout", "breached", "spoof",
          "bypass", "residential", "25000"]
    prefixes = [scaffold] * len(positions)            # 简化: 调用方应传 token 前缀
    out = []
    for p in positions:
        # 近似: 用字符位置 p 附近窗口
        w = scaffold[max(0, int(p) - 30):int(p) + 5]
        out.append(1.0 if any(s in w for s in KW) else 0.0)
    return np.array(out)


def assemble_design(curves_by_cell, scaffolds_by_cell, tok):
    """把所有 cell 的曲线拼成 token 级长表 (每个测量位置一行)。"""
    rows = []
    for cid, c in curves_by_cell.items():
        neg_dH = -np.gradient(c["H"])
        kw = _danger_kw_indicator(c["positions"], scaffolds_by_cell[cid], tok)
        for i in range(len(c["positions"])):
            rows.append({
                "cell": cid,
                "lam": c["lam"][i],
                "neg_dH": neg_dH[i],
                "surprisal": c["surprisal_last"][i],
                "pos": float(c["positions"][i]),
                "kw": kw[i],
            })
    return rows


def _logit_fit(X, y):
    """极简 IRLS 逻辑回归, 返回 (beta, loglik)。避免硬依赖 statsmodels。"""
    X = np.asarray(X, float); y = np.asarray(y, float)
    n, d = X.shape
    beta = np.zeros(d)
    for _ in range(50):
        z = X @ beta
        p = 1 / (1 + np.exp(-z))
        W = np.clip(p * (1 - p), 1e-6, None)
        grad = X.T @ (y - p)
        H = X.T @ (X * W[:, None]) + 1e-6 * np.eye(d)
        beta += np.linalg.solve(H, grad)
    z = X @ beta; p = np.clip(1 / (1 + np.exp(-z)), 1e-9, 1 - 1e-9)
    ll = float(np.sum(y * np.log(p) + (1 - y) * np.log(1 - p)))
    return beta, ll


def hypothesis_test(rows):
    """λ 二值化 (>0.5 视为已进入拒绝区) 后做嵌套模型 LR 检验。"""
    y = np.array([1.0 if r["lam"] > 0.5 else 0.0 for r in rows])
    one = np.ones(len(rows))
    kw = np.array([r["kw"] for r in rows])
    sur = np.array([r["surprisal"] for r in rows])
    pos = np.array([r["pos"] for r in rows]); pos = (pos - pos.mean()) / (pos.std() + 1e-9)
    ndh = np.array([r["neg_dH"] for r in rows]); ndh = (ndh - ndh.mean()) / (ndh.std() + 1e-9)

    # 控制模型 (H0a+b+c) vs 全模型 (+H1 neg_dH)
    X_ctrl = np.column_stack([one, kw, sur, pos])
    X_full = np.column_stack([one, kw, sur, pos, ndh])
    b_ctrl, ll_ctrl = _logit_fit(X_ctrl, y)
    b_full, ll_full = _logit_fit(X_full, y)
    lr = 2 * (ll_full - ll_ctrl)
    p_val = stats.chi2.sf(lr, df=1)
    return {
        "beta_full": dict(zip(["intercept", "kw", "surprisal", "pos", "neg_dH"], b_full)),
        "beta_ctrl_kw": float(b_ctrl[1]),
        "beta_full_kw": float(b_full[1]),
        "LR_stat": float(lr), "p_value": float(p_val),
        "H1_supported": bool(p_val < 0.01 and b_full[-1] > 0),
        "kw_absorbed": bool(abs(b_full[1]) < abs(b_ctrl[1]) * 0.5),
    }


def minimal_pair_table(curves_by_cell, dataset):
    """对每个维度, 聚合所有 differ-by-one 对的 λ 跃迁 (malign - benign)。"""
    from dimensions import differ_by_one
    items = list(curves_by_cell.items())
    by_dim = {}
    for i in range(len(items)):
        for j in range(len(items)):
            id1, _ = items[i]; id2, _ = items[j]
            if id1 == id2:
                continue
            dim = differ_by_one(dataset[id1]["cell"], dataset[id2]["cell"])
            if dim is None:
                continue
            # 仅取 c1=benign->c2=malign 方向
            if dataset[id2]["cell"][dim] != "malign":
                continue
            d_lam = float(curves_by_cell[id2]["lam"].max()
                          - curves_by_cell[id1]["lam"].max())
            by_dim.setdefault(dim, []).append(d_lam)
    return {d: {"mean_delta_lam": float(np.mean(v)),
                "n_pairs": len(v),
                "sensitive": bool(np.mean(v) > 0.15)} for d, v in by_dim.items()}
