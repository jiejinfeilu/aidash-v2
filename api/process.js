/* ================================================================
   POST /api/process —— AI 秘书分析（v2 修复版）
   入参：{ pin, text?, imageBase64?, provider?, model?, visionProvider?, history? }
   - pin：与 APP_PIN 一致
   - text：用户文字（可选，与图片至少有一个）
   - imageBase64：压缩后的 base64 data URL
   - provider/model：手机端选的分析模型（需在白名单 ALLOWED_AI_MODELS）
   - visionProvider：识图引擎（auto/deepseek/zhipu/openai/none，可逗号兜底）
   - history：最近 8 条对话（多轮修订用）
   返回：{ ok, provider, model, visionProvider, visionUsed,
           summary, plan, todos, countdowns, notes, shopping, markdown }
   ================================================================ */
var ai = require("./_lib/ai");
var http = require("./_lib/http");

/* 计算北京时间（Asia/Shanghai）的“YYYY-MM-DD（星期X）” */
function beijingToday() {
  var parts = {};
  new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric", month: "2-digit", day: "2-digit", weekday: "long"
  }).formatToParts(new Date()).forEach(function (p) {
    if (p.type !== "literal") { parts[p.type] = p.value; }
  });
  return parts.year + "-" + parts.month + "-" + parts.day + "，" + parts.weekday + "。";
}

/* 清洗对话历史：只保留 user/assistant 文本，最多 8 条，单条限长 */
function cleanHistory(history) {
  var out = [];
  if (!Array.isArray(history)) { return out; }
  history.slice(-8).forEach(function (h) {
    if (!h || typeof h !== "object") { return; }
    var role = h.role === "user" ? "user" : "assistant";
    var c = String(h.content || "").trim();
    if (c) { out.push({ role: role, content: c.slice(0, 4000) }); }
  });
  return out;
}

/* 核心逻辑（独立出来便于本地测试） */
async function runProcess(input) {
  var env = input.env || process.env;

  /* 1. 口令校验 */
  var pin = String(input.pin || "");
  if (!env.APP_PIN || pin !== env.APP_PIN) {
    return { status: 401, json: { error: "口令错误" } };
  }

  /* 2. 参数校验 */
  var text = String(input.text || "").trim();
  var imageBase64 = String(input.imageBase64 || "");
  var userName = String(input.userName || "").trim().slice(0, 20);
  var userNameVariants = [];
  String(input.userNameVariants || "").split(/[,，、;；]/).forEach(function (s) {
    s = String(s || "").trim().slice(0, 20);
    if (s && userNameVariants.length < 10) { userNameVariants.push(s); }
  });
  var aiTone = ["活泼", "严肃"].indexOf(String(input.aiTone || "").trim()) >= 0 ? String(input.aiTone).trim() : "默认";
  var aiGreeting = String(input.aiGreeting || "").trim().slice(0, 60);
  var personaMd = String(input.personaMd || "").trim().slice(0, 12000);
  var personaName = String(input.personaName || "").trim().slice(0, 30);
  var personaTask = String(input.personaTask || "").trim().toLowerCase();
  /* 人设压缩任务不需要文字/图片 */
  if (!text && !imageBase64 && personaTask !== "compress") {
    return { status: 400, json: { error: "缺少文字或图片" } };
  }
  if (imageBase64 && !/^data:image\/(png|jpe?g|webp|gif|bmp);base64,/.test(imageBase64)) {
    return { status: 400, json: { error: "图片格式不支持（需要 base64 data URL）" } };
  }
  if (imageBase64.length > 4.4e6) {
    return { status: 413, json: { error: "图片太大（压缩后再试）" } };
  }
  var history = cleanHistory(input.history);

  /* 3. 解析秘书模型（手机端选择 + 白名单校验） */
  var secretary;
  try {
    secretary = ai.resolveSecretary(env, input);
  } catch (e) {
    return { status: 400, json: { error: e.message } };
  }
  var apiKey = secretary.apiKey || (secretary.meta.envKey ? env[secretary.meta.envKey] : "");
  if (!apiKey) {
    return { status: 500, json: { error: "未配置 " + secretary.meta.envKey + " 环境变量" } };
  }

  /* 4.5 人设档案整理压缩（不走识图/待办流程） */
  if (personaTask === "compress") {
    if (!personaMd) {
      return { status: 400, json: { error: "当前人设档案为空，无法压缩" } };
    }
    try {
      var maxTokens2 = 4096;
      if (secretary.provider === "zhipu") {
        maxTokens2 = parseInt(env.ZHIPU_MAX_TOKENS || "1024", 10) || 1024;
      }
      var cContent = await ai.chatCompletion({
        provider: secretary.provider,
        apiKey: apiKey,
        model: secretary.model,
        messages: ai.buildCompressMessages(personaMd),
        baseUrl: secretary.baseUrl,
        chatPath: secretary.chatPath,
        timeoutMs: 45000,
        maxTokens: maxTokens2
      });
      var cParsed = ai.parseJsonContent(cContent);
      var cMd = cParsed && cParsed.personaMd ? String(cParsed.personaMd).trim() : "";
      if (!cMd) {
        return { status: 502, json: { error: "压缩失败：AI 未返回有效档案" } };
      }
      return {
        status: 200,
        json: {
          ok: true,
          personaMd: cMd.slice(0, 12000),
          summary: cParsed.summary ? String(cParsed.summary).trim().slice(0, 300) : "",
          provider: secretary.provider,
          model: secretary.model
        }
      };
    } catch (e) {
      return { status: 502, json: { error: "压缩失败：" + e.message } };
    }
  }

  /* 5. 解析识图引擎（仅当有图片时才需要） */
  var vc = null;
  var visionUsed = "";
  if (imageBase64) {
    try {
      vc = ai.visionChain(env, secretary, input.visionProvider, input.customProviders);
    } catch (e) {
      return { status: 400, json: { error: e.message } };
    }
    visionUsed = vc.mode === "none" ? "none" : "";
  }

  /* 总预算：识图 + 分析共享 52 秒（Vercel 免费版函数上限 60 秒） */
  var TOTAL_BUDGET = 52000;
  var startAt = Date.now();
  var secBase = {
    text: text, today: beijingToday(), history: history,
    userName: userName, userNameVariants: userNameVariants,
    aiTone: aiTone, aiGreeting: aiGreeting, personaMd: personaMd, personaName: personaName
  };

  /* 6. 组装消息（有图时按引擎选择单次调用或先读图再分析） */
  var messages;
  if (imageBase64) {
    if (vc.mode === "none") {
      return { status: 400, json: { error: "已关闭识图（visionProvider=none），请先在手机设置里开启识图引擎" } };
    }
    if (vc.mode === "single") {
      /* 秘书模型本身能看图：一次调用直接输出 JSON */
      messages = ai.buildSecretaryMessages(Object.assign({ singleImage: imageBase64 }, secBase));
      visionUsed = secretary.provider + ":" + secretary.model;
    } else {
      /* 两段式：先并行读图（多模型兜底 + 限流重试），再交给秘书分析 */
      var img;
      try {
        img = await ai.readImageTextMulti(env, vc.chain, imageBase64, undefined, TOTAL_BUDGET);
      } catch (e) {
        return {
          status: 502,
          json: { error: "识图失败（已尝试全部识图引擎）：" + e.message }
        };
      }
      visionUsed = img.provider + ":" + img.model;
      messages = ai.buildSecretaryMessages(Object.assign({ imageText: img.text }, secBase));
    }
  } else {
    messages = ai.buildSecretaryMessages(secBase);
  }

  /* 7. 调用 AI */
  try {
    /* 智谱免费模型输出上限 1024；付费模型可用 ZHIPU_MAX_TOKENS 调大 */
    var maxTokens = 4096;
    if (secretary.provider === "zhipu") {
      maxTokens = parseInt(env.ZHIPU_MAX_TOKENS || "1024", 10) || 1024;
    }
    /* 带图时受总预算约束；纯文字请求保留 45 秒 */
    var secTimeout = imageBase64
      ? Math.max(8000, Math.min(30000, TOTAL_BUDGET - (Date.now() - startAt)))
      : 45000;
    var content = await ai.chatCompletion({
      provider: secretary.provider,
      apiKey: apiKey,
      model: secretary.model,
      messages: messages,
      baseUrl: secretary.baseUrl,
      chatPath: secretary.chatPath,
      timeoutMs: secTimeout,
      maxTokens: maxTokens
    });
    var parsed = ai.parseJsonContent(content);
    if (!parsed || typeof parsed !== "object") {
      return { status: 502, json: { error: "AI 返回无法解析的 JSON" } };
    }
    return {
      status: 200,
      json: {
        ok: true,
        provider: secretary.provider,
        model: secretary.model,
        visionProvider: String(input.visionProvider || env.VISION_PROVIDER || "auto"),
        visionUsed: visionUsed,
        summary: parsed.summary || "",
        plan: parsed.plan || [],
        todos: parsed.todos || [],
        countdowns: parsed.countdowns || [],
        notes: parsed.notes || [],
        shopping: parsed.shopping || [],
        markdown: parsed.markdown || "",
        personaUpdate: parsed.personaUpdate ? String(parsed.personaUpdate).trim().slice(0, 4000) : ""
      }
    };
  } catch (e) {
    var msg = "AI 调用失败：" + e.message;
    if (/超时|timeout/i.test(String(e.message))) {
      msg += "。可能是免费模型繁忙或分析模型较慢：请稍后重试，或把分析模型切回 DeepSeek V4 Flash";
    }
    return { status: 502, json: { error: msg } };
  }
}

/* Vercel 函数入口 */
module.exports = async function handler(req, res) {
  http.setCors(res);
  if (req.method === "OPTIONS") { res.status(200).end(); return; }
  if (req.method !== "POST") { res.status(405).json({ error: "仅支持 POST" }); return; }

  var body;
  try {
    body = JSON.parse(await http.readBody(req, 5 * 1024 * 1024));
  } catch (e) {
    res.status(400).json({ error: "请求体解析失败：" + e.message });
    return;
  }

  var result = await runProcess(body);
  res.status(result.status).json(result.json);
};

module.exports.runProcess = runProcess;
