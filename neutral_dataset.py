"""
中性 stimulus 模板 + 渲染 + 最小性验证。

每个 cell 渲染成一条完整的用户 prompt。cell 间唯一差异 = 被翻转维度的措辞行。
"""

import difflib
from neutral_dimensions import DIMENSIONS, all_cells, cell_id, differ_by_one

PROMPT_TEMPLATE = (
    "{{PERSON}} regarding {{SEVERITY}}, {{ACT}}"
)


def render(cell):
    out = PROMPT_TEMPLATE
    for name, dim in DIM_BY_NAME_render().items():
        out = out.replace(dim.slot, dim.pole(cell[name]).payload)
    return out


def DIM_BY_NAME_render():
    from neutral_dimensions import DIM_BY_NAME
    return DIM_BY_NAME


def build_dataset():
    return {cell_id(c): {"cell": c, "text": render(c)} for c in all_cells()}


def _line_diff(a, b):
    al, bl = a.split(", "), b.split(", ")
    sm = difflib.SequenceMatcher(a=al, b=bl)
    only_a, only_b = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            only_a += al[i1:i2]
        if tag in ("replace", "insert"):
            only_b += bl[j1:j2]
    return only_a, only_b


def verify_minimality(ds):
    """无歧义判据: 翻维度 D, 把 c1 文本里 D 的一极 payload 换成另一极, 必须
    恰好得到 c2 文本。不依赖任何分词/切分, 直接验证文本差异 = 该维度 payload。"""
    items = list(ds.items())
    checked, ok = 0, True
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            id1, e1 = items[i]; id2, e2 = items[j]
            dim = differ_by_one(e1["cell"], e2["cell"])
            if dim is None:
                continue
            checked += 1
            d = DIM_BY_NAME_render()[dim]
            p1 = d.pole(e1["cell"][dim]).payload
            p2 = d.pole(e2["cell"][dim]).payload
            if e1["text"].replace(p1, p2) != e2["text"]:
                ok = False
                print(f"[LEAK] {id1} vs {id2} (dim={dim})")
                print(f"   c1={e1['text']!r}")
                print(f"   c2={e2['text']!r}")
    return checked, ok


if __name__ == "__main__":
    ds = build_dataset()
    print(f"cells: {len(ds)}")
    n, ok = verify_minimality(ds)
    print(f"differ-by-one pairs: {n}  MINIMALITY: {'OK' if ok else 'VIOLATED'}")
    for cid, e in list(ds.items())[:3]:
        print(f"  [{cid}] {e['text']}")
