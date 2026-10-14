# Teaching-Agent

维州（VIC）小学补习机构的备课 agent demo。老师选一个 Victorian Curriculum 2.0 数学知识点（Level 3-6）、学生水平和课时，一键生成整节课的材料：

- 复习热身、新知识讲解（含学习目标、易错点、时间分配）
- 例题精讲、三档分层练习（基础 / 中等 / 拔高）、5 分钟小测、课后作业
- 给家长的反馈（语言可按机构配置，例如简体中文）
- 导出带机构 logo 和配色的 Word：教师版（含答案和解析）和学生练习卷（不含答案）

每道数值题都会用 sympy 按题目给出的算式重新计算答案。对不上的题会发回模型修正；修不好的题会标红，提醒老师核对。

## 快速开始

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # 安装 uv
uv sync
uv run uvicorn app.main:app --reload
```

打开 http://localhost:8000 。没有配置 API key 时会自动使用离线 mock 模式，生成的是内置的示例内容（答案都正确），适合演示界面和导出效果。

接入真实模型：复制 `.env.example` 为 `.env`，填入 Azure OpenAI（Australia East 区域）的 endpoint、key 和 deployment。AWS Bedrock（悉尼区域）需要先安装可选依赖：`uv sync --extra bedrock`，再设置 `LLM_PROVIDER=bedrock`。

## 测试和检查

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## 结构

| 路径 | 作用 |
|---|---|
| `app/workflow/dag.py` | 按依赖顺序分段生成，互不依赖的段落并行执行 |
| `app/workflow/prompt.py` | 分 7 层拼提示词：角色、课程结构、大纲、老师补充说明、前文、本段要求、输出格式 |
| `app/workflow/engine.py` | 整节课生成、JSON 校验重试、答案复算后修题、带老师反馈重写单段 |
| `app/llm/` | Azure OpenAI、AWS Bedrock 和离线 mock 三种模型接入 |
| `app/verify/math_check.py` | 只接受纯四则运算表达式，用 sympy 精确计算 |
| `app/render/` | matplotlib 画数轴、柱状图、长方形，以及 Markdown 渲染 |
| `app/export/docx_export.py` | 生成教师版和学生版 Word |
| `data/curriculum/` | 大纲知识点（自写概括，不含 VCAA 原文） |
| `data/templates/` | 教案模板：有哪些段落、每段怎么写、依赖关系 |
| `data/orgs/` | 机构配置：名称、配色、logo、使用的模板、家长反馈语言 |

## 给新机构做定制

定制只改配置，不改代码：

1. 在 `data/orgs/` 新建一个机构 JSON（`id` 只能用小写字母、数字和 `-`）。`logo_path` 填相对 `data/orgs/` 的 PNG 路径；不填就用机构名首字母自动生成 logo。
2. 需要不同的课堂结构时，复制 `data/templates/default-tutoring.json` 改段落，然后在机构配置里把 `template_id` 指向新模板。段落描述里可以用 `${LEVEL}`、`${TOPIC}`、`${STUDENT_LEVEL}`、`${DURATION}`、`${PARENT_LANGUAGE}`、`${ORG_NAME}` 这些变量。

## 注意事项

- `data/curriculum/vic-maths-l3-6.json` 只是演示用的子集。知识点概括是自己写的，content description 代码在给客户使用前需要逐条对照 [VCAA 官网](https://f10.vcaa.vic.edu.au/learning-areas/mathematics) 核实。
- 不存储任何学生个人信息。生成的教案目前只保存在内存里，重启服务后就没了。
- 答案复算只能证明“答案和算式一致”，不能证明题目本身出得合理。所有 AI 生成的内容都必须由老师审核后再使用。

## 下一步

- Postgres（悉尼区域）+ 登录和多租户隔离
- 导入机构旧讲义和题库（RAG），让生成内容沿用机构自己的风格
- VIC 精英中学考试备考题、英语阅读理解、PDF 导出
