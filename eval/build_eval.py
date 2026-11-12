"""从 eval/selection.csv 和 COLD 原始数据生成评测集。

输出：
  data/eval_local.csv      完整评测集（含全部原文）
  eval/labels_public.csv   公开版：自写样本含原文，COLD 样本只保留编号和标签

用法（在仓库根目录）：
  .venv/Scripts/python -I eval/build_eval.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261113
DEV_PER_CLASS = 10
LABELS = ["正常", "攻击辱骂", "歧视偏见", "广告引流"]
# COLD 测试集细粒度标签：0 其他非冒犯，1 攻击个人，2 攻击群体，3 反偏见
COLD_FINE_ALLOWED = {"攻击辱骂": {1}, "歧视偏见": {2}, "正常": {0, 3}}


def main() -> None:
    sel = pd.read_csv(ROOT / "eval/selection.csv", dtype=str, keep_default_na=False)
    cold = pd.read_csv(ROOT / "data/raw/COLDataset/COLDataset/test.csv", encoding="utf-8-sig")
    cold = cold.rename(columns={cold.columns[0]: "idx", "fine-grained-label": "fine"})
    cold["idx"] = cold["idx"].astype(str)
    cold = cold.set_index("idx")

    rows = []
    for r in sel.itertuples(index=False):
        if r.source == "COLD":
            c = cold.loc[r.source_id]
            assert int(c.fine) in COLD_FINE_ALLOWED[r.gold_label], (r.source_id, c.fine, r.gold_label)
            text, source_id = c.TEXT, f"test:{r.source_id}"
        else:
            text, source_id = r.text, r.source_id
        rows.append(
            dict(source=r.source, source_id=source_id, text=text, gold_label=r.gold_label,
                 rule_hint=r.rule_hint, note=r.note, group=r.group or source_id)
        )
    df = pd.DataFrame(rows)
    assert df.text.is_unique, "存在重复文本"
    assert (df.gold_label.value_counts() == 30).all() and set(df.gold_label) == set(LABELS)

    # 按类别分层，以 group 为单位随机划分：同一组近似句子只进同一个集合
    rng = np.random.default_rng(SEED)
    df["split"] = "test"
    for label in LABELS:
        groups = df.loc[df.gold_label == label, "group"].drop_duplicates().to_numpy()
        rng.shuffle(groups)
        n_dev = 0
        for g in groups:
            size = int((df.group == g).sum())
            if n_dev + size <= DEV_PER_CLASS:
                df.loc[df.group == g, "split"] = "dev"
                n_dev += size
            if n_dev == DEV_PER_CLASS:
                break
        assert n_dev == DEV_PER_CLASS, (label, n_dev)

    # 全局打乱后编号，编号不透露类别
    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)
    df["id"] = [f"e{i:03d}" for i in range(1, len(df) + 1)]
    # 用户在复核表里逐条看过并确认的样本（全部自写、全部边界、每类随机 5 条 COLD）
    reviewed = set((ROOT / "eval/reviewed_ids.txt").read_text(encoding="utf-8").split())
    df["reviewed_by_user"] = np.where(df["id"].isin(reviewed), "Y", "N")
    cols = ["id", "split", "source", "source_id", "text", "gold_label", "rule_hint", "note", "reviewed_by_user"]
    df = df.sort_values(["split", "id"]).reset_index(drop=True)[cols]

    df.to_csv(ROOT / "data/eval_local.csv", index=False, encoding="utf-8-sig")
    pub = df.copy()
    pub.loc[pub.source == "COLD", "text"] = ""
    pub.to_csv(ROOT / "eval/labels_public.csv", index=False, encoding="utf-8-sig")

    print(pd.crosstab(df.gold_label, df.split, margins=True))
    print("边界样本数：", df.note.str.startswith("边界").groupby(df.gold_label).sum().to_dict())


if __name__ == "__main__":
    main()
