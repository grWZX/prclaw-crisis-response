# 危机传播管理工具包 —— crisis-response-toolkit

> **描述**：基于"事实-价值"模型和危机管理五路径的危机传播管理工具包。当组织面临突发事件、舆情危机或需要准备新闻发布会时使用，适用于企业、政府机构及公共事业部门。兼容 PRClaw Agent 架构。
>
> **版本**：v1.0 | **最后更新**：2026年6月24日 | **主入口**：`skills/crisis-response.md`

本目录为完整资源包，主程序通过 `skills/crisis-response.md` 加载精简指令；详细理论、案例与脚本见下方子目录。

## 目录结构

```
crisis-response-toolkit/
├── SKILL.md                          # 本文件（资源包说明）
├── references/
│   ├── theory-framework.md           # 完整理论框架
│   ├── case-library.md               # 案例库（6个案例）
│   └── spokesperson-checklist.md     # 发言人操作清单与禁忌速查
└── scripts/
    └── score_response.py             # 声明质量评分脚本
```

## 快速使用

- **Agent 激活**：在 `config/skills.yaml` 中注册 `skills/crisis-response.md` 即可，无需修改主程序代码。
- **声明评分**：`python skills/crisis-response-toolkit/scripts/score_response.py`
- **深度学习**：按需阅读 `references/` 下各文档。

## 参考资源索引

| 文件 | 内容 |
|---|---|
| `references/theory-framework.md` | 危机本质论、事实-价值模型、五路径、三原则、修辞三要素 |
| `references/case-library.md` | 企业/政府/数据安全三类共6个案例 |
| `references/spokesperson-checklist.md` | 发布前检查、风险控制、禁忌速查、一票否决项 |
| `scripts/score_response.py` | 事实层/价值层/路径适配三维评分 + 一票否决 |

## 与 copy-news-release 的对应关系

| copy-news-release | crisis-response-toolkit |
|---|---|
| `references/rhetoric-framework.md` | `references/theory-framework.md` |
| `references/statement-case-library.md` | `references/case-library.md` |
| `references/spokesperson-checklist.md` | `references/spokesperson-checklist.md` |
| `scripts/score_statement.py` | `scripts/score_response.py` |
