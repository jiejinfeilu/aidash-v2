# AiDash v2 — C 部分：Vercel 后端部署步骤

> 本部分包含：`api/process.js`（AI 秘书）、`api/save.js`（写回 GitHub）、`api/ping.js`（探活）、`api/data.js`（数据代理）、`api/_lib/`（共用封装）、`vercel.json`、`.env.example`。

## 1. 先看懂四个接口

| 接口 | 作用 | 关键入参 | 返回 |
|---|---|---|---|
| `POST /api/process` | AI 秘书分析文字+图片（支持多轮修订与“人设压缩”任务） | `pin`、`text`、`imageBase64`、`provider`、`model`、`visionProvider`、`history`、`userName`、`userNameVariants`、`aiTone`、`aiGreeting`、`personaMd`、`personaName`、`personaTask`、`customProviders` | `summary / plan / todos / countdowns / notes / shopping / markdown / provider / model / visionUsed / personaUpdate`；`personaTask=compress` 时返回 `{ ok, personaMd, summary }` |
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
| ZHIPU_VISION_MODELS | `glm-4.6v-flash,glm-4v-flash`（识图兜底链，可只留一个） |
| ZHIPU_MAX_TOKENS | `1024`（免费模型单次输出上限；付费模型可调大） |
| VISION_PROVIDER | `auto`（推荐）/ `zhipu` / `openai` / `none` |
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
| auto（推荐） | 秘书模型能看图就直接看；否则**优先用你添加的“支持识图”自定义模型**，全部失败才用智谱 | 自定义模型优先、智谱兜底，限流自动重试 |
| zhipu | 智谱 GLM（`glm-4.6v-flash` + `glm-4v-flash` 并行） | 免费、国内直连，高峰限流会自动重试换模型 |
| deepseek | DeepSeek（预留） | 官方 API 目前不支持图片；选择后会先试 DeepSeek，失败自动落到智谱。以后官方支持识图，代码里 `DEEPSEEK_VISION_SUPPORTED` 改为 `true` 即可 |
| openai | OpenAI 视觉模型 | 需要可直连 OpenAI 的网络，费用较高 |
| custom:xxx | 你添加的自定义视觉模型 | 手机端添加时勾选“支持识图”即可出现在这里 |
| none | 不看图 | 上传图片会收到“已关闭识图”的提示 |

> 实测结论：DeepSeek 官方 API（含 deepseek-v4-pro-0813）不接受图片输入，
> 会报 `unknown variant 'image_url'`；已保留为“预留”选项，失败自动落到智谱。

### 3.2 手机端选模型 / 识图引擎（v2 新增）

1. 手机 App → 设置 → AI 模型：
   - 分析模型：DeepSeek V4 Flash / DeepSeek V4 Pro / 智谱 GLM / OpenAI GPT-4o-mini（列表由 `/api/ping` 下发，离线用缓存）；
   - 识图引擎：自动（推荐）/ 智谱 / DeepSeek（预留）/ OpenAI / 自定义视觉模型 / 关闭。
2. 点“保存 AI 设置”，选择会写入 `data.json.settings` 并同步云端。
3. 每次“AI 秘书处理”都会把选择带给后端，后端校验白名单后执行。
4. 称呼与语气（纯文字/带图都生效）：
   - “AI 对我的称呼”：主称呼，如“主人”；
   - “称呼变体”：逗号分隔多个，如“主人，老板，小张”，不同回复间轮换；
   - “语气风格”：默认 / 活泼 / 严肃；
   - “固定开场白”：如“好的，{称呼}！”——`{称呼}` 会自动替换成你的称呼，每次回复总结开头先用它。
5. “AI 人设（人格档案 MD）”：导入/编辑一份 Markdown 人格档案（性格、脾气、说话风格、思考方式、行为准则，最多 12000 字），
   每次回复严格遵循；对话中 AI 发现值得记录的新偏好时，会返回 `personaUpdate` 建议，
   手机端点“采纳并记录”即追加写入档案并同步云端（带日期“更新记录”小节），让 AI 持续“成长”。
   - **多套人设**：可新建/切换/重命名/删除多套人格档案，各自独立成长，切换当前人设即生效；
   - **档案过长怎么办**：提示词会优先执行档案开头的“核心身份/性格/底线/风格”，成长记录只作背景；
     AI 的更新建议已要求“精简修改（≤200 字）”而不是无限追加；超过 6000 字时手机端会提醒，
     可点“整理压缩”让 AI 生成 ≤4000 字的精简核心版，预览后采用（`personaTask=compress`）。

### 3.3 切换到 DeepSeek V4 Pro（两种方式）

**方式一：手机端直接切（推荐日常用）**
设置 → AI 模型 → 分析模型选 `DeepSeek · deepseek-v4-pro` → 保存 AI 设置。
同一把 `DEEPSEEK_API_KEY` 共用，不需要动 Vercel。
注意：Pro 也只是“分析模型”，识图仍由智谱完成（DeepSeek 官方 API 不支持图片）。

**方式二：Vercel 管理端改默认值**
Project → Settings → Environment Variables → `DEEPSEEK_MODEL=deepseek-v4-pro` → Save →
Deployments → 最新一次 → Redeploy。

回滚：切回 `deepseek-v4-flash` 重新部署即可。
费用：Pro 按量计费、比 Flash 贵，具体以 DeepSeek 官网价格页为准。

### 3.4 手机端添加自定义模型 / API（本地保存）

1. 设置 → AI 模型 → 往下找到“自定义模型（本地保存）”。
2. 填写：名称（如“我的Kimi”）、模型名（如 `moonshot-v1-8k`）、
   接口地址（OpenAI 兼容，必须以 `https://` 开头，如 `https://api.deepseek.com`）、
   API Key；若该模型支持看图，勾选“支持识图”。
3. 点“添加自定义模型” → 会出现在“分析模型”和“识图引擎”下拉框里。
4. 安全说明：API Key **只保存在手机本机**（localStorage），请求时经 HTTPS 发给
   你自己的 Vercel 后端，**不会写入 GitHub**；删除自定义模型即删除 Key。
5. 接口地址需为 OpenAI 兼容格式；后端会拒绝 http、内网地址，防止误用。

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
- **图片上传报 image_url 不支持**：这是 DeepSeek 官方 API 的限制（实测），请把识图引擎设为 `auto` 或 `zhipu`，并确认 `ZHIPU_API_KEY` 已配置。
- **识图提示“访问量过大”**：智谱免费模型高峰限流，代码会自动并行换 `glm-4v-flash` 并重试；仍失败就稍等 1~2 分钟再试。
- **识图报 max_tokens 参数非法**：智谱免费视觉模型输出上限是 1024 tokens，代码已自动适配；若识别长文被截断，可换付费的 `glm-4.6v-flashx` 并把 `ZHIPU_MAX_TOKENS` 调大。
- **502 GitHub 写入失败**：Token 权限不足（需要 Contents 读写）、Token 过期，或 `GITHUB_REPO` 写错（格式 `用户名/仓库名`）。
- **图片太大**：前端已自动压缩；若仍报错，说明图片质量/尺寸超限，压缩参数在 `web/index.html` 的 `fileToDataURL` 里。
- **想用 OpenAI**：把 `AI_PROVIDER` 改成 `openai`，填上 `OPENAI_API_KEY`；注意国内网络需要代理，费用高于 DeepSeek。
- **本地测试**：可用 `node` 直接跑 `api/process.js` 的 `runProcess`（见代码注释），但正常使用请以 Vercel 线上环境为准。
- **“立即推送到 Kindle”按钮报 403/404**：`/api/refresh` 需要 GITHUB_TOKEN 额外勾选 **Actions → Read and write** 权限（在 GitHub fine-grained token 里把 Actions 权限从 No access 改为 Read and write），并确认仓库里存在 `.github/workflows/daily_push.yml`。
