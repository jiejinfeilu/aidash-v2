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
  if (!text && !imageBase64) {
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
  var apiKey = env[secretary.meta.envKey];
  if (!apiKey) {
    return { status: 500, json: { error: "未配置 " + secretary.meta.envKey + " 环境变量" } };
  }

  /* 4. 解析识图引擎 */
  var vc = ai.visionChain(env, secretary, input.visionProvider);
  var visionUsed = vc.mode === "none" ? "none" : "";

  /* 5. 组装消息（有图时按引擎选择单次调用或先读图再分析） */
  var messages;
  if (imageBase64) {
    if (vc.mode === "none") {
      return { status: 400, json: { error: "已关闭识图（visionProvider=none），请先在手机设置里开启识图引擎" } };
    }
    if (vc.mode === "single") {
      /* 秘书模型本身能看图：一次调用直接输出 JSON */
      messages = ai.buildSecretaryMessages({
        text: text, today: beijingToday(), history: history, singleImage: imageBase64
      });
      visionUsed = secretary.provider + ":" + secretary.model;
    } else {
      /* 两段式：先用视觉模型读图，再交给秘书分析 */
      var imageText = "";
      var lastErr = null;
      for (var i = 0; i < vc.chain.length; i++) {
        var vp = vc.chain[i];
        var vKey = env[ai.PROVIDERS[vp.provider].envKey];
        if (!vKey) {
          lastErr = new Error("未配置 " + ai.PROVIDERS[vp.provider].envKey);
          continue;
        }
        try {
          imageText = await ai.readImageText(vp.provider, vp.model, imageBase64, vKey, 55000);
          visionUsed = vp.provider + ":" + vp.model;
          break;
        } catch (e) {
          lastErr = e;
        }
      }
      if (!imageText) {
        return {
          status: 502,
          json: { error: "识图失败（已尝试全部识图引擎）：" + (lastErr ? lastErr.message : "未知错误") }
        };
      }
      messages = ai.buildSecretaryMessages({
        text: text, today: beijingToday(), history: history, imageText: imageText
      });
    }
  } else {
    messages = ai.buildSecretaryMessages({ text: text, today: beijingToday(), history: history });
  }

  /* 6. 调用 AI */
  try {
    var content = await ai.chatCompletion({
      provider: secretary.provider,
      apiKey: apiKey,
      model: secretary.model,
      messages: messages,
      timeoutMs: 55000
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
        markdown: parsed.markdown || ""
      }
    };
  } catch (e) {
    return { status: 502, json: { error: "AI 调用失败：" + e.message } };
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
