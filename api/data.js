/* ================================================================
   GET /api/data —— 从 GitHub 读取 data.json 返回给前端
   作用：前端数据读取的第一优先源（后端地址可用时，
   不依赖被墙的 GitHub raw / jsDelivr）。
   ================================================================ */
var github = require("./_lib/github");
var http = require("./_lib/http");

async function runData(env) {
  env = env || process.env;
  var repo = String(env.GITHUB_REPO || "").trim();
  var branch = String(env.GITHUB_BRANCH || "main").trim();
  var token = String(env.GITHUB_TOKEN || "").trim();
  if (!repo || !token) {
    return { status: 500, json: { error: "未配置 GITHUB_REPO / GITHUB_TOKEN 环境变量" } };
  }
  try {
    var r = await github.getFile(repo, branch, "data.json");
    if (r.status === 404) {
      return { status: 404, json: { error: "data.json 尚未创建（先在手机“记录”页保存一次）" } };
    }
    if (r.status !== 200) {
      return { status: 502, json: { error: "GitHub 读取 data.json 失败（HTTP " + r.status + "）" } };
    }
    var obj = JSON.parse(Buffer.from(r.json.content, "base64").toString("utf8"));
    return { status: 200, json: obj };
  } catch (e) {
    return { status: 502, json: { error: "GitHub 读取失败：" + e.message } };
  }
}

module.exports = async function handler(req, res) {
  http.setCors(res);
  if (req.method === "OPTIONS") { res.status(200).end(); return; }
  if (req.method !== "GET") { res.status(405).json({ error: "仅支持 GET" }); return; }
  var result = await runData();
  res.status(result.status).json(result.json);
};

module.exports.runData = runData;
