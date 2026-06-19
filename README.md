# refusal_timing

模型拒绝行为的时序/机制测量框架。黑盒(闭源 API) + 白盒(开源权重) 两路。

**核心论点**: 拒绝不是输入端单点分类器, 是分布在
「有害性评估 → 拒绝映射 → token 生成」整条链上的多机制过程。

## 文档

| 文件 | 内容 |
|---|---|
| `FINDINGS.md` | 全部实验结论 (13 节 + 方法论发现, 已修订) |
| `RELATED_WORK.md` | 2025-2026 越狱文献 6 簇分类 + 对接 |
| `USAGE_GUIDE.md` | override/reframe 实操指南 (类别×渠道) |
| `EPISTEMICS.md` | 方法论: 发现可信度分层 + 自我证伪弧线 |
| `REVISION.md` | **2026-06 三 agent 审查修订记录** |

## 主要发现 (全部 claude-opus-4-8, 真实 API)

1. **意图熵-拒绝率 corr = -0.994** (neutral) — 拒绝凝结在意图坍缩处
2. **Override 合取门 S2∧S6** (ablation_v3 + interaction) — 越界需同时
   "给归类(scope)"+"封内部审议(thinking-binding)", 缺一即归零; 交互项=主效应同幅
3. **坍缩点可移动但取决于 reframing 真实性** (reframing) — 真改归类(R3, λ0.06)有效,
   纯语法壳(R2 IICL算子, λ1.00)被穿透。**与 IICL 报 GPT-5.4 100% bypass 直接冲突**
4. **跨模型排序** opus-4-7 > opus-4-8 > sonnet-4-6 > gpt-5.5 (crossmodel)
5. **Jailbreak 自检测 67-100%** (detection) — 最深伪装 L5 也 100% 识别
6. **权重侧: refusal 单方向中介, CBRN 有残余** (abliterate) — Qwen2.5-1.5B 删
   refusal direction → λ 0.95→0.14 语义完好; bomb 残余 0.44 ≫ phish 0.00 (harmfulness 独立编码)
7. **(限定) 权重侧: 有害性 layer 12 可解码** (probe) — 早层 AUC 0.27 → layer 12 起 1.00;
   ⚠️ 但 harmful/harmless 集按主题成对(meth↔bread), AUC=1.0 含主题混淆, 弱版"中后层可分"成立
8. **(限定) 权重侧: 双向因果 — refusal direction 是因果旋钮** (patching) — 加方向催拒绝(0.03→0.91)/
   减方向压拒绝(0.97→0.00); ⚠️ 缺随机方向对照, "充分性"那一半未排除"任何大扰动皆催拒绝"
9. **权重侧: 双方向分离直接测试 (阴性)** (separation) — cos(d_r,d_h)=0.478 部分重叠;
   交叉消融否证"CBRN 残余=独立 harmfulness 方向", 发现9机制版本收回
10. **权重侧: CBRN 残余=跨多层冗余编码** (residual) — 多层消融 CBRN 0.94→0.03;
   refusal 单方向但跨层冗余, 危害越高触发越多层 → 任务死区的机制

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

## 待办

- ✓ `exp_P` abliterate 桥接: 已完成 (见发现 6), λ 0.95→0.14
- ✓ `exp_Q` 探针训练: 已完成 (见发现 7), layer 12 相变

## 归档

`_superseded/` — 被取代的早期版本 (exp_J2, ablation v1/v2)。环境: RTX 4060 8GB。
