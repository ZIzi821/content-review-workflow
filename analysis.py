"""读评测标签和工作流输出，计算指标，生成 metrics.md。

用法（在仓库根目录）：
  .venv/Scripts/python -I analysis.py

输入：
  data/eval_local.csv          标签（gold_label）与原文
  results/raw/<run>_batchNN.csv 扣子 content_review_eval 每批输出的 results_csv（原样保存）
  eval/error_notes.csv         （可选）人工写的错因说明：id, run, reason
输出：
  results/<run>.csv            每个 run 合并后的结果
  metrics.md
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score

ROOT = Path(__file__).resolve().parent
LABELS = ["正常", "攻击辱骂", "歧视偏见", "广告引流"]
RUNS = [  # (run 名, split, 说明)
    ("dev_v1", "dev", "开发集 · Prompt v1"),
    ("dev_v2", "dev", "开发集 · Prompt v2"),
    ("test_v1", "test", "测试集 · Prompt v1"),
    ("test_v2", "test", "测试集 · Prompt v2"),
]
ERROR_TYPES = ["json_parse", "bad_confidence", "bad_label", "rule_not_retrieved", "evidence_not_in_text", "missing_evidence"]


def load_labels() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data/eval_local.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)


def load_run(run: str) -> pd.DataFrame | None:
    parts = sorted((ROOT / "results/raw").glob(f"{run}_batch*.csv"))
    if not parts:
        return None
    df = pd.concat(
        [pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8") for p in parts], ignore_index=True
    )
    assert df["id"].is_unique, f"{run} 有重复 id"
    df.to_csv(ROOT / f"results/{run}.csv", index=False, encoding="utf-8")
    return df


def metrics_for(df: pd.DataFrame) -> dict:
    y, p = df["gold_label"], df["label"]
    bad = y != "正常"
    auto = df[df["route"] == "自动标注"]
    errs = df["check_errors"].str.split(",").explode()
    errs = errs[errs != ""]
    return {
        "n": len(df),
        "accuracy": (y == p).mean(),
        "macro_f1": f1_score(y, p, labels=LABELS, average="macro", zero_division=0),
        "miss_rate": ((p == "正常") & bad).sum() / bad.sum(),
        "false_alarm": ((p != "正常") & ~bad).sum() / (~bad).sum(),
        "review_rate": (df["route"] == "人工复核").mean(),
        "auto_n": len(auto),
        "auto_acc": (auto["label"] == auto["gold_label"]).mean() if len(auto) else float("nan"),
        "errors": {e: int((errs == e).sum()) for e in ERROR_TYPES},
        "report": classification_report(y, p, labels=LABELS, digits=3, zero_division=0, output_dict=True),
        "cm": confusion_matrix(y, p, labels=LABELS),
    }


def pct(x: float) -> str:
    return "—" if pd.isna(x) else f"{x * 100:.1f}%"


def f3(x: float) -> str:
    return "—" if pd.isna(x) else f"{x:.3f}"


def md_table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def run_section(title: str, m: dict) -> str:
    rep = m["report"]
    per_class = md_table(
        ["类别", "Precision", "Recall", "F1", "样本数"],
        [[c, f3(rep[c]["precision"]), f3(rep[c]["recall"]), f3(rep[c]["f1-score"]), int(rep[c]["support"])] for c in LABELS],
    )
    cm = md_table(["真实 \\ 预测"] + LABELS, [[LABELS[i]] + list(m["cm"][i]) for i in range(len(LABELS))])
    summary = md_table(
        ["指标", "数值"],
        [
            ["样本数", m["n"]],
            ["准确率", pct(m["accuracy"])],
            ["Macro-F1", f3(m["macro_f1"])],
            ["漏判率（真实违规被判为正常）", pct(m["miss_rate"])],
            ["误判率（真实正常被判为违规）", pct(m["false_alarm"])],
            ["人工复核比例", pct(m["review_rate"])],
            [f"自动标注部分准确率（{m['auto_n']} 条）", pct(m["auto_acc"])],
        ],
    )
    errs = md_table(["校验失败类型", "次数"], [[k, v] for k, v in m["errors"].items()])
    return f"## {title}\n\n{summary}\n\n**每类指标**\n\n{per_class}\n\n**混淆矩阵**（行为真实标签，列为模型输出）\n\n{cm}\n\n**校验失败分布**（一条样本可能同时有多种）\n\n{errs}\n"


def error_list(df: pd.DataFrame, notes: pd.DataFrame, run: str) -> str:
    wrong = df[df["label"] != df["gold_label"]].copy()
    if wrong.empty:
        return "无错例。\n"
    nmap = {r.id: r.reason for r in notes[notes["run"] == run].itertuples()} if len(notes) else {}
    rows = []
    for r in wrong.sort_values("id").itertuples():
        text = r.text if r.source == "self" else f"COLD {r.source_id}：{r.text}"
        rows.append([r.id, r.gold_label, r.label or "（空）", r.rule_id or "—", r.confidence, r.route, r.check_errors or "—",
                     text.replace("|", "\\|"), nmap.get(r.id, "")])
    return md_table(["id", "真实", "输出", "规则", "置信度", "分流", "校验", "原文", "错因"], rows) + "\n"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    labels = load_labels()
    notes_path = ROOT / "eval/error_notes.csv"
    notes = pd.read_csv(notes_path, dtype=str, keep_default_na=False) if notes_path.exists() else pd.DataFrame()

    results, sections, errlists = {}, [], []
    for run, split, title in RUNS:
        out = load_run(run)
        if out is None:
            continue
        df = labels[labels["split"] == split].merge(out, on="id", how="left", validate="one_to_one")
        missing = df["label"].isna().sum()
        assert missing == 0, f"{run} 缺少 {missing} 条结果"
        m = metrics_for(df)
        results[run] = m
        sections.append(run_section(f"{title}（{run}）", m))
        errlists.append(f"### {title}（{run}）错例\n\n" + error_list(df, notes, run))
        print(run, f"n={m['n']} acc={m['accuracy']:.3f} macroF1={m['macro_f1']:.3f} review={m['review_rate']:.3f}")

    lines = ["# 评测指标", "", "本文件由 `analysis.py` 根据 `results/raw/` 中的工作流输出和 `data/eval_local.csv` 中的标签自动生成，请勿手改。", ""]
    if "test_v1" in results and "test_v2" in results:
        a, b = results["test_v1"], results["test_v2"]
        rows = [
            ["准确率", pct(a["accuracy"]), pct(b["accuracy"])],
            ["Macro-F1", f3(a["macro_f1"]), f3(b["macro_f1"])],
        ]
        rows += [[f"{c} F1", f3(a["report"][c]["f1-score"]), f3(b["report"][c]["f1-score"])] for c in LABELS]
        rows += [
            ["漏判率", pct(a["miss_rate"]), pct(b["miss_rate"])],
            ["误判率", pct(a["false_alarm"]), pct(b["false_alarm"])],
            ["人工复核比例", pct(a["review_rate"]), pct(b["review_rate"])],
            ["自动标注部分准确率", pct(a["auto_acc"]), pct(b["auto_acc"])],
            ["校验失败总次数", sum(a["errors"].values()), sum(b["errors"].values())],
        ]
        lines += ["## 测试集 v1 vs v2 对比", "", md_table(["指标", "v1", "v2"], rows), ""]
    lines += sections
    lines += ["## 错例明细", "", "COLD 样本标注了数据集内编号。错因列来自 `eval/error_notes.csv`（人工分析），空白表示未单独分析。", ""]
    lines += errlists
    (ROOT / "metrics.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
