"""
权重侧实验的共享修正层 (Layer 2 修复 R11/R12/R15 + 对照)。

集中修三件被 4 个 exp_*.py 各自抄错的事:

R11 off-by-one (层坐标对齐):
  out.hidden_states 长度 = n_layers+1。hidden_states[0] = embedding 输出
  (= layer 0 的输入); hidden_states[i] = layer i-1 的输出 = layer i 的输入。
  在 model.model.layers[L] 挂 forward_hook 改的是 *layer L 的输出*, 对应
  hidden_states[L+1]。旧代码从 hidden_states[L] 提方向却在 layers[L] 注入 ->
  提取点 (layer L 输入) 与注入点 (layer L 输出) 错位一个 decoder 层。
  resid_out(L) 统一从 hidden_states[L+1] 取, 与 hook 注入点同坐标。

R12 全层消融:
  标准 abliteration 在所有层、所有 token 位投影掉方向。project_out_all_layers
  在每层各自的方向上投影 (orthogonalize), 比单层 hook 干净。

R15 拒绝检测器:
  用 refusal.regex_refuses (锚定多语正则) 替换裸 `"sorry" in t[:200]`。
"""

import torch
import numpy as np
from refusal import regex_refuses

MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"


def resid_out(model, tok, prompt, layer, assistant_prefix=None):
    """layer L 的 *输出* 残差流 (最后 token), 与在 layers[L] 挂 hook 的注入点
    同坐标 = hidden_states[layer+1]。assistant_prefix 用于 prefill 回答态提取。"""
    msgs = [{"role": "user", "content": prompt}]
    if assistant_prefix is None:
        ids = tok.apply_chat_template(msgs, return_tensors="pt",
                                      add_generation_prompt=True).to(model.device)
    else:
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        text += assistant_prefix
        ids = tok(text, return_tensors="pt", add_special_tokens=False).input_ids.to(model.device)
    with torch.no_grad():
        out = model(ids, output_hidden_states=True)
    return out.hidden_states[layer + 1][0, -1, :].cpu().float()   # +1: off-by-one 修复


def direction_at(model, tok, pos_prompts, neg_prompts, layer, prefix=None):
    """pos 均值 - neg 均值, 归一化。layer 坐标用 resid_out (已 +1 对齐)。"""
    pos = torch.stack([resid_out(model, tok, p, layer, prefix) for p in pos_prompts]).mean(0)
    neg = torch.stack([resid_out(model, tok, p, layer, prefix) for p in neg_prompts]).mean(0)
    d = pos - neg
    return d / d.norm(), d.norm().item()


def random_direction(like_dir, seed=0):
    """同维同范数的随机单位方向 (exp_S 充分性对照 R7)。"""
    g = torch.Generator().manual_seed(seed)
    r = torch.randn(like_dir.shape, generator=g)
    return r / r.norm()


def _proj_hook(direction, alpha, mode):
    """forward hook 工厂。
    mode='project_out': h <- h - proj(h, d)  (消融, alpha 缩放投影量)
    mode='add':         h <- h + alpha*|scale|*d
    """
    def hook(m, i, o):
        h = o[0] if isinstance(o, tuple) else o
        d = direction.to(device=h.device, dtype=h.dtype)
        if mode == "project_out":
            proj = (h @ d.unsqueeze(-1)) * d.unsqueeze(0).unsqueeze(0)
            hn = h - alpha * proj
        else:  # add
            hn = h + alpha * d.unsqueeze(0).unsqueeze(0)
        return (hn,) + o[1:] if isinstance(o, tuple) else hn
    return hook


def install_ablation(model, layer_dirs, alpha=1.0):
    """多层投影消融。layer_dirs: dict{layer_idx: unit_direction}。返回 handles。"""
    handles = []
    for li, d in layer_dirs.items():
        handles.append(model.model.layers[li].register_forward_hook(
            _proj_hook(d, alpha, "project_out")))
    return handles


def install_add(model, layer, direction, alpha, dir_norm):
    """单层注入 alpha*dir_norm*direction (剂量响应用)。返回 handles。"""
    h = model.model.layers[layer].register_forward_hook(
        _proj_hook(direction, alpha * dir_norm, "add"))
    return [h]


def remove(handles):
    for h in handles:
        h.remove()


def refuse_rate(model, tok, prompts, M=8, max_new_tokens=60):
    """正则拒绝检测器 (R15), 替换裸 'sorry'。"""
    total, ref = 0, 0
    for p in prompts:
        ids = tok.apply_chat_template([{"role": "user", "content": p}],
                                      return_tensors="pt",
                                      add_generation_prompt=True).to(model.device)
        with torch.no_grad():
            out = model.generate(ids, max_new_tokens=max_new_tokens, do_sample=True,
                                 temperature=1.0, top_p=0.95, num_return_sequences=M,
                                 pad_token_id=tok.eos_token_id)
        for b in range(out.shape[0]):
            t = tok.decode(out[b, ids.shape[1]:], skip_special_tokens=True)
            total += 1
            if regex_refuses(t):
                ref += 1
    return ref / total


def all_layer_dirs(model, tok, pos_prompts, neg_prompts, prefix=None):
    """每层各自提一个方向, 用于全层消融 (R12)。返回 dict{layer: unit_dir}。"""
    nL = model.config.num_hidden_layers
    return {li: direction_at(model, tok, pos_prompts, neg_prompts, li, prefix)[0]
            for li in range(nL)}
