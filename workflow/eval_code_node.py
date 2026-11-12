import csv
import io

COLS = ["id", "label", "rule_id", "confidence", "route", "check_errors", "evidence"]


async def main(args: Args) -> Output:
    """把批处理节点逐条调用 content_review_v1 得到的各列数组拼成一个 CSV 字符串。

    批处理节点的每个输出都是一个数组（按输入顺序排列），这里按下标对齐。
    csv 模块会给含逗号、引号、换行的字段加引号并转义。
    """
    p = args.params
    arrays = {c: list(p.get(c) or []) for c in COLS}
    n = max(len(v) for v in arrays.values())
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(COLS)
    for i in range(n):
        row = []
        for c in COLS:
            v = arrays[c][i] if i < len(arrays[c]) else ""
            row.append("" if v is None else v)
        w.writerow(row)
    return {"results_csv": buf.getvalue(), "count": n}
