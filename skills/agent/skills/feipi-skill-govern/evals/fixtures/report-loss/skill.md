---
name: feipi-issues-build-report
description: 根据已有问题清单生成本地报告和用户通知文本；不做外部发送。
---

# 问题报告

用户提供问题 JSON，按照 [报告规约](references/report-policy.md) 生成报告和通知。

```bash
python3 scripts/report.py INPUT OUTPUT_DIR
```

交付 OUTPUT_DIR 中的 report.md 和 notification.txt。
