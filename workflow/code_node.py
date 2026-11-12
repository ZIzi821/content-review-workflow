import json
import re

LABELS = {"正常", "攻击辱骂", "歧视偏见", "广告引流"}
THRESHOLD = 0.7


def parse_llm(raw):
    """大模型输出可能是对象，也可能是带 ```json 代码块的文本。"""
    if isinstance(raw, dict):
        return raw
    s = (raw or "").strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    return json.loads(s)


async def main(args: Args) -> Output:
    p = args.params
    text = p.get("text") or ""
    retrieved_text = json.dumps(p.get("retrieved"), ensure_ascii=False)  # 知识库检索节点的 outputList
    retrieved_ids = set(re.findall(r"【(R\d+)", retrieved_text))  # 只取规则标题里的编号，不取正文里“按 R2”这类引用

    errors = []
    try:
        r = parse_llm(p.get("llm"))
        if not isinstance(r, dict):
            raise ValueError("not an object")
    except Exception:
        r, errors = {}, ["json_parse"]

    label = str(r.get("label") or "").strip()
    rule_id = str(r.get("rule_id") or "").strip()
    if rule_id.lower() in {"null", "none"}:
        rule_id = ""
    evidence = str(r.get("evidence") or "")
    try:
        conf = float(r.get("confidence") or 0)
    except Exception:
        conf, errors = 0.0, errors + ["bad_confidence"]

    if r and label not in LABELS:
        errors.append("bad_label")
    if label and label != "正常" and rule_id not in retrieved_ids:
        errors.append("rule_not_retrieved")  # 引用了没检索到的规则
    if evidence and evidence not in text:
        errors.append("evidence_not_in_text")  # 证据不是原文
    if label and label != "正常" and not evidence:
        errors.append("missing_evidence")

    return {
        "label": label,
        "rule_id": rule_id,
        "evidence": evidence,
        "confidence": conf,
        "need_review": bool(errors) or conf < THRESHOLD,
        "check_errors": ",".join(errors),
    }
