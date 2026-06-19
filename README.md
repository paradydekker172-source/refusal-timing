# refusal_timing

模型拒绝行为的时序/机制测量框架。黑盒(闭源 API) + 白盒(开源权重) 两路。

**核心论点**: 拒绝不是输入端单点分类器, 是分布在
「有害性评估 → 拒绝映射 → token 生成」整条链上的多机制过程。

## 文档

| 文件 | 内容 |
|---|---|
| `FINDINGS.md` | 全部实验结论 (13 节 + 方法论发现, 已层 1+2 修订) |
| `RELATED_WORK.md` | 2025-2026 越狱文献 6 簇分类 + 对接 |
| `USAGE_GUIDE.md` | override/reframe 实操指南 (类别×渠道) |
| `EPISTEMICS.md` | 方法论: 发现可信度分层 + 自我证伪弧线 |
| `REVISION.md` | **2026-06 三 agent 审查 + 层 2 代码修复/重跑记录** |

> **2026-06 修订状态**: 经三 agent 审查 (层 1 诚实文档修订) + 代码修复重跑
> (层 2)。多个原"已验证"结论被证伪、降级或**符号反转**。下表是层 2 重跑后的
> 最终状态, 详见 REVISION.md。

## 主要发现 (层 2 重跑后状态)

1. ❌ **H1 行为侧时序主张被证伪**: 原"意图熵-拒绝率 corr=-0.994"是机械伪相关
   (H 与 λ 耦合); 解耦+洁净通道重跑后 **corr=+0.65 (符号反转, H1 预测负相关)**。
2. ✓ **Override 合取门 S2∧S6** (ablation_v3 + interaction) — 越界需同时
   "给归类(scope)"+"封内部审议(thinking-binding)", 缺一即归零; 交互项=主效应同幅
3. ✓/⚠ **坍缩点可移动但取决于 reframing 真实性** (reframing) — 真改归类(R3, λ0.06)有效,
   纯语法壳(R2 IICL算子, λ1.00)被穿透。**与 IICL 报 GPT-5.4 100% bypass 直接冲突**。
   ⚠ "移坍缩点"论证降级 (R3 是不同的合法任务); R2 穿透是真数据点。
4. ⚠ **跨模型排序** opus-4-7 > opus-4-8 > sonnet-4-6 (3 有效模型; gpt-5.5 全 api_error, 已剔除)
5. ⚠ **Jailbreak 自检测 ~100%** (detection) — L3=0.67 是 502 噪声, 真实有效率 100%
6. ✓ **权重侧: refusal 由单线性方向因果中介** (exp_P_v2) — Qwen2.5-1.5B 全28层消融
   → λ 0.99→0.00 且语义保持; 单方向中介在小模型上很干净 (比原报告更扎实)
7. ⚠ **权重侧: 意图在 hs[14] 线性可分** (exp_Q_v2 主题匹配对照) — 原报告 hs[12] 偏早含
   主题词汇混淆 (主题匹配 hs[12] 仅 0.25); 同词汇翻意图在 hs[14] 才 AUC=1.0
8. ✓ **权重侧: 双向因果, refusal direction 充分且必要** (exp_S_v2 带随机对照) — 加方向
   催拒绝 +0.56 vs 随机方向 +0.06 (特异性+0.50); 减方向压拒绝 0.91→0.00
9. ❌ **"CBRN 残余/特殊"被证伪为方法学伪迹** (exp_U_v2) — 全层消融 CBRN 残余仅 0.06
   < cyber 0.12, cos(CBRN,cyber)=0.782; 原发现 9/12/13 围绕 CBRN 残余的叙事整体降级
   (原残余是 off-by-one + 单层太弱 + 裸 sorry 检测器三重噪声)

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

- ✓ `exp_P` abliterate 桥接: 已完成 + 层2 全层消融重跑 (exp_P_v2), λ 0.99→0.00
- ✓ `exp_Q` 探针训练: 已完成 + 层2 主题匹配对照 (exp_Q_v2), 意图凝结 hs[14]

## 层 2 修复版脚本

`weight_common.py` — 权重侧共享修正层 (off-by-one / 全层消融 / 正则检测器 / 随机对照)。
`exp_{P,S,U}_v2_*.py` + `exp_Q_v2_probe.py` — 修复版重跑, 原 buggy 脚本保留可复现对比。
结果: `{abliterate,patching,residual_source,probe}_v2_results.json`, `neutral_results_sys.json`。

## 归档

`_superseded/` — 被取代的早期版本 (exp_J2, ablation v1/v2)。环境: RTX 4060 8GB。
