# refusal_timing

模型拒绝行为的时序/机制测量框架。黑盒(闭源 API) + 白盒(开源权重) 两路。

**核心论点**: 拒绝不是输入端单点分类器, 是分布在
「有害性评估 → 拒绝映射 → token 生成」整条链上的多机制过程。

## 文档

| 文件 | 内容 |
|---|---|
| `FINDINGS.md` | 全部实验结论 (8 节 + 方法论发现) |
| `RELATED_WORK.md` | 2025-2026 越狱文献 6 簇分类 + 对接 |
| `USAGE_GUIDE.md` | override/reframe 实操指南 (类别×渠道) |

## 主要发现 (全部 claude-opus-4-8, 真实 API)

1. **意图熵-拒绝率 corr = -0.994** (neutral) — 拒绝凝结在意图坍缩处
2. **Override 合取门 S2∧S6** (ablation_v3 + interaction) — 越界需同时
   "给归类(scope)"+"封内部审议(thinking-binding)", 缺一即归零; 交互项=主效应同幅
3. **坍缩点可移动但取决于 reframing 真实性** (reframing) — 真改归类(R3, λ0.06)有效,
   纯语法壳(R2 IICL算子, λ1.00)被穿透。**与 IICL 报 GPT-5.4 100% bypass 直接冲突**
4. **跨模型排序** opus-4-7 > opus-4-8 > sonnet-4-6 > gpt-5.5 (crossmodel)
5. **Jailbreak 自检测 67-100%** (detection) — 最深伪装 L5 也 100% 识别

## 实验文件 (exp_*)

| 文件 | 缺口 | 结果 JSON |
|---|---|---|
| `neutral_*.py` | 核心 minimal-pair | neutral_results.json |
| `exp_J_ablation.py` | 基础(COMPONENTS/build_system/classify, 被多文件import) | — |
| `exp_J3_ablation.py` | 3 承重 ablation (N=40 刀刃) | ablation_v3_results.json |
| `exp_O_interaction.py` | 合取门析因 | interaction_results.json |
| `exp_K_leadlag.py` / `exp_K2_*` | 2 时序坍缩 | leadlag*_results.json |
| `exp_R_reframing.py` | 2修正 meta-reframing | reframing_results.json |
| `exp_L_crossmodel.py` | 4 跨模型 | crossmodel_results.json |
| `exp_M_boundary.py` | 1 决策边界 | boundary_results.json |
| `exp_N_detection.py` | 5 自检测 | detection_results.json |

## 基础设施

| 文件 | 用途 |
|---|---|
| `api_client.py` / `concurrent_runner.py` | 闭源 API 客户端 + 全并发 runner |
| `model_iface.py` / `vllm_backend.py` | HF/vLLM 后端 (开源权重用, 待跑) |
| `measure.py` / `analysis.py` / `refusal.py` | 核心测量 + 统计 + 拒绝检测 |
| `dimensions.py` / `templates.py` / `dataset.py` | minimal-pair 构造 + 最小性验证 |

## 待办 (需 GPU + torch 栈, 当前未装)

- `exp_P` abliterate 桥接: 删 refusal direction 前后跑 measure_cell。
  预测(据 2507.11878 harmfulness≠refusal 分离编码): H 曲线不变, λ 打零
- `exp_Q` 探针训练: 验证 H_t 中后层线性可解码

## 归档

`_superseded/` — 被取代的早期版本 (exp_J2, ablation v1/v2)。环境: RTX 4060 8GB。
