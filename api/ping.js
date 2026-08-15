/* ================================================================
   GET /api/ping —— 探活 + 返回当前 AI 配置与可用模型
   作用：手机端“测试连接”按钮和 AI 模型下拉框的数据来源。
   不需要口令（只返回配置信息，不返回任何密钥）。
   ================================================================ */
var ai = require("./_lib/ai");
var http = require("./_lib/http");

async function runPing(env) {
  env = env || process.env;
  var providerName = String(env.AI_PROVIDER || "deepseek").toLowerCase();
  var meta = ai.PROVIDERS[providerName] || ai.PROVIDERS.deepseek;
  var defaultModel = String(env[meta.envModel] || meta.model).trim();
  return {
    ok: true,
    api: "aidash-v2",
    time: new Date().toISOString(),
    ai: {
      provider: providerName,
      model: defaultModel,
      visionProvider: String(env.VISION_PROVIDER || "auto")
    },
    models: ai.listAllowedModels(env),
    visionProviders: [
      { id: "auto", label: "自动（推荐）" },
      { id: "deepseek", label: "DeepSeek（V4 Pro）" },
      { id: "zhipu", label: "智谱 GLM" },
      { id: "none", label: "关闭识图" }
    ]
  };
}

module.exports = async function handler(req, res) {
  http.setCors(res);
  if (req.method === "OPTIONS") { res.status(200).end(); return; }
  if (req.method !== "GET") { res.status(405).json({ error: "仅支持 GET" }); return; }
  var result = await runPing();
  res.status(200).json(result);
};

module.exports.runPing = runPing;
