# 评论内容审核预标注 Workflow（进行中）

在扣子（coze.cn）上用低代码工作流搭的评论审核预标注流程：先检索规则，再由大模型按规则给出类别、规则编号、原文证据和置信度；代码节点核对规则编号和证据是否属实；低置信度或核对失败的转人工复核。之后用 120 条自建标注样本评测 Prompt v1 和 v2。

项目按阶段推进，每完成一个阶段提交一次。完整说明、流程图和评测结果会在全部阶段完成后补全。

## 当前进度

- [x] 阶段 A：规则知识库（`rules/`）
- [x] 阶段 B：评测集 120 条，开发 40 / 测试 80，标签已复核，测试集已冻结（`data/`、`eval/`）
- [ ] 阶段 C：工作流 `content_review_v1`
- [ ] 阶段 D：评测工作流与开发集运行
- [ ] 阶段 E：错例分析与 Prompt v2
- [ ] 阶段 F：测试集运行与指标
- [ ] 阶段 H：完整 README

运行过程和与原计划不一致的地方都记在 [`runs.md`](runs.md)。

## 数据来源与许可

- 攻击辱骂、歧视偏见和部分正常样本取自 COLD 数据集（Deng et al., *COLD: A Benchmark for Chinese Offensive Language Detection*, EMNLP 2022，仓库 [thu-coai/COLDataset](https://github.com/thu-coai/COLDataset)）。COLD 以 Apache License 2.0 发布，许可全文见 [`data/COLD_LICENSE.txt`](data/COLD_LICENSE.txt)。本项目只从 COLD 测试集中挑选了部分样本，并按本项目的 4 个类别重新映射了标签，没有改动原文。
- 广告引流样本和少量正常商品讨论样本是自写的，其中的联系方式都是虚构或打码的。
- 规则是参考公开社区规范、用自己的话写的简化版，不代表任何平台的真实审核标准。
- 评测集含有冒犯性文本，仅用于研究和评测。
