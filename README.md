# ClawBrain

ClawBrain 是一个万能的 LLM 代理网关，作为 OpenClaw 的“外挂大脑”，提供上下文压缩、多模型路由及 Token 优化功能。

## 项目结构
- `design/`: 存放代码生成的提示词与设计文档
- `src/`: 存放生成的源代码
- `tests/`: 存放生成的测试脚本与数据
- `results/`: 存放自动化测试报告 (nisi)

## 安装指南 (Installation)
本项目使用 Python 3.10+ 并推荐在虚拟环境中运行：

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境 (Linux/macOS)
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

## 运行与开发 (Development)
- 运行测试：`pytest tests/ --json-report --json-report-file=results/test_report.json`
- 生成 nisi 报告：`python3 scripts/nisi_generator.py`
- 启动网关：`uvicorn src.main:app --host 0.0.0.0 --port 11435 --reload`
