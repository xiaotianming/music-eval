# HTTP API 使用

服务默认运行于 `http://127.0.0.1:18763`。启动后查看 `/docs`（交互式 OpenAPI）及 `/openapi.json`（实际请求/响应模式）。该服务面向本机单用户，不能直接暴露公网。

| 操作 | 路由 |
|---|---|
| 健康检查 / 运行设置 | `GET /api/health`、`GET/PUT /api/settings` |
| 导入 / 样本查询 / 修改元数据 | `POST /api/import`、`GET /api/samples`、`PATCH /api/samples/{id}` |
| 音频 / 波形 | `GET /api/samples/{id}/audio`、`GET /api/samples/{id}/waveform` |
| 单曲报告 / 导出 | `GET /api/samples/{id}/report`、`GET /api/samples/{id}/report/{html,json}` |
| 任务创建 / 查询 | `POST /api/jobs`、`GET /api/jobs`、`GET /api/jobs/{id}` |
| 取消 / 重试 | `POST /api/jobs/{id}/cancel`、`POST /api/jobs/{id}/retry` |
| 报告 / 导出 | `GET /api/report`、`GET /api/export/{json,csv,html,bundle}` |
| 清单模板 / 合成示例 | `GET /api/template/{csv,jsonl}`、`POST /api/demo` |
| 盲听 / 投票 / 揭晓 | `POST /api/blind`、`POST /api/blind/{id}/vote`、`POST /api/blind/{id}/reveal` |
| 盲听统计 | `GET /api/votes` |

## 导入

`/api/import` 接收 multipart/form-data：多个 `files`、字符串 JSON `metadata`，以及可选的 CSV/JSONL 文件 `manifest`。清单记录的 `audio` 必须与上传文件名完全一致。后端不会根据清单读取任意本机文件。

```json
{
  "audio": "example.wav",
  "prompt_id": "p001",
  "prompt": "舒缓的钢琴独奏",
  "prompt_en": "A calm solo piano piece",
  "model_id": "model-a",
  "model_version": "v1",
  "audio_type": "instrumental",
  "seed": "42",
  "tags": "piano,calm",
  "role": "generated"
}
```

`audio_type` 为 `song` 或 `instrumental`；`role` 为 `generated` 或 `reference`。必填元数据为 `prompt_id`、`model_id`；提示词可留空，但无法计算 CLAP。

## 评估任务

使用导入响应中的 `sample_ids` 创建任务：

```json
{
  "sample_ids": ["实际样本 ID"],
  "metrics": ["basic", "clap", "songeval"],
  "reference_ids": [],
  "exploratory": false
}
```

可用指标为 `basic`、`clap`、`songeval`、`fad`、`translation`。只传 `translation` 可生成并保存可编辑译文。FAD 参考样本必须显式标为 `reference`。

任务包含 `done`、`total` 和逐项 `items`。逐项状态为 `queued/running/success/failed/skipped/cancelled`；结果中 `stale=true` 表示当前输入已改变，旧分数不参与报告。读取分数前先检查状态；跳过、失败和不适用的结果保留空值。

取消是异步的，需继续查询直到状态结束。重试保留原任务输入快照，只重排失败、跳过、取消项；修改输入后应创建新任务。

## 报告筛选

单曲报告默认显示最新结果；传入 `job_id` 可查看该任务的输入快照和分数，例如 `/api/samples/{id}/report?job_id={task_id}`。HTML/JSON 导出支持同一个参数。歌曲未参与该任务时返回 404。

样本列表和单曲报告的 `overall` 包含综合分 `score`、满分 `max_score=100`、`version`、`coverage`、分项 `components` 及状态 `complete/partial/unavailable/invalid`。暂定分附带缺项原因。任务查询通过 `overall_scores[sample_id]` 返回该任务的综合分；模型报告中的 `metrics.overall_score` 只汇总完整评分。

`/api/report` 及导出接口支持 `ids`（逗号分隔）、`model`、`version`、`audio_type`、`tag` 查询参数。所有指标遵循相同筛选范围；跨类型音乐不计算配对差异。

错误响应通常使用 FastAPI 的 `detail` 字段：422 表示输入不合法，404 表示对象不存在，409 表示当前状态不允许操作。逐项推理失败不会被替换成 HTTP 成功分数，请检查任务中的状态与原因。
