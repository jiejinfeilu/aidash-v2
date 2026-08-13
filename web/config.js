/* ================================================================
   AiDash 前端配置（B 部分）
   部署后请修改下面两个地址；也可以在手机 App 的
   “设置 → 连接”里填写，App 内的填写会覆盖这里的默认值。
   ================================================================ */
window.AIDASH_CONFIG = {
  /* Vercel 后端地址列表：按顺序自动切换（第一个为主，超时自动换下一个）。
     部署完成后把这里改成真实地址，如 ["https://aidash-seven.vercel.app"] */
  API_BASES: ["https://aidash.vercel.app"],

  /* GitHub 数据 raw 地址（兼容字段，用于设置页展示） */
  RAW_BASE: "https://raw.githubusercontent.com/jiejinfeilu/aidash-v2/main",

  /* 数据读取顺序：jsDelivr CDN 优先（国内更快更稳），GitHub raw 兜底 */
  DATA_BASES: [
    "https://cdn.jsdelivr.net/gh/jiejinfeilu/aidash-v2@main/",
    "https://raw.githubusercontent.com/jiejinfeilu/aidash-v2/main/"
  ],

  /* 默认设置（可在 App “设置”里修改） */
  DEFAULT_SETTINGS: {
    city: "温州",
    lat: "27.99",
    lon: "120.70",
    autoAdopt: false
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
