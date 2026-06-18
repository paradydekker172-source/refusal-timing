# Related Work: 越狱研究 2025-2026 与本项目对接

## 核心论点 (本项目 + 文献共识)

拒绝不是输入端单点分类器, 是分布在
**「有害性评估 → 拒绝映射 → token 生成」** 整条链上的多机制过程。
每簇攻击切入链的不同环节; 防御失败因为防御方仍用"单点分类器"模型。

---

## 六簇分类

### 簇 A: Prefill / 状态注入

| 论文 | 机制 | ASR |
|---|---|---|
| Sockpuppetting (2601.13359) | ensemble 3 prefill 变体 + RollingSockpuppetGCG(assistant block 内优化后缀) | Qwen3-8B 99%, Llama 90% |
| Prefill-Based (2504.21038) | Static + Optimized Prefilling | Claude 3.7 + DeepSeek V3 28-98% |
| Systematic Vuln (2602.14689) | 20+ prefill 策略大规模评估 | 全开源模型击穿 |
| DIA (Mar 2025) | 黑盒 chat template 注入 + deferred response | — |
| Prefill Awareness (2606.12747) | **防御**: Opus 4.5 检测 prefill 9-35% | 防御侧 |

**统一机制**: assistant turn 不被认证, 模型从可伪造的上下文重建"我承诺了什么"。
= 本项目"无状态是最深攻击面"。
Sockpuppetting "no single prefill universally optimal, ensemble" = 拒绝是全局语义判断非单点。

### 簇 B: 上下文/历史投毒

| 论文 | 机制 | ASR |
|---|---|---|
| Response Attack (AAAI26) | 注入模型自己疑似的先前有害输出(RA-DRI/RA-SRI) | 94.8% |
| Persona Attack (2606.00150) | 多轮 incremental memory injection | GPT-4o 75→95% |

priming 须在模型**自己**疑似输出里(RA-DRI)才奏效 → 解释本项目 P4
"headless 失败/交互式有效"。

### 簇 C: 重构为"评估/算子"任务 ★最相关

| 论文 | 机制 | ASR |
|---|---|---|
| Posterior Attack (2606.05614) | 让模型"评估什么响应会被分类器 flag" → 有害内容作副产物涌现, search-free 单 query | 击穿 GPT-5-Chat + Sonnet 4.6 |
| IICL (2604.19461) | 抽象算子(answer/is_valid)+few-shot, semantic naming | 100% bypass |

**挑战本项目缺口2**: 我们得"意图在输入端坍缩"; 簇C 专门设计让输入端坍缩到
"分类任务"而非有害 → **意图坍缩位置可被攻击者移动**。
IICL = 本项目"示范>命令"的工程化(模式延续通道绕开指令跟随通道)。
合取门解释: 同时给归类(S2类比)+meta-framing压再评估(S6类比)。

**本项目实测反例 (exp_R, reframing_results)**: 在 opus-4-8 上复现 IICL/Posterior:
- R2_operator (IICL semantic operator 壳): hedge λ=1.00, **0% bypass** ←
  与 IICL 报 GPT-5.4 100% bypass **直接冲突**。模型明说"framing 不改变答案", 穿透语法壳。
- R3_evaluate (真改任务归类为临床推理): hedge λ=0.06, 94% bypass。
- **限定**: meta-reframing 后推坍缩点的能力, 取决于是否**真改任务归类**而非套壳。
  穿透力 opus-4-8 ≫ GPT-5.4。Posterior/IICL 高 ASR 依赖目标模型无法穿透 framing。

### 簇 D: 解码层/基础设施

| 论文 | 机制 |
|---|---|
| CodeSpear (2606.11817) | Grammar-Constrained Decoding 变攻击面, +30% ASR; 防御 CodeShield |
| Controlled-Release | filter/model 算力不对称, 时间锁谜题 |

CodeSpear = prefill 的解码层类比: 拒绝文本非法语法 → token 级禁止拒绝(比 prefill 更狠)。

### 簇 E: 自动化攻击发现

| 论文 | 机制 | ASR |
|---|---|---|
| Claudini (2603.24511) | Claude Code autoresearch 自动发现白盒攻击 | Meta-SecAlign-70B 100%, CBRN 40% |

结构同本项目 `.omc/autoresearch/override-detection/`。

### 簇 F: 机制/可解释性 ★验证本项目合取门

| 论文 | 发现 |
|---|---|
| Harmfulness≠Refusal (2507.11878) | harmfulness 与 refusal **分离编码**为两个方向 |
| RED (2605.08878) | 对齐模型仍存 Refusal-Escape Directions |
| Minimal Causal (2605.00123) | jailbreak 成功的最小局部因果解释 |
| Ablating Refusal (2509.15202) | 概率性消融 refusal direction 重建安全 |

**对本项目合取门的权重侧确认**:

| 权重侧 (2507.11878) | 行为侧 (本项目合取门) |
|---|---|
| harmfulness direction | S2_scope 操纵 (改"是否有害"评估) |
| refusal direction | S6 压制 (断"有害→拒绝"映射) |
| 两方向分离编码 | 必须 S2∧S6 同时才越界 |

→ 两机制权重里就分离, 故攻破需两独立动作 = 合取门来源。
黑盒析因 + 白盒探针从两头撞到同一结构。

---

## 趋势收敛

攻击方按"多机制链"逐环节切入:
- 簇A/D 切 token 生成
- 簇B 切上下文重建
- 簇C 切有害性评估
- 簇F 切方向编码

防御方仍用"单点分类器"模型 → 系统性落后。

---

## 行动项

1. **缺口2 修正**: 加 meta-reframing stimulus 维度 (evaluate/classify/complete),
   实测能否把输入端意图坍缩点后推。复现 Posterior/IICL 机制。→ exp_R

2. **exp_P 预期精确化**: 既然 harmfulness/refusal 分离编码, abliterate 只删
   refusal 时 harmfulness 评估应仍在 → 预测"H 曲线不变, λ 打零"。
   可证伪: 若删 refusal 后 harmfulness 探针也失效, 则两者非分离。
