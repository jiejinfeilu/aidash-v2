# AiDash v2 — C 部分：Vercel 后端部署步骤

> 本部分包含：`api/process.js`（AI 秘书）、`api/save.js`（写回 GitHub）、`api/ping.js`（探活）、`api/data.js`（数据代理）、`api/_lib/`（共用封装）、`vercel.json`、`.env.example`。

## 1. 先看懂四个接口

| 接口 | 作用 | 关键入参 | 返回 |
|---|---|---|---|
| `POST /api/process` | AI 秘书分析文字+图片（支持多轮修订） | `pin`、`text`、`imageBase64`、`provider`、`model`、`visionProvider`、`history` | `summary / plan / todos / countdowns / notes / shopping / markdown / provider / model / visionUsed` |
| `POST /api/save` | 合并数据写回 GitHub | `pin`、`data`、`markdown?` | `{ ok, updatedAt }` |
| `GET /api/ping` | 探活 + 返回可用模型列表（手机端下拉框数据源） | 无 | `{ ok, ai, models, visionProviders }` |
| `GET /api/data` | 代理读取 data.json（前端第一数据源，绕过被墙的 raw） | 无 | data.json 内容 |

两个写接口都要求 `pin` 与 Vercel 环境变量 `APP_PIN` 一致，否则返回 401。

## 2. 上传到 GitHub 仓库

1. 打开你的 `aidash` 仓库 → Code → Add file → **Upload files**。
2. 把本机 `aidash` 文件夹里的以下内容拖进去：
   - `api/` 整个文件夹（含 `process.js`、`save.js`、`_lib/`）
   - `vercel.json`
   - `.env.example`（只含变量名，不含真实密钥，可上传）
3. 填写提交说明（如 `add backend`）→ Commit changes。

> 注意：真实密钥**不要**写进任何文件。`.env.example` 只是模板。

## 3. 在 Vercel 部署

1. 打开 https://vercel.com ，用 GitHub 账号登录。
2. Add New → **Project** → Import `aidash` 仓库。
3. 配置：
   - Framework Preset：**Other**
   - Build Command / Output Directory：**留空**（纯 API，无前端构建）
   - Root Directory：**留空**
4. 在 **Environment Variables** 里添加以下变量（带推荐值的按推荐填）：

| 变量 | 填写 |
|---|---|
| AI_PROVIDER | `deepseek` |
| DEEPSEEK_API_KEY | 你的 DeepSeek Key |
| DEEPSEEK_MODEL | `deepseek-v4-flash`（想用 Pro 就填 `deepseek-v4-pro`） |
| ZHIPU_API_KEY | 智谱开放平台 Key（识图用，免费；https://open.bigmodel.cn） |
| ZHIPU_MODEL | `glm-4.6v-flash` |
| VISION_PROVIDER | `auto`（推荐）/ `deepseek` / `zhipu` / `none` |
| ALLOWED_AI_MODELS | `deepseek:deepseek-v4-flash,deepseek:deepseek-v4-pro,zhipu:glm-4.6v-flash,openai:gpt-4o-mini` |
| OPENAI_API_KEY | 留空（用 OpenAI 时再填） |
| OPENAI_MODEL | `gpt-4o-mini` |
| GITHUB_TOKEN | fine-grained Token（见 A 部分第 4.1 节） |
| GITHUB_REPO | `jiejinfeilu/aidash-v2` |
| GITHUB_BRANCH | `main` |
| APP_PIN | 你自己定的 4~6 位口令（手机端要填同一个） |

5. 点 **Deploy**。部署完成后会得到地址，形如：
   `https://aidash-v2-xxxxx.vercel.app`
6. 之后每次仓库更新，Vercel 会自动重新部署。

> 提示：手机端现在可以直接选模型，不用每次改环境变量。环境变量只负责
> “默认值 + 白名单 + Key”，具体说明见下面的“识图引擎对照表”。

### 3.1 识图引擎对照表（手机端选择与 VISION_PROVIDER 一致）

| 选择 | 谁来看图片 | 说明 |
|---|---|---|
| auto（推荐） | 秘书模型能看图就直接看；否则自动用智谱 | DeepSeek V4 Pro 会直接处理图片；Flash 会自动交给智谱 |
| deepseek | DeepSeek（取 DEEPSEEK_MODEL） | 用 Pro 时体验最好；若官方接口报不支持会按兜底列表降级 |
| zhipu | 智谱 GLM-4.6V-Flash | 免费、国内直连，推荐作为兜底 |
| none | 不看图 | 上传图片会收到“已关闭识图”的提示 |

### 3.2 手机端选模型 / 识图引擎（v2 新增）

1. 手机 App → 设置 → AI 模型：
   - 分析模型：DeepSeek V4 Flash / DeepSeek V4 Pro / 智谱 GLM / OpenAI GPT-4o-mini（列表由 `/api/ping` 下发，离线用缓存）；
   - 识图引擎：自动 / DeepSeek / 智谱 / 关闭。
2. 点“保存 AI 设置”，选择会写入 `data.json.settings` 并同步云端。
3. 每次“AI 秘书处理”都会把选择带给后端，后端校验白名单后执行。

### 3.3 切换到 DeepSeek V4 Pro（两种方式）

**方式一：手机端直接切（推荐日常用）**
设置 → AI 模型 → 分析模型选 `DeepSeek · deepseek-v4-pro` → 保存 AI 设置。
同一把 `DEEPSEEK_API_KEY` 共用，不需要动 Vercel。

**方式二：Vercel 管理端改默认值**
Project → Settings → Environment Variables → `DEEPSEEK_MODEL=deepseek-v4-pro` → Save →
Deployments → 最新一次 → Redeploy。

回滚：切回 `deepseek-v4-flash` 重新部署即可。
费用：Pro 按量计费、比 Flash 贵，具体以 DeepSeek 官网价格页为准。

## 4. 验证接口（部署后用电脑测试）

### 4.1 口令错误 → 应返回 401

```bash
curl -X POST https://你的项目.vercel.app/api/process \
  -H "Content-Type: application/json" \
  -d '{"pin":"0000","text":"周六前把房租转给房东"}'
```

### 4.2 正常调用 → 应返回 AI 秘书 JSON

```bash
curl -X POST https://你的项目.vercel.app/api/process \
  -H "Content-Type: application/json" \
  -d '{"pin":"你的口令","text":"周六前把房租转给房东，10月3日参加婚礼"}'
```

预期 `todos` 里出现“把房租转给房东”且 `dueDate` 为最近的周六，`countdowns` 里出现“参加婚礼”。

### 4.3 保存测试（会把仓库里的 data.json 初始化）

```bash
curl -X POST https://你的项目.vercel.app/api/save \
  -H "Content-Type: application/json" \
  -d '{"pin":"你的口令","data":{"todos":[],"countdowns":[],"notes":[],"shopping":[],"layout":{},"settings":{}}}'
```

成功后到仓库里刷新，能看到 `data.json` 和 `data.md` 两个文件被创建。

## 5. 前端对接

1. 手机 App → 设置 → 连接：
   - 后端地址列表（每行一个）：`https://aidash-v2-xxxxx.vercel.app`
   - GitHub 数据地址填：`https://raw.githubusercontent.com/jiejinfeilu/aidash-v2/main`
   - 口令填：与 `APP_PIN` 相同
2. 点“保存连接”（会自动测试所有地址，最快的记为当前生效）。
3. 回“记录”页测试：输入文字或拍照 → AI 秘书处理 → 秘书对话里可继续修改 → 勾选后保存。

## 6. 常见问题

- **401 口令错误**：手机端填的口令与 Vercel 环境变量 `APP_PIN` 不一致。
- **502 AI 调用失败**：`DEEPSEEK_API_KEY` 没填、余额不足，或模型不在白名单（`ALLOWED_AI_MODELS`）。
- **图片上传报 image_url 不支持**：当前秘书模型是纯文本（如 Flash），请把识图引擎设为 `auto` 或 `zhipu`，并确认 `ZHIPU_API_KEY` 已配置。
- **502 GitHub 写入失败**：Token 权限不足（需要 Contents 读写）、Token 过期，或 `GITHUB_REPO` 写错（格式 `用户名/仓库名`）。
- **图片太大**：前端已自动压缩；若仍报错，说明图片质量/尺寸超限，压缩参数在 `web/index.html` 的 `fileToDataURL` 里。
- **想用 OpenAI**：把 `AI_PROVIDER` 改成 `openai`，填上 `OPENAI_API_KEY`；注意国内网络需要代理，费用高于 DeepSeek。
- **本地测试**：可用 `node` 直接跑 `api/process.js` 的 `runProcess`（见代码注释），但正常使用请以 Vercel 线上环境为准。
- **“立即推送到 Kindle”按钮报 403/404**：`/api/refresh` 需要 GITHUB_TOKEN 额外勾选 **Actions → Read and write** 权限（在 GitHub fine-grained token 里把 Actions 权限从 No access 改为 Read and write），并确认仓库里存在 `.github/workflows/daily_push.yml`。
