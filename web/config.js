/* ================================================================
   AiDash 前端配置（B 部分）—— v2 修复版
   部署后请把 API_BASES 改成真实地址；也可以在手机 App 的
   “设置 → 连接”里填写，App 内的填写会覆盖这里的默认值。
   ================================================================ */
window.AIDASH_CONFIG = {
  /* Vercel 后端地址列表：按顺序自动切换（第一个为主，超时自动换下一个）。
     部署完成后把这里改成真实地址，如 ["https://aidash-v2-xxxx.vercel.app"]；
     也可在手机“设置 → 连接”里多填几个（每行一个），App 会优先使用。 */
  API_BASES: ["https://aidash-v2.vercel.app"],

  /* GitHub 数据 raw 地址（兼容字段，用于设置页展示与最后兜底） */
  RAW_BASE: "https://raw.githubusercontent.com/jiejinfeilu/aidash-v2/main",

  /* 数据静态镜像列表：前端实际读取顺序是
     后端 /api/data（自动优先）→ 下面这些 jsDelivr 镜像 → GitHub raw 兜底。
     jsDelivr 在国内有多条线路，逐个尝试提高成功率。 */
  DATA_BASES: [
    "https://cdn.jsdelivr.net/gh/jiejinfeilu/aidash-v2@main/",
    "https://fastly.jsdelivr.net/gh/jiejinfeilu/aidash-v2@main/",
    "https://gcore.jsdelivr.net/gh/jiejinfeilu/aidash-v2@main/",
    "https://testingcf.jsdelivr.net/gh/jiejinfeilu/aidash-v2@main/"
  ],

  /* 默认设置（可在 App “设置”里修改） */
  DEFAULT_SETTINGS: {
    city: "温州",
    lat: "27.99",
    lon: "120.70",
    autoAdopt: false,
    autoFullscreen: true,
    aiProvider: "deepseek",
    aiModel: "deepseek-v4-flash",
    visionProvider: "auto"
  },

  /* 默认版块布局（与 D 部分 generate_image.py 保持一致，可在 App 里改） */
  DEFAULT_LAYOUT: {
    order: ["header", "weather", "feeds", "countdown", "todo", "notes", "quote"],
    heights: {
      weather: 170,
      feeds: 300,
      countdown: 150,
      todo: 240,
      notes: 180,
      quote: 90
    }
  }
};
