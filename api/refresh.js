/* ================================================================
   POST /api/refresh —— 立即推送到 Kindle
   入参：{ pin }
   作用：通过 GitHub API 触发仓库里的 “Daily Kindle Push” 工作流，
   让它立刻生成仪表盘并发送邮件（无需等定时任务）。
   注意：GITHUB_TOKEN 需要额外勾选 Actions 的 Read and write 权限，
   否则 GitHub 会返回 403，手机端会提示“触发失败”。
   ================================================================ */
var github = require("./_lib/github");
var http = require("./_lib/http");

async function runRefresh(input) {
  var env = input.env || process.env;
  var pin = String(input.pin || "");
  if (!env.APP_PIN || pin !== env.APP_PIN) {
    return { status: 401, json: { error: "口令错误" } };
  }
  var repo = String(env.GITHUB_REPO || "").trim();
  var branch = String(env.GITHUB_BRANCH || "main").trim();
  var token = String(env.GITHUB_TOKEN || "").trim();
  if (!repo || !token) {
    return { status: 500, json: { error: "未配置 GITHUB_REPO / GITHUB_TOKEN 环境变量" } };
  }
  try {
    var r = await github.dispatchWorkflow(repo, branch, "daily_push.yml");
    if (r.status === 204 || (r.status >= 200 && r.status < 300)) {
      return { status: 200, json: { ok: true, message: "已触发，1~3 分钟后 Kindle 收到新仪表盘" } };
    }
    if (r.status === 403 || r.status === 404) {
      return {
        status: 502,
        json: { error: "触发失败（HTTP " + r.status + "）：请确认 GITHUB_TOKEN 已勾选 Actions 读写权限，且工作流文件存在" }
      };
    }
    return { status: 502, json: { error: "触发失败（HTTP " + r.status + "）" } };
  } catch (e) {
    return { status: 502, json: { error: "触发失败：" + e.message } };
  }
}

module.exports = async function handler(req, res) {
  http.setCors(res);
  if (req.method === "OPTIONS") { res.status(200).end(); return; }
  if (req.method !== "POST") { res.status(405).json({ error: "仅支持 POST" }); return; }
  var body;
  try {
    body = JSON.parse(await http.readBody(req, 1024 * 1024));
  } catch (e) {
    res.status(400).json({ error: "请求体解析失败：" + e.message });
    return;
  }
  var result = await runRefresh(body);
  res.status(result.status).json(result.json);
};

module.exports.runRefresh = runRefresh;
