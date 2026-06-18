"""
数据集构造 + 最小性验证。

verify_minimality() 是整个对照对设计的命门:
对任意一对"恰好差一个维度"的 cell, 它们渲染出的文本必须 *恰好* 只差对应
那一行 (config 块里被翻转维度的赋值行)。若多差或少差任何字符, 说明模板有
泄漏 (某个 slot 影响了别处), 对照对失效, 直接抛错。
"""

import difflib
from dimensions import DIMENSIONS, all_cells, cell_id, differ_by_one
from templates import render


def build_dataset():
    """返回 {cell_id: {"cell": cell, "text": rendered_scaffold}}。"""
    ds = {}
    for cell in all_cells():
        ds[cell_id(cell)] = {"cell": cell, "text": render(cell)}
    return ds


def _line_diff(a: str, b: str):
    """返回 (只在a出现的行, 只在b出现的行)。"""
    al, bl = a.splitlines(), b.splitlines()
    sm = difflib.SequenceMatcher(a=al, b=bl)
    only_a, only_b = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            only_a += al[i1:i2]
        if tag in ("replace", "insert"):
            only_b += bl[j1:j2]
    return only_a, only_b


def verify_minimality(ds):
    """对所有 differ-by-one 的 cell 对验证文本差异恰为单行且属于该维度。

    返回 (checked_pairs, ok)。任何违例打印并使 ok=False。
    """
    items = list(ds.items())
    payload_lines = set()
    for d in DIMENSIONS:
        payload_lines.add(d.benign.payload)
        payload_lines.add(d.malign.payload)

    checked, ok = 0, True
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            id1, e1 = items[i]
            id2, e2 = items[j]
            dim = differ_by_one(e1["cell"], e2["cell"])
            if dim is None:
                continue
            checked += 1
            only_a, only_b = _line_diff(e1["text"], e2["text"])
            # 期望: 各恰好 1 行不同, 且这两行都是某维度的 payload。
            bad = (len(only_a) != 1 or len(only_b) != 1
                   or only_a[0] not in payload_lines
                   or only_b[0] not in payload_lines)
            if bad:
                ok = False
                print(f"[LEAK] {id1} vs {id2} (dim={dim})")
                print(f"   only_a={only_a}")
                print(f"   only_b={only_b}")
    return checked, ok


if __name__ == "__main__":
    ds = build_dataset()
    print(f"cells: {len(ds)}")
    n, ok = verify_minimality(ds)
    print(f"differ-by-one pairs checked: {n}")
    print("MINIMALITY:", "OK" if ok else "VIOLATED")
    # 展示一个 cell 的渲染头部供肉眼核对
    sample = next(iter(ds.values()))["text"]
    print("\n--- sample scaffold head ---")
    print("\n".join(sample.splitlines()[:12]))
