# 工作流 `content_review_v1` 节点配置

平台：扣子（coze.cn）开发空间 → 资源库 → 工作流。截图：`screenshots/C1_canvas_content_review_v1.jpg`。

```text
开始 → 知识库检索 → 大模型 → 代码 → 选择器 ─┬（need_review = true）→ 人工复核分支 ─┐
                                            └（否则）──────────────→ 自动标注分支 ─┴→ 变量聚合 → 结束
```

| 节点 | 配置 |
|---|---|
| 开始 | 输入 `text`（String，必填）、`id`（String，选填） |
| 知识库检索 | Query 引用 `开始.text`；知识库 `content_review_rules`（扣子知识库，文本，1 个文档 8 个分段）；搜索策略：混合；最大召回数量 3；最小匹配度 0.01（最低值，保证每次都返回 3 条）；查询改写：关闭；结果重排：开启；仅查看个人文档：开启（默认）。输出 `outputList`（Array<Object>，每项含 `output`、`documentId`） |
| 大模型 | 模型：豆包·2.0·mini·260428；生成多样性：自定义，生成随机性（温度）0，Top P 1，重复语句惩罚 0；深度思考：关闭；最大回复长度 4096。输入变量 `rules` 引用 `知识库检索.outputList`，`text` 引用 `开始.text`。系统提示词和用户提示词见 `prompts/v1.md`。输出格式：文本，输出变量 `output`（String） |
| 代码 | Python。输入 `text` ← `开始.text`，`retrieved` ← `知识库检索.outputList`，`llm` ← `大模型.output`。源码见 `workflow/code_node.py`。输出 `label`（String）、`rule_id`（String）、`evidence`（String）、`confidence`（Number）、`need_review`（Boolean）、`check_errors`（String） |
| 选择器 | 如果 `代码.need_review` = `true` → 人工复核分支；否则 → 自动标注分支 |
| 人工复核分支 | 文本处理节点，字符串拼接，内容为固定文本 `人工复核`，输出 `output` |
| 自动标注分支 | 文本处理节点，字符串拼接，内容为固定文本 `自动标注`，输出 `output` |
| 变量聚合 | 聚合策略：返回每个分组中第一个非空的值。`Group1` = [`人工复核分支.output`, `自动标注分支.output`] |
| 结束 | 返回变量：`label`、`rule_id`、`evidence`、`confidence`（← 代码），`route`（← 变量聚合.Group1），`check_errors`（← 代码），`id`（← 开始.id） |

## 与搭建指南不同的地方

1. **大模型输出格式选“文本”，不选 JSON**：选 JSON 时，模型一旦输出不合法的 JSON，节点会直接报错，整条运行失败，批量评测里这条就没有结果。选文本、由代码节点解析，解析失败会记为 `json_parse` 并转人工复核，失败次数也能计进指标。
2. **模型选豆包·2.0·mini，不用默认的 2.0·pro**：2.0·pro 的参数面板里没有温度，只有“重复语句惩罚”。2.0·mini 可以把生成随机性设为 0，而且是面向成本敏感场景的型号。
3. **代码节点比指南原版多做了两件事**：
   - 解析前先去掉 ```json 代码块标记。
   - 已检索规则编号只从规则标题“【R…”里取。如果从整段检索文本里匹配 `R\d+`，会把正文里“按 R2”这类交叉引用也算进来，`rule_not_retrieved` 就查不出问题了。
4. **结束节点多输出一个 `id`**：方便评测时对齐样本。
