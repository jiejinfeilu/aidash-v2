/* ================================================================
   AI 调用封装（v2 修复版）
   - 分析模型（秘书）：DeepSeek（默认）/ OpenAI / 智谱 GLM
   - 识图引擎（眼睛）：zhipu / deepseek / openai / auto / none
   - 三家均为 OpenAI 兼容 Chat Completions 格式
   - 所有 Key 只来自环境变量，绝不写进前端
   ================================================================ */
var https = require("https");

/* 三家服务商配置 */
var PROVIDERS = {
  deepseek: {
    base: "https://api.deepseek.com",
    chatPath: "/chat/completions",
    model: "deepseek-v4-flash",   /* 默认模型；可用 DEEPSEEK_MODEL 覆盖 */
    envKey: "DEEPSEEK_API_KEY",
    envModel: "DEEPSEEK_MODEL",
    label: "DeepSeek"
  },
  openai: {
    base: "https://api.openai.com",
    chatPath: "/v1/chat/completions",
    model: "gpt-4o-mini",
    envKey: "OPENAI_API_KEY",
    envModel: "OPENAI_MODEL",
    label: "OpenAI"
  },
  zhipu: {
    base: "https://open.bigmodel.cn/api/paas/v4",
    chatPath: "/chat/completions",
    model: "glm-4.6v-flash",      /* 智谱免费视觉模型 */
    envKey: "ZHIPU_API_KEY",
    envModel: "ZHIPU_MODEL",
    label: "智谱 GLM"
  }
};

/* 默认白名单：手机端只能在这些模型里选（防止乱填烧钱） */
var DEFAULT_ALLOWED = [
  "deepseek:deepseek-v4-flash",
  "deepseek:deepseek-v4-pro",
  "zhipu:glm-4.6v-flash",
  "openai:gpt-4o-mini"
];

/* DeepSeek 官方 API 目前（2026-08-15 实测）不接受图片输入。
   以后官方支持识图时，把这里改成 true 即可，前端不用改。 */
var DEEPSEEK_VISION_SUPPORTED = false;

function normalizeKey(s) { return String(s || "").trim().toLowerCase(); }

/* 判断某 provider + model 是否支持图片输入 */
function hasVision(provider, model) {
  var p = normalizeKey(provider);
  var m = String(model || "").toLowerCase();
  if (p === "zhipu") { return /glm-4(\.\d+)?v/.test(m); }
  if (p === "deepseek") {
    return DEEPSEEK_VISION_SUPPORTED;
  }
  if (p === "openai") { return /gpt-4o|gpt-4\.1|gpt-5/.test(m); }
  return false;
}

/* 手机端“自定义模型”校验：
   - 必须 https、不能是内网地址（防 SSRF）
   - id/baseUrl/model/apiKey 必填，长度限制
   - chatPath 只允许普通路径，最终统一以 /chat/completions 结尾 */
function sanitizeCustomProviders(arr) {
  if (!Array.isArray(arr)) { return []; }
  var out = [];
  arr.slice(0, 5).forEach(function (c) {
    if (!c || typeof c !== "object") { return; }
    var id = String(c.id || "").trim().slice(0, 40);
    var name = String(c.name || "").trim().slice(0, 50);
    var baseUrl = String(c.baseUrl || "").trim().replace(/\/+$/, "").slice(0, 300);
    var model = String(c.model || "").trim().slice(0, 100);
    var apiKey = String(c.apiKey || "").trim().slice(0, 600);
    var chatPath = String(c.chatPath || "/chat/completions").trim().slice(0, 80);
    if (!id || !baseUrl || !model || !apiKey) { return; }
    if (!/^https:\/\//i.test(baseUrl)) { return; }
    try {
      var u = new URL(baseUrl);
      var host = u.hostname.toLowerCase();
      if (host === "localhost" || host === "127.0.0.1" || host === "::1" ||
          /^(10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.)/.test(host) ||
          host.endsWith(".local")) { return; }
      if (u.username || u.password) { return; }
    } catch (e) { return; }
    if (chatPath.indexOf("..") >= 0 || !/^\/[a-zA-Z0-9._/-]*$/.test(chatPath)) { return; }
    if (!chatPath.endsWith("/chat/completions")) {
      chatPath = chatPath.replace(/\/+$/, "") + "/chat/completions";
    }
    out.push({
      id: id, name: name || id, baseUrl: baseUrl, model: model,
      apiKey: apiKey, chatPath: chatPath, vision: !!c.vision
    });
  });
  return out;
}

/* 拼出 OpenAI 兼容的完整接口地址 */
function chatEndpoint(baseUrl, chatPath) {
  var b = String(baseUrl || "").replace(/\/+$/, "");
  var p = String(chatPath || "/chat/completions");
  if (!/^\//.test(p)) { p = "/" + p; }
  if (!p.endsWith("/chat/completions")) { p = p.replace(/\/+$/, "") + "/chat/completions"; }
  return b + p;
}

/* 智谱识图模型列表：默认两个免费模型都试（并行），可用
   ZHIPU_VISION_MODELS 或 ZHIPU_MODEL 覆盖，逗号分隔多个。 */
var DEFAULT_ZHIPU_VISION = ["glm-4.6v-flash", "glm-4v-flash"];
function getVisionModels(env) {
  env = env || process.env;
  var arr = [];
  var raw = String(env.ZHIPU_VISION_MODELS || env.ZHIPU_MODEL || "").trim();
  if (raw) {
    raw.split(",").forEach(function (s) {
      s = s.trim();
      if (s && arr.indexOf(s) < 0) { arr.push(s); }
    });
  }
  DEFAULT_ZHIPU_VISION.forEach(function (m) {
    if (arr.indexOf(m) < 0) { arr.push(m); }
  });
  return arr.slice(0, 3);
}

/* 读取白名单：ALLOWED_AI_MODELS（换行/逗号/分号分隔 "provider:model"） */
function listAllowedModels(env) {
  env = env || process.env;
  var raw = String(env.ALLOWED_AI_MODELS || "").trim();
  var pairs = raw ? raw.split(/[\n,;]+/) : DEFAULT_ALLOWED.slice();
  var out = [];
  pairs.forEach(function (s) {
    s = String(s).trim();
    if (!s) { return; }
    var i = s.indexOf(":");
    if (i <= 0) { return; }
    var provider = s.slice(0, i).trim().toLowerCase();
    var model = s.slice(i + 1).trim();
    var meta = PROVIDERS[provider];
    if (!meta || !model) { return; }
    out.push({
      provider: provider,
      model: model,
      label: meta.label + " · " + model,
      vision: hasVision(provider, model)
    });
  });
  return out;
}

/* 解析本次要用的秘书模型；客户端显式指定时必须命中白名单 */
function resolveSecretary(env, body) {
  env = env || process.env;
  body = body || {};
  var customs = sanitizeCustomProviders(body.customProviders);
  var providerName = normalizeKey(body.provider || env.AI_PROVIDER || "deepseek");
  if (providerName === "custom") {
    var cid = String(body.model || "").trim();
    var c = null;
    for (var i = 0; i < customs.length; i++) {
      if (customs[i].id === cid) { c = customs[i]; break; }
    }
    if (!c) { throw new Error("找不到该自定义模型（请先在手机“设置 → AI 模型”里添加并保存）"); }
    return {
      provider: "custom",
      model: c.model,
      customId: c.id,
      meta: { envKey: null, label: c.name || c.id },
      baseUrl: c.baseUrl,
      chatPath: c.chatPath,
      apiKey: c.apiKey,
      vision: !!c.vision
    };
  }
  var meta = PROVIDERS[providerName];
  if (!meta) { throw new Error("AI_PROVIDER 仅支持 deepseek / openai / zhipu"); }
  var model = String(body.model || env[meta.envModel] || meta.model).trim();
  if (!model) { throw new Error("模型名为空"); }
  var explicit = String(body.provider || "").trim() || String(body.model || "").trim();
  if (explicit) {
    var hit = listAllowedModels(env).some(function (m) {
      return m.provider === providerName && m.model === model;
    });
    if (!hit) {
      throw new Error("该模型不在白名单（ALLOWED_AI_MODELS），请先在 Vercel 环境变量里配置");
    }
  }
  return { provider: providerName, model: model, meta: meta, vision: hasVision(providerName, model) };
}

/* 解析识图引擎：
   none                      -> 关闭识图
   auto                      -> 秘书模型能看图就单次调用；否则用智谱兜底
   deepseek / zhipu / openai -> 强制指定；可逗号写多个按顺序兜底 */
function visionChain(env, secretary, visionProviderRaw, customProviders) {
  env = env || process.env;
  var customs = sanitizeCustomProviders(customProviders);
  var raw = normalizeKey(visionProviderRaw || env.VISION_PROVIDER || "auto");
  if (!raw || raw === "none") { return { mode: "none", chain: [] }; }
  if (raw === "auto") {
    if (secretary.vision) { return { mode: "single", chain: [] }; }
    var autoChain = [];
    /* 自定义视觉模型优先（prio=0），智谱兜底（prio=1） */
    customs.forEach(function (c) {
      if (c.vision) {
        autoChain.push({ provider: "custom", id: c.id, model: c.model, apiKey: c.apiKey, baseUrl: c.baseUrl, chatPath: c.chatPath, prio: 0 });
      }
    });
    if (env.ZHIPU_API_KEY) {
      getVisionModels(env).forEach(function (m) { autoChain.push({ provider: "zhipu", model: m, prio: 1 }); });
    }
    if (!autoChain.length) {
      throw new Error("未配置任何识图引擎（需要 ZHIPU_API_KEY 或在手机添加支持识图的自定义模型）");
    }
    return { mode: "two", chain: autoChain };
  }
  var chain = [];
  raw.split(",").forEach(function (s) {
    s = s.trim();
    if (!s) { return; }
    if (s === "deepseek") {
      /* DeepSeek 预留：官方支持识图后优先用它；现在失败会自动落到智谱 */
      chain.push({ provider: "deepseek", model: String(env[PROVIDERS.deepseek.envModel] || PROVIDERS.deepseek.model).trim(), prio: 0 });
      if (env.ZHIPU_API_KEY) {
        getVisionModels(env).forEach(function (m) { chain.push({ provider: "zhipu", model: m, prio: 1 }); });
      }
      return;
    }
    if (s.indexOf("custom:") === 0) {
      var cid = s.slice(7);
      for (var i = 0; i < customs.length; i++) {
        if (customs[i].id === cid && customs[i].vision) {
          chain.push({ provider: "custom", id: cid, model: customs[i].model, apiKey: customs[i].apiKey, baseUrl: customs[i].baseUrl, chatPath: customs[i].chatPath });
          break;
        }
      }
      return;
    }
    var meta = PROVIDERS[s];
    if (!meta) { return; }
    if (s === "zhipu") {
      getVisionModels(env).forEach(function (m) { chain.push({ provider: "zhipu", model: m }); });
    } else {
      chain.push({ provider: s, model: String(env[meta.envModel] || meta.model).trim() });
    }
  });
  /* 去重（deepseek 分支已自动带上智谱兜底，避免重复调用） */
  var seen = {};
  chain = chain.filter(function (c) {
    var k = c.provider + ":" + c.model + ":" + (c.id || "");
    if (seen[k]) { return false; }
    seen[k] = true;
    return true;
  });
  if (!chain.length) {
    throw new Error("识图引擎选择无效，或该自定义模型未勾选“支持识图”");
  }
  return { mode: "two", chain: chain };
}

function sleep(ms) {
  return new Promise(function (resolve) { setTimeout(resolve, ms); });
}

/* 发起 HTTPS POST，返回解析后的 JSON；非 2xx 时抛错 */
function httpsJsonPost(urlStr, headers, body, timeoutMs) {
  return new Promise(function (resolve, reject) {
    var url = new URL(urlStr);
    var req = https.request(url, {
      method: "POST",
      headers: Object.assign({ "Content-Type": "application/json" }, headers)
    }, function (res) {
      var data = "";
      res.setEncoding("utf8");
      res.on("data", function (c) {
        data += c;
        if (data.length > 5e6) { req.destroy(new Error("响应过大")); }
      });
      res.on("end", function () {
        var json = null;
        try { json = JSON.parse(data); } catch (e) {}
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(json || {});
        } else {
          var msg = (json && json.error && (json.error.message || JSON.stringify(json.error))) || ("HTTP " + res.statusCode);
          reject(new Error(msg));
        }
      });
    });
    req.setTimeout(timeoutMs || 60000, function () { req.destroy(new Error("AI 请求超时")); });
    req.on("error", reject);
    req.write(JSON.stringify(body));
    req.end();
  });
}

/* 真正发送一次对话请求 */
async function sendChat(meta, options, payload) {
  var res = await httpsJsonPost(
    chatEndpoint(options.baseUrl || meta.base, options.chatPath || meta.chatPath),
    { "Authorization": "Bearer " + options.apiKey },
    payload,
    options.timeoutMs
  );
  var choice = res.choices && res.choices[0];
  var content = choice && choice.message && choice.message.content;
  if (!content) {
    throw new Error("AI 返回为空：" + (res.error ? JSON.stringify(res.error) : "未知错误"));
  }
  return content;
}

/* 调用 Chat Completions；部分视觉模型不支持 response_format 时自动去掉重试 */
async function chatCompletion(options) {
  var p = PROVIDERS[options.provider];
  if (!p && !options.baseUrl) { throw new Error("未知 AI_PROVIDER：" + options.provider); }
  if (options.provider === "custom" && !options.baseUrl) { throw new Error("自定义模型缺少接口地址"); }
  var payload = {
    model: options.model || p.model,
    messages: options.messages,
    temperature: 0.3,
    max_tokens: options.maxTokens || 4096
  };
  if (options.jsonMode !== false) { payload.response_format = { type: "json_object" }; }
  try {
    return await sendChat(p, options, payload);
  } catch (e) {
    if (options.jsonMode !== false && /response_format|json_object/i.test(String(e.message))) {
      delete payload.response_format;
      return await sendChat(p, options, payload);
    }
    throw e;
  }
}

/* 构建“秘书”角色的消息：系统提示 + 对话历史 + 当前输入（可带图片） */
function buildSecretaryMessages(input) {
  var today = input.today || "";
  var system =
    "你是我的资深私人助理（秘书）。请把用户随手记录的文字和图片理解清楚，像贴心秘书一样给出安排，而不是机械分类。\n" +
    "\n" +
    "工作要求：\n" +
    "1. 从信息中提炼“可执行事项”放入 todos，判断优先级（高/中/低），并给出建议完成日期 dueDate（格式 YYYY-MM-DD；仅当信息中出现日期、截止日或相对时间词时才推算填写，否则填空字符串），每条都要有 reason（一句话说明为什么这样安排）。\n" +
    "2. 有明确日期的事件（如“10月3日参加婚礼”）要同时放入 countdowns（name 用事件名，date 用 YYYY-MM-DD）和 todos。\n" +
    "3. 纯想法、灵感、知识、备忘放入 notes，tags 给 1~3 个简短标签；买东西的需求放入 shopping。\n" +
    "4. plan 给出“今天应该优先做的事”，按优先级和截止日期排序，每项一句话。\n" +
    "5. 图片中的文字必须全部读取并纳入分析；不要编造图片里没有的信息；如果图片和文字都有，以两者结合为准。\n" +
    "6. 如果用户给出了修改指令（如“房租改成下周一”），请基于之前的安排整体更新，保留仍然有效的事项，输出完整的 JSON，不要只输出变化部分。\n" +
    "\n" +
    "输出要求：\n" +
    "- 只输出一个合法 JSON 对象，不要输出任何其他文字。\n" +
    "- JSON 结构固定为：\n" +
    "{\n" +
    "  \"summary\": \"一句话总结这条信息\",\n" +
    "  \"plan\": [\"今天优先：...\"],\n" +
    "  \"todos\": [{\"text\": \"...\", \"priority\": \"高|中|低\", \"dueDate\": \"YYYY-MM-DD 或空字符串\", \"reason\": \"...\"}],\n" +
    "  \"countdowns\": [{\"name\": \"...\", \"date\": \"YYYY-MM-DD\"}],\n" +
    "  \"notes\": [{\"text\": \"...\", \"tags\": [\"标签1\", \"标签2\"]}],\n" +
    "  \"shopping\": [{\"text\": \"...\"}],\n" +
    "  \"markdown\": \"把这条信息整理成适合存档的中文 Markdown（包含待办清单、倒计时、笔记、购物清单）\"\n" +
    "}\n" +
    "\n" +
    "今天是：" + today;

  /* 称呼 + 称呼变体（纯文字/带图请求都生效） */
  var names = [];
  if (input.userName) { names.push(String(input.userName).trim()); }
  (Array.isArray(input.userNameVariants) ? input.userNameVariants : []).forEach(function (n) {
    n = String(n || "").trim();
    if (n && names.indexOf(n) < 0 && names.length < 10) { names.push(n); }
  });
  var primaryName = names.length ? names[0] : "";
  if (primaryName) {
    system += "\n\n用户希望被你称呼为「" + primaryName + "」";
    if (names.length > 1) {
      system += "，称呼变体还有：" + names.slice(1).map(function (n) { return "「" + n + "」"; }).join("、") +
        "（不同回复之间轮换使用，不要每次都一样）";
    }
    system += "。礼貌要求：每次回复的总结开头必须自然称呼一次（例如“好的，主人”），这是基本礼貌，不要省略。" +
      "称呼规则：同一句话内不要重复；新句子或新话题时如果自然，可以再次称呼，但不要每句都叫，保持聊天感。";
  }

  /* 语气风格 */
  var tone = input.aiTone || "默认";
  if (tone === "活泼") {
    system += "\n语气风格：活泼亲切，像朋友一样，可以适当用感叹号和“~”收尾，不要使用 emoji 符号。";
  } else if (tone === "严肃") {
    system += "\n语气风格：简洁、正式、专业，不用感叹号、表情和网络用语。";
  } else {
    system += "\n语气风格：自然友好，像日常聊天，口语化但不啰嗦；避免“已为您安排如下”这类公文式僵硬表达。";
  }

  /* 固定开场白（支持 {称呼} 占位符） */
  var greeting = String(input.aiGreeting || "").trim();
  if (greeting) {
    greeting = greeting.replace(/\{称呼\}/g, primaryName || "你");
    system += "\n固定开场白：每次回复的总结（summary）开头请先使用「" + greeting + "」自然开场（可以补标点衔接，不要加其它多余前缀）。";
  }

  /* AI 人设档案（Markdown）：用户提供并持续更新的“人格发展文件” */
  var personaMd = String(input.personaMd || "").trim();
  if (personaMd) {
    if (input.personaName) {
      system += "\n\n你现在扮演的人设名称：「" + String(input.personaName).trim().slice(0, 30) + "」。";
    }
    system +=
      "\n\n【AI 人设与行为准则（Markdown 档案，必须严格遵守）】\n" + personaMd +
      "\n\n这份档案是你的“人格发展档案”：你的性格、脾气、基本信息、说话风格、思考方式、习惯与约束都以它为准；" +
      "当档案内容与本提示其它要求冲突时，以档案为准（涉及安全与明显事实错误时除外）。" +
      "你应当在回复中自然体现这份人格，而不是机械复述档案内容。" +
      "如果档案较长：档案开头的「核心身份 / 性格 / 脾气与底线 / 说话风格 / 思考方式 / 行为准则」优先执行，" +
      "后面的成长记录作为背景参考即可，不要让历史细节盖过核心人格。";
  }

  /* 人格成长：把值得记录的新偏好通过 personaUpdate 回报，由用户确认后写回档案 */
  system +=
    "\n\n每次回复：如果这次对话里你了解到值得记录的新偏好或变化" +
    "（例如用户纠正了称呼、语气、作息、工作方式，或你自己形成了更稳定的风格），" +
    "请在输出 JSON 的可选字段 personaUpdate 中给出简短 Markdown 增量（如 \"- 新增：…\" 或 \"- 修改：…\"）；" +
    "更新要精简（一般不超过 200 字）；如果档案里已有类似内容，优先输出 \"- 修改：…\" 而不是重复添加；" +
    "仅在确有值得记录的变化时输出，没有变化就不要输出该字段。";

  /* 网址纪律：不编造、不附带链接（模型偶发幻觉输出 raw.githubusercontent 之类地址） */
  system +=
    "\n\n网址纪律：除用户原文明确给出的网址外，不要在总结、今日安排、待办、笔记、购物清单和 Markdown 里编造或附带任何网址/链接；" +
    "尤其不要输出 raw.githubusercontent.com、jsdelivr、vercel.app 之类的地址。";

  var userParts = [];
  if (input.imageText) { userParts.push("[图片识别结果]\n" + input.imageText); }
  if (input.text) { userParts.push(input.text); }
  if (!userParts.length) { userParts.push("（请结合对话历史整理安排）"); }

  var messages = [{ role: "system", content: system }];

  /* 多轮修订：携带最近对话（纯文本），图片只在首轮 */
  var history = Array.isArray(input.history) ? input.history.slice(-8) : [];
  history.forEach(function (h) {
    if (!h || typeof h !== "object") { return; }
    var role = h.role === "user" ? "user" : "assistant";
    var c = h.content;
    if (typeof c === "string" && c.trim()) { messages.push({ role: role, content: c.slice(0, 4000) }); }
  });

  var userText = userParts.join("\n\n");
  /* 在用户消息里也提醒一次称呼，提高模型遵守率（纯文字/带图都生效） */
  if (primaryName) {
    userText = userText + "\n（本条请用「" + primaryName + "」称呼我）";
  }
  if (input.singleImage) {
    /* 单次调用：秘书模型本身能看图，图片直接随本轮请求传入 */
    messages.push({
      role: "user",
      content: [
        { type: "text", text: userText },
        { type: "image_url", image_url: { url: input.singleImage } }
      ]
    });
  } else {
    messages.push({ role: "user", content: userText });
  }
  return messages;
}

/* 人设档案整理器：把长大的档案压缩成核心版（供“整理压缩”功能使用） */
function buildCompressMessages(personaMd) {
  return [
    {
      role: "system",
      content: "你是 AI 人设档案整理器。请把用户的人格档案压缩整理成一份不超过 4000 字、结构清晰的 Markdown，保留：核心身份、性格、脾气与底线、说话风格、思考方式、行为准则与约束、成长方向。删除重复和过时细节，把重要约束写得更明确。只输出 JSON：{\"personaMd\":\"压缩后的Markdown\",\"summary\":\"一句话说明这次整理改了什么\"}"
    },
    { role: "user", content: personaMd }
  ];
}

/* 识图专用：让视觉模型完整提取图片文字 */
async function readImageText(provider, model, imageBase64, apiKey, timeoutMs, opts) {
  opts = opts || {};
  var messages = [{
    role: "user",
    content: [
      {
        type: "text",
        text: "你是一位严谨的 OCR 助手。请完整提取图片中的全部文字（便签、截图、票据、手写、印刷均可），不要遗漏日期、数字、金额；提取完后用一句话概括图片内容。只输出：图片文字内容 + 一句概括。"
      },
      { type: "image_url", image_url: { url: imageBase64 } }
    ]
  }];
  var content = await chatCompletion({
    provider: provider,
    apiKey: apiKey,
    model: model,
    messages: messages,
    timeoutMs: timeoutMs || 55000,
    jsonMode: false,
    /* 智谱免费视觉模型输出上限 1024 tokens，OCR 结果足够用 */
    maxTokens: 1024,
    baseUrl: opts.baseUrl,
    chatPath: opts.chatPath
  });
  return String(content || "").trim();
}

/* 识图多引擎 + 优先级分组 + 限流自动重试：
   - 按 prio 分组：prio 小的一组先并行试，全部失败才轮到下一组
     （自定义视觉模型 prio=0 优先，智谱 prio=1 兜底）
   - 最后一组若报“访问量过大/限流”，等 2 秒再重试一次 */
async function readImageTextMulti(env, chain, imageBase64, readFn, budgetMs) {
  env = env || process.env;
  readFn = readFn || readImageText;
  var startAt = Date.now();
  var budget = budgetMs || 30000;
  function remaining() { return budget - (Date.now() - startAt); }
  var groups = [];
  chain.forEach(function (vp) {
    var p = typeof vp.prio === "number" ? vp.prio : 0;
    if (!groups[p]) { groups[p] = []; }
    groups[p].push(vp);
  });
  var lastErr = null;
  for (var g = 0; g < groups.length; g++) {
    /* 优先级可能从 1 开始（没有自定义模型时只有智谱），跳过空洞 */
    if (!groups[g]) { continue; }
    var attempts = 0;
    while (attempts < 2) {
      attempts++;
      /* 单次识图最长 20 秒，但不能吃掉整个预算 */
      var perAttempt = Math.max(5000, Math.min(20000, remaining()));
      if (perAttempt < 5000) {
        lastErr = new Error("识图总时间预算不足（请稍后重试）");
        break;
      }
      var jobs = groups[g].map(function (vp) {
        var meta = PROVIDERS[vp.provider];
        var key = vp.apiKey || (meta ? env[meta.envKey] : "");
        if (!key) {
          return Promise.resolve({ ok: false, err: new Error("未配置 " + (meta ? meta.envKey : "自定义模型 API Key")) });
        }
        return readFn(vp.provider, vp.model, imageBase64, key, perAttempt, {
          baseUrl: vp.baseUrl,
          chatPath: vp.chatPath
        })
          .then(function (t) {
            return { ok: true, text: t, provider: vp.provider, model: vp.model };
          })
          .catch(function (e) { return { ok: false, err: e }; });
      });
      var results = await Promise.all(jobs);
      var hit = null;
      for (var i = 0; i < results.length; i++) {
        if (results[i].ok) { hit = results[i]; break; }
      }
      if (hit) { return hit; }
      var errs = results.map(function (r) { return r.err; }).filter(Boolean);
      lastErr = errs[errs.length - 1] || new Error("识图失败");
      var rateLimited = errs.some(function (e) {
        return /访问量过大|限流|429|rate.?limit|繁忙|overload|稍后再试/i.test(String(e && e.message));
      });
      var isLastGroup = g === groups.length - 1;
      /* 非最后一组：失败直接切换下一组（保持优先级）；最后一组限流才重试 */
      if (!rateLimited || !isLastGroup) { break; }
      if (remaining() < 6000) { break; }
      await sleep(2000);
    }
  }
  throw lastErr;
}

/* 尽量从模型输出中解析 JSON（支持纯 JSON / 代码块 / 前后杂文） */
function parseJsonContent(content) {
  if (!content) { return null; }
  var s = String(content).trim();
  try { return JSON.parse(s); } catch (e) {}
  var fence = s.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fence) {
    try { return JSON.parse(fence[1].trim()); } catch (e2) {}
  }
  var start = s.indexOf("{");
  var end = s.lastIndexOf("}");
  if (start >= 0 && end > start) {
    try { return JSON.parse(s.slice(start, end + 1)); } catch (e3) {}
  }
  return null;
}

module.exports = {
  PROVIDERS: PROVIDERS,
  DEEPSEEK_VISION_SUPPORTED: DEEPSEEK_VISION_SUPPORTED,
  hasVision: hasVision,
  sanitizeCustomProviders: sanitizeCustomProviders,
  chatEndpoint: chatEndpoint,
  listAllowedModels: listAllowedModels,
  resolveSecretary: resolveSecretary,
  visionChain: visionChain,
  buildSecretaryMessages: buildSecretaryMessages,
  buildCompressMessages: buildCompressMessages,
  readImageText: readImageText,
  readImageTextMulti: readImageTextMulti,
  getVisionModels: getVisionModels,
  chatCompletion: chatCompletion,
  parseJsonContent: parseJsonContent,
  httpsJsonPost: httpsJsonPost
};
