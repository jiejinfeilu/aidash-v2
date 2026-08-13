# -*- coding: utf-8 -*-
"""AiDash — 生成每日仪表盘图片（v2.1：多版式 + 星际驾驶舱质感）

版式（data.json.settings.layoutPreset 或 --preset）：
    portrait_dual  竖屏双栏（1072×1448，Kindle 用）
    landscape      横屏驾驶舱（1920×1080，手机全屏用）
    classic        经典单栏（1072×1448，白底黑字）

视觉：深空渐变背景 + 星点 + 微网格 + 面板辉光描边 + 数字发光 +
      LED 标题 + CRT 扫描线（Kindle 灰阶下仍保持高对比）。

用法：
    python generate_image.py --local --preset portrait_dual --out x.png
"""
import argparse
import json
import os
import random
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

try:
    import config_local as CFG
except Exception:
    CFG = None

# ---------------- 画布与预设 ----------------
PRESETS = {
    "portrait_dual": {"w": 1072, "h": 1448, "label": "竖屏双栏"},
    "landscape":     {"w": 1920, "h": 1080, "label": "横屏驾驶舱"},
    "classic":       {"w": 1072, "h": 1448, "label": "经典单栏"},
}
DEFAULT_PRESET = "portrait_dual"
DAILY_CUSTOM_COUNT = 2   # 每天前 N 次生成使用自定义名言

MARGIN = 18
GAP = 10
HEADER_H = 175
PANEL_TITLE_H = 48

WEEK = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
KNOWN_MODULES = {"weather", "feeds", "countdown", "todo", "notes", "quote"}

EN_LABELS = {
    "天气": "WEATHER",
    "资讯热榜": "FEED // SECTOR",
    "倒计时": "TIMER",
    "安排 / 待办": "TASKS",
    "AI 笔记": "MEMO",
    "每日一言": "QUOTE",
    "综合情报": "INTEL // HUB",
}

DEFAULT_QUOTES = [
    "博观而约取，厚积而薄发。",
    "不积跬步，无以至千里；不积小流，无以成江海。",
    "知之者不如好之者，好之者不如乐之者。",
    "路漫漫其修远兮，吾将上下而求索。",
    "纸上得来终觉浅，绝知此事要躬行。",
    "凡事预则立，不预则废。",
    "学而不思则罔，思而不学则殆。",
    "天行健，君子以自强不息。",
    "温故而知新，可以为师矣。——《论语》",
    "三人行，必有我师焉。——《论语》",
    "己所不欲，勿施于人。——《论语》",
    "工欲善其事，必先利其器。——《论语》",
    "岁寒，然后知松柏之后凋也。——《论语》",
    "见贤思齐焉，见不贤而内自省也。——《论语》",
    "敏而好学，不耻下问。——《论语》",
    "知之为知之，不知为不知，是知也。——《论语》",
    "士不可以不弘毅，任重而道远。——《论语》",
    "千里之行，始于足下。——《道德经》",
    "上善若水，水善利万物而不争。——《道德经》",
    "知人者智，自知者明。——《道德经》",
    "合抱之木，生于毫末。——《道德经》",
    "慎终如始，则无败事。——《道德经》",
    "知足不辱，知止不殆。——《道德经》",
    "吾生也有涯，而知也无涯。——《庄子》",
    "君子之交淡如水。——《庄子》",
    "锲而不舍，金石可镂。——《荀子》",
    "青，取之于蓝，而青于蓝。——《荀子》",
    "业精于勤，荒于嬉；行成于思，毁于随。——韩愈",
    "书山有路勤为径，学海无涯苦作舟。——韩愈",
    "会当凌绝顶，一览众山小。——杜甫",
    "读书破万卷，下笔如有神。——杜甫",
    "随风潜入夜，润物细无声。——杜甫",
    "长风破浪会有时，直挂云帆济沧海。——李白",
    "天生我材必有用，千金散尽还复来。——李白",
    "大鹏一日同风起，扶摇直上九万里。——李白",
    "欲穷千里目，更上一层楼。——王之涣",
    "不畏浮云遮望眼，只缘身在最高层。——王安石",
    "山重水复疑无路，柳暗花明又一村。——陆游",
    "位卑未敢忘忧国。——陆游",
    "问渠那得清如许？为有源头活水来。——朱熹",
    "静以修身，俭以养德。——诸葛亮",
    "非淡泊无以明志，非宁静无以致远。——诸葛亮",
    "亦余心之所善兮，虽九死其犹未悔。——屈原",
    "盛年不重来，一日难再晨。——陶渊明",
    "采菊东篱下，悠然见南山。——陶渊明",
    "沉舟侧畔千帆过，病树前头万木春。——刘禹锡",
    "山不在高，有仙则名。——刘禹锡",
    "海上生明月，天涯共此时。——张九龄",
    "海内存知己，天涯若比邻。——王勃",
    "落霞与孤鹜齐飞，秋水共长天一色。——王勃",
    "但愿人长久，千里共婵娟。——苏轼",
    "竹杖芒鞋轻胜马，谁怕？一蓑烟雨任平生。——苏轼",
    "回首向来萧瑟处，归去，也无风雨也无晴。——苏轼",
    "腹有诗书气自华。——苏轼",
    "不识庐山真面目，只缘身在此山中。——苏轼",
    "人生如逆旅，我亦是行人。——苏轼",
    "会挽雕弓如满月，西北望，射天狼。——苏轼",
    "苟日新，日日新，又日新。——《大学》",
    "博学之，审问之，慎思之，明辨之，笃行之。——《中庸》",
    "玉不琢，不成器；人不学，不知道。——《礼记》",
    "居安思危，思则有备，有备无患。——《左传》",
    "少壮不努力，老大徒伤悲。——《长歌行》",
    "厚德载物。——《周易》",
    "穷则变，变则通，通则久。——《周易》",
    "黑发不知勤学早，白首方悔读书迟。——颜真卿",
    "千磨万击还坚劲，任尔东西南北风。——郑燮",
    "落红不是无情物，化作春泥更护花。——龚自珍",
    "莫问收获，但问耕耘。——曾国藩",
    "天道忌巧。——曾国藩",
    "此心光明，亦复何言。——王阳明",
]


# ---------------- 配置与字体 ----------------
def get_cfg(key, default):
    if os.environ.get(key):
        return os.environ.get(key)
    if CFG is not None and hasattr(CFG, key) and getattr(CFG, key):
        return getattr(CFG, key)
    return default


FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]
MONO_CANDIDATES = [
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/cour.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]

_font_path = None
_mono_path = None
_cache = {}


def font(size):
    global _font_path
    if _font_path is None:
        _font_path = get_cfg("FONT_PATH", "") or next(
            (p for p in FONT_CANDIDATES if os.path.exists(p)), None
        )
        if not _font_path:
            sys.exit("找不到中文字体！请把字体路径填到 config_local.py 的 FONT_PATH")
    key = ("f", size)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(_font_path, size)
    return _cache[key]


def font_mono(size):
    global _mono_path
    if _mono_path is None:
        _mono_path = next((p for p in MONO_CANDIDATES if os.path.exists(p)), None)
    key = ("m", size)
    if key not in _cache:
        if _mono_path:
            _cache[key] = ImageFont.truetype(_mono_path, size)
        else:
            _cache[key] = font(size)
    return _cache[key]


# ---------------- 主题 ----------------
class Style:
    pass


def make_style(kind):
    s = Style()
    if kind == "sci":
        s.bg_top = (13, 20, 44)
        s.bg_bottom = (4, 6, 13)
        s.panel_top = (21, 32, 60)
        s.panel_bottom = (10, 16, 32)
        s.border = (58, 104, 158)
        s.hi = (120, 175, 225)
        s.glow = (82, 232, 224)
        s.accent = (82, 232, 224)
        s.accent2 = (125, 255, 160)
        s.amber = (255, 190, 100)
        s.fg = (226, 236, 250)
        s.muted = (132, 160, 200)
        s.dim = (76, 102, 142)
        s.warn = (255, 120, 120)
        s.bg = (8, 12, 24)
        s.panel = (13, 20, 36)
        s.line = (40, 66, 100)
        s.pink = (255, 154, 213)
        s.purple = (183, 139, 255)
    else:
        white = (255, 255, 255)
        black = (0, 0, 0)
        s.bg_top = white
        s.bg_bottom = white
        s.panel_top = white
        s.panel_bottom = white
        s.border = black
        s.hi = black
        s.glow = black
        s.accent = black
        s.accent2 = black
        s.amber = black
        s.fg = black
        s.muted = (90, 90, 90)
        s.dim = (150, 150, 150)
        s.warn = black
        s.bg = white
        s.panel = white
        s.line = black
        s.pink = black
        s.purple = black
    return s


STYLE = make_style("sci")


# ---------------- 画布 / 辉光层 ----------------
BASE = None
FX = None


def vgrad_img(w, h, top, bottom):
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for yy in range(h):
        t = yy / max(1, h - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        d.line([(0, yy), (w, yy)], fill=c)
    return img


def paste_gradient(base, box, top, bottom):
    x, y, w, h = box
    base.paste(vgrad_img(w, h, top, bottom), (x, y))


def make_bg(w, h, s):
    img = vgrad_img(w, h, s.bg_top, s.bg_bottom)
    d = ImageDraw.Draw(img)
    rnd = random.Random(42)
    # 微网格
    for gx in range(0, w, 120):
        d.line([(gx, 0), (gx, h)], fill=(18, 26, 48), width=1)
    for gy in range(0, h, 120):
        d.line([(0, gy), (w, gy)], fill=(18, 26, 48), width=1)
    # 十字准星小标记（电脑界面感）
    for gx in range(240, w, 240):
        for gy in range(240, h, 240):
            d.line([(gx - 4, gy), (gx + 4, gy)], fill=(26, 38, 66))
            d.line([(gx, gy - 4), (gx, gy + 4)], fill=(26, 38, 66))
    # 星点
    for _ in range(int(w * h / 7000)):
        x = rnd.randint(0, w - 1)
        y = rnd.randint(0, h - 1)
        b = rnd.randint(30, 100)
        d.point((x, y), fill=(b, b, b + 12))
    for _ in range(18):
        x = rnd.randint(0, w - 1)
        y = rnd.randint(0, h - 1)
        d.ellipse([x, y, x + 1, y + 1], fill=s.accent)
    # 四角闪光星
    for _ in range(16):
        x = rnd.randint(0, w - 1)
        y = rnd.randint(0, h - 1)
        ss = rnd.randint(2, 5)
        c = (232, 196, 224) if rnd.random() < 0.5 else (196, 204, 255)
        d.line([(x - ss, y), (x + ss, y)], fill=c, width=1)
        d.line([(x, y - ss), (x, y + ss)], fill=c, width=1)
    return img


def begin_canvas(w, h, s):
    global BASE, FX
    BASE = make_bg(w, h, s)
    FX = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    return BASE, ImageDraw.Draw(BASE)


def finish_canvas():
    global BASE, FX
    W, H = BASE.size
    sd = ImageDraw.Draw(FX)
    # CRT 扫描线
    for yy in range(0, H, 3):
        sd.line([(0, yy), (W, yy)], fill=(0, 0, 0, 20))
    img = Image.alpha_composite(BASE.convert("RGBA"), FX).convert("RGB")
    BASE = None
    FX = None
    return img


def fxd():
    return ImageDraw.Draw(FX) if FX is not None else None


def glow_rounded(box, radius, color, width, passes=5):
    if FX is None:
        return
    d = fxd()
    x, y, w, h = box
    for i in range(passes):
        exp = i * 2
        a = max(14, int(95 * (passes - i) / passes))
        d.rounded_rectangle(
            [x - exp, y - exp, x + w + exp, y + h + exp],
            radius=radius + exp,
            outline=color + (a,),
            width=width + i,
        )


def glow_text(pos, s, f, color, passes=5):
    if FX is None:
        return
    d = fxd()
    x, y = pos
    for i in range(passes, 0, -1):
        a = max(32, int(170 * i / passes))
        c = color + (a,)
        d.text((x - i, y), s, font=f, fill=c)
        d.text((x + i, y), s, font=f, fill=c)
        d.text((x, y - i), s, font=f, fill=c)
        d.text((x, y + i), s, font=f, fill=c)


# ---------------- 文本工具 ----------------
def tw(draw, s, f):
    return draw.textlength(s, font=f)


def truncate(draw, s, f, max_w):
    s = str(s)
    if tw(draw, s, f) <= max_w:
        return s
    t = s
    while t and tw(draw, t + "…", f) > max_w:
        t = t[:-1]
    return t + "…"


def wrap_lines(draw, s, f, max_w):
    lines = []
    cur = ""
    for ch in str(s):
        if tw(draw, cur + ch, f) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def text_spaced(draw, xy, s, f, fill, spacing=2):
    x, y = xy
    for ch in s:
        draw.text((x, y), ch, font=f, fill=fill)
        x += tw(draw, ch, f) + spacing


def draw_signal(draw, x, y, color, n=5):
    """Wi-Fi 式信号条小部件"""
    for i in range(n):
        hh = 6 + i * 4
        draw.rounded_rectangle([x + i * 8, y + (26 - hh), x + i * 8 + 5, y + 26], radius=1, fill=color)


def draw_loading_bar(draw, x, y, w, pct, label):
    """电脑终端式加载进度线：[▮▮▮▮▮▯▯▯▯] 66% ▍"""
    h = 16
    if STYLE.bg != (255, 255, 255):
        draw.rounded_rectangle([x, y, x + w, y + h], radius=5, outline=STYLE.dim, width=1)
        fill_w = int((w - 6) * pct / 100.0)
        if fill_w > 0:
            draw.rounded_rectangle([x + 3, y + 3, x + 3 + fill_w, y + h - 3], radius=3, fill=STYLE.accent2)
            if FX is not None:
                fxd().rectangle([x + 3, y + 3, x + 3 + fill_w, y + h - 3], fill=STYLE.accent2 + (110,))
        # 分节刻度
        for sx in range(x + 6, x + w - 6, 14):
            draw.line([(sx, y), (sx, y + h)], fill=STYLE.panel_bottom, width=1)
    else:
        draw.rounded_rectangle([x, y, x + w, y + h], radius=5, outline="black", width=1)
        fill_w = int((w - 6) * pct / 100.0)
        if fill_w > 0:
            draw.rounded_rectangle([x + 3, y + 3, x + 3 + fill_w, y + h - 3], radius=3, fill="black")
    lf = font(15)
    draw.text((x, y + h + 5), label, font=lf, fill=STYLE.muted)
    pf = font_mono(17)
    ptxt = "%d%%" % pct
    draw.text((x + w - tw(draw, ptxt, pf), y + h + 4), ptxt, font=pf, fill=STYLE.fg)
    cxs = x + w + 8
    draw.rectangle([cxs, y + h + 5, cxs + 8, y + h + 19], fill=STYLE.accent)


# ---------------- 科技 + 萌趣 小部件 ----------------
def draw_kawaii_face(draw, cx, cy, r=5, smile=0.5, color=None):
    """Q 版小脸：两点眼睛 + 微笑嘴（smile 越大嘴越弯）"""
    c = color or STYLE.fg
    ex = r * 0.55
    ey = r * 0.5
    draw.ellipse([cx - ex - 1.5, cy - ey, cx - ex + 1.5, cy - ey + 3], fill=c)
    draw.ellipse([cx + ex - 1.5, cy - ey, cx + ex + 1.5, cy - ey + 3], fill=c)
    mx0 = cx - r * 0.35
    mx1 = cx + r * 0.35
    my = cy + r * 0.45
    arc_h = r * (0.15 + 0.4 * smile)
    draw.arc([mx0, my - arc_h, mx1, my + arc_h], 20, 160, fill=c, width=1)


def draw_mascot(draw, cx, cy, r=16):
    """小星球机器人吉祥物（顶部天线 + 腮红）"""
    if STYLE.bg == (255, 255, 255):
        return
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=STYLE.panel)
    draw.arc([cx - r, cy - r, cx + r, cy + r], 0, 360, fill=STYLE.accent, width=2)
    draw.line([(cx, cy - r), (cx, cy - r - 6)], fill=STYLE.accent, width=2)
    draw.ellipse([cx - 2, cy - r - 8, cx + 2, cy - r - 4], fill=STYLE.pink)
    draw_kawaii_face(draw, cx, cy + 2, r=6, smile=0.8)
    draw.ellipse([cx - 8, cy + 3, cx - 5, cy + 6], fill=STYLE.pink)
    draw.ellipse([cx + 5, cy + 3, cx + 8, cy + 6], fill=STYLE.pink)


def draw_sparkle(draw, x, y, s=5, color=None):
    """四角闪光星"""
    c = color or STYLE.pink
    draw.line([(x - s, y), (x + s, y)], fill=c, width=2)
    draw.line([(x, y - s), (x, y + s)], fill=c, width=2)


def draw_battery(draw, x, y, level=72, w=34, h=15):
    """电池电量条（低电量变橙）"""
    level = max(0, min(100, level))
    c = STYLE.accent2 if level > 30 else STYLE.amber
    draw.rounded_rectangle([x, y, x + w, y + h], radius=4, outline=STYLE.muted, width=1)
    fill_w = int((w - 4) * level / 100.0)
    if fill_w > 0:
        draw.rounded_rectangle([x + 2, y + 2, x + 2 + fill_w, y + h - 2], radius=2, fill=c)
    draw.rectangle([x + w + 2, y + 5, x + w + 6, y + h - 5], fill=STYLE.muted)


def draw_radar(draw, x, y, r=15):
    """迷你雷达：外圈 + 扫描亮弧 + 回波点"""
    if STYLE.bg == (255, 255, 255):
        return
    draw.arc([x - r, y - r, x + r, y + r], 0, 360, fill=STYLE.dim, width=2)
    draw.arc([x - r, y - r, x + r, y + r], -60, 40, fill=STYLE.accent, width=2)
    draw.line([(x, y), (x + r - 2, y)], fill=STYLE.accent, width=1)
    draw.ellipse([x - 3, y - 3, x - 1, y - 1], fill=STYLE.accent2)
    draw.ellipse([x + 4, y - 5, x + 6, y - 3], fill=STYLE.accent2)


def draw_mini_bars(draw, x, y, label, pct, color, w=70, h=8):
    """迷你占用条（CPU / MEM 用）"""
    lf = font(12)
    draw.text((x, y - 1), label, font=lf, fill=STYLE.muted)
    draw.rounded_rectangle([x + 30, y, x + 30 + w, y + h], radius=3, outline=STYLE.dim, width=1)
    fw = int((w - 2) * pct / 100.0)
    if fw > 0:
        draw.rounded_rectangle([x + 31, y + 1, x + 31 + fw, y + h - 1], radius=2, fill=color)


def draw_cloud(draw, cx, cy, s=18, color=None, face=True):
    """Q 版云朵（带笑脸）"""
    c = color or STYLE.accent
    draw.ellipse([cx - s, cy - s * 0.5, cx - s * 0.3, cy + s * 0.7], fill=c)
    draw.ellipse([cx - s * 0.45, cy - s, cx + s * 0.4, cy + s * 0.6], fill=c)
    draw.ellipse([cx + s * 0.1, cy - s * 0.6, cx + s * 0.9, cy + s * 0.7], fill=c)
    draw.rounded_rectangle([cx - s, cy + s * 0.2, cx + s * 0.9, cy + s * 0.75], radius=4, fill=c)
    if face:
        draw_kawaii_face(draw, cx + s * 0.05, cy + s * 0.35, r=s * 0.24, smile=0.7)


def draw_sun(draw, cx, cy, s=16, color=None, face=True):
    """Q 版太阳（带笑脸）"""
    import math
    c = color or STYLE.amber
    for i in range(8):
        a = i * 45
        x1 = cx + math.cos(math.radians(a)) * (s + 3)
        y1 = cy + math.sin(math.radians(a)) * (s + 3)
        x2 = cx + math.cos(math.radians(a)) * (s + 7)
        y2 = cy + math.sin(math.radians(a)) * (s + 7)
        draw.line([(x1, y1), (x2, y2)], fill=c, width=2)
    draw.ellipse([cx - s, cy - s, cx + s, cy + s], fill=c)
    if face:
        draw_kawaii_face(draw, cx, cy, r=s * 0.5, smile=0.7)


# ---------------- 面板与标题 ----------------
def panel(draw, box, radius=None):
    x, y, w, h = box
    if STYLE.bg == (255, 255, 255):
        draw.rounded_rectangle([x, y, x + w, y + h], radius=16, outline="black", width=2)
        return
    r = radius or 18
    paste_gradient(BASE, box, STYLE.panel_top, STYLE.panel_bottom)
    draw.rounded_rectangle([x, y, x + w, y + h], radius=r, outline=STYLE.border, width=2)
    # 顶部高光（玻璃感）
    draw.line([(x + 10, y + 2), (x + w - 10, y + 2)], fill=STYLE.hi, width=1)
    # 四角小圆点（替代直角括号，更柔和）
    for cx, cy in [(x + 7, y + 7), (x + w - 7, y + 7), (x + 7, y + h - 7), (x + w - 7, y + h - 7)]:
        draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=STYLE.accent)
    glow_rounded(box, r, STYLE.glow, 2, 5)


def title(draw, box, text, size=24):
    x, y, w, h = box
    if STYLE.bg == (255, 255, 255):
        draw.rectangle([x + 16, y + 12, x + 21, y + 34], fill="black")
        draw.text((x + 30, y + 9), text, font=font(26), fill="black")
        draw.line([x + 16, y + 46, x + w - 16, y + 46], fill=(224, 224, 224), width=2)
        return
    # LED 指示灯
    draw.ellipse([x + 18, y + 14, x + 26, y + 22], fill=STYLE.accent2)
    draw.text((x + 32, y + 8), text, font=font(size), fill=STYLE.fg)
    # 右侧英文小标签
    en = EN_LABELS.get(text, "")
    if en:
        ef = font(14)
        text_spaced(draw, (x + w - 16 - tw(draw, en, ef) - 4 * (len(en) - 1), y + 12), en, ef, STYLE.muted, 2)
    # 底部辉光线
    draw.line([x + 18, y + 46, x + w - 18, y + 46], fill=STYLE.dim, width=1)
    if FX is not None:
        d = fxd()
        d.line([(x + 18, y + 45), (x + 18 + 120, y + 45)], fill=STYLE.accent + (140,), width=2)
        d.line([(x + 18, y + 47), (x + 18 + 120, y + 47)], fill=STYLE.accent + (70,), width=2)


def placeholder(draw, box, msg="暂无数据"):
    x, y, w, h = box
    draw.text((x + 22, y + 58), msg, font=font(22), fill=STYLE.muted)


# ---------------- 顶部 ----------------
def _header_deco(draw, box):
    x, y, w, h = box
    # 顶部细线
    draw.line([(x + 26, y + 8), (x + w - 26, y + 8)], fill=STYLE.dim, width=1)
    # 吉祥物 + 状态文字
    draw_mascot(draw, x + 40, y + 26, 15)
    draw.text((x + 66, y + 19), "ONLINE // 系统在线", font=font(15), fill=STYLE.muted)
    # 信号条 + 十六进制标 + 电池
    draw_signal(draw, x + 236, y + 18, STYLE.accent)
    hx = font_mono(14)
    draw.text((x + 288, y + 19), "0x0A1D", font=hx, fill=STYLE.dim)
    draw_battery(draw, x + 342, y + 16, level=72)
    draw_sparkle(draw, x + 396, y + 23, 4)
    # 右侧版本标
    label = "AiDash 驾驶舱"
    lf = font(17)
    draw.text((x + w - 24 - tw(draw, label, lf), y + 14), label, font=lf, fill=STYLE.dim)


def draw_header_portrait(draw, box, now):
    x, y, w, h = box
    panel(draw, box, radius=24)
    _header_deco(draw, box)

    t = now.strftime("%H:%M")
    tf = font_mono(88)
    tw_ = tw(draw, t, tf)
    tx = x + (w - tw_) / 2
    glow_text((tx, y + 22), t, tf, STYLE.accent2, 5)
    draw.text((tx, y + 22), t, font=tf, fill=STYLE.accent2)

    # 时间下装饰线
    cy = y + 122
    draw.line([(x + 150, cy), (tx - 24, cy)], fill=STYLE.dim, width=1)
    draw.line([(tx + tw_ + 24, cy), (x + w - 150, cy)], fill=STYLE.dim, width=1)
    draw.polygon([(x + w / 2 - 7, cy), (x + w / 2 + 7, cy), (x + w / 2, cy - 8)], outline=STYLE.accent, width=1)

    date_s = "%d年%d月%d日 %s" % (now.year, now.month, now.day, WEEK[now.weekday()])
    df = font(26)
    draw.text((x + (w - tw(draw, date_s, df)) / 2, y + 132), date_s, font=df, fill=STYLE.fg)

    hh = now.hour
    greet = (
        "夜深了，早点休息" if hh < 6 else
        "早上好，元气满满" if hh < 12 else
        "下午好，继续加油" if hh < 18 else
        "晚上好，放松一下"
    )
    gf = font(19)
    draw.text((x + (w - tw(draw, greet, gf)) / 2, y + 162), greet, font=gf, fill=STYLE.muted)


def draw_status_bar_landscape(draw, box, now):
    x, y, w, h = box
    panel(draw, box, radius=22)
    draw_mascot(draw, x + 36, y + 34, 16)
    t = now.strftime("%H:%M")
    tf = font_mono(54)
    glow_text((x + 70, y + 16), t, tf, STYLE.accent2, 4)
    draw.text((x + 70, y + 16), t, font=tf, fill=STYLE.accent2)

    date_s = "%d年%d月%d日 %s" % (now.year, now.month, now.day, WEEK[now.weekday()])
    df = font(25)
    draw.text((x + 280, y + 34), date_s, font=df, fill=STYLE.fg)
    draw_signal(draw, x + 540, y + 30, STYLE.accent)
    hx = font_mono(14)
    draw.text((x + 592, y + 32), "0x0A1D", font=hx, fill=STYLE.dim)
    draw_battery(draw, x + 650, y + 30, level=72)
    draw_mini_bars(draw, x + 720, y + 26, "CPU", 23, STYLE.purple)
    draw_mini_bars(draw, x + 720, y + 48, "MEM", 45, STYLE.pink)
    draw_radar(draw, x + w - 96, y + 44, 18)

    hh = now.hour
    greet = (
        "夜深了，早点休息" if hh < 6 else
        "早上好，元气满满" if hh < 12 else
        "下午好，继续加油" if hh < 18 else
        "晚上好，放松一下"
    )
    gf = font(21)
    draw.text((x + 940, y + 36), greet, font=gf, fill=STYLE.muted)
    label = "AiDash 驾驶舱"
    lf = font(17)
    draw.text((x + w - 26 - tw(draw, label, lf), y + 12), label, font=lf, fill=STYLE.dim)


# ---------------- 模块绘制 ----------------
def draw_weather(draw, box, weather):
    x, y, w, h = box
    title(draw, box, "天气")
    if not weather:
        placeholder(draw, box, "天气加载失败")
        return
    cy = y + PANEL_TITLE_H + 8
    cur = weather.get("cur", "")
    # Q 版天气图标（晴=太阳，其余=云朵，都带笑脸）
    if STYLE.bg != (255, 255, 255):
        if "晴" in cur:
            draw_sun(draw, x + 38, cy + 24, 18)
        else:
            draw_cloud(draw, x + 38, cy + 26, 20)
    # 把温度数字突出显示
    m = re.search(r"(-?\d+)°C", cur)
    if m:
        pre = cur[: m.start()]
        num = m.group(1) + "°"
        post = cur[m.end():].replace("°C", "")
        cf = font(32)
        nf2 = font_mono(38)
        pf = font(24)
        cx = x + 88
        draw.text((cx, cy + 6), pre, font=pf, fill=STYLE.fg)
        cx += tw(draw, pre, pf)
        glow_text((cx, cy), num + "C", nf2, STYLE.accent, 4)
        draw.text((cx, cy), num + "C", font=nf2, fill=STYLE.accent)
        cx += tw(draw, num + "C", nf2)
        draw.text((cx, cy + 6), post, font=pf, fill=STYLE.fg)
    else:
        draw.text((x + 88, cy), truncate(draw, cur, font(30), w - 108), font=font(30), fill=STYLE.accent)
    cy += 52
    sf = font(21)
    draw.text((x + 20, cy), truncate(draw, weather.get("sub", ""), sf, w - 40), font=sf, fill=STYLE.muted)
    cy += 30
    ff = font(20)
    for line in weather.get("fc", []):
        if cy + 30 > y + h - 4:
            break
        draw.text((x + 20, cy), truncate(draw, line, ff, w - 40), font=ff, fill=STYLE.fg)
        cy += 28


def draw_feeds(draw, box, cats):
    x, y, w, h = box
    title(draw, box, "资讯热榜")
    if not cats:
        placeholder(draw, box, "暂无资讯")
        return
    cy = y + PANEL_TITLE_H + 4
    cat_h = 30
    item_h = 27
    nf = font(20)
    for idx, (label, items) in enumerate(cats):
        if cy + cat_h + item_h > y + h - 6:
            break
        draw.rectangle([x + 18, cy + 5, x + 22, cy + 23], fill=STYLE.accent)
        draw.text((x + 30, cy), label, font=font(21), fill=STYLE.fg)
        draw.ellipse([x + w - 84, cy + 6, x + w - 76, cy + 14], fill=STYLE.accent2)
        draw.text((x + w - 68, cy + 3), "LIVE", font=font(13), fill=STYLE.accent2)
        cy += cat_h
        for k, it in enumerate(items):
            if cy + item_h > y + h - 6:
                break
            idxf = font_mono(14)
            draw.text((x + 26, cy + 2), "%02d" % (k + 1), font=idxf, fill=STYLE.dim)
            draw.text(
                (x + 52, cy),
                truncate(draw, it, nf, w - 72),
                font=nf,
                fill=STYLE.muted,
            )
            cy += item_h


def draw_countdown(draw, box, data):
    x, y, w, h = box
    title(draw, box, "倒计时")
    counts = data.get("countdowns") or []
    if not counts:
        placeholder(draw, box, "暂无倒计时")
        return
    row_h = 42
    content_h = h - PANEL_TITLE_H - 8
    rows = max(1, min(len(counts), int((content_h - 4) / row_h)))
    cy = y + PANEL_TITLE_H + list_start(content_h, rows, row_h)
    for c in counts[:rows]:
        name = str(c.get("name", ""))
        date = str(c.get("date", ""))
        d = days_until(date)
        if d is None:
            txt = "日期格式错误"
        elif d > 0:
            txt = "还有 %d 天" % d
        elif d == 0:
            txt = "就是今天！"
        else:
            txt = "已过 %d 天" % (-d)
        nf = font(22)
        name_line = truncate(draw, name, nf, w - 170)
        draw.text((x + 20, cy + 2), name_line, font=nf, fill=STYLE.fg)
        if d is None:
            draw.text((x + w - 24 - tw(draw, "N/A", font(18)), cy + 6), "N/A", font=font(18), fill=STYLE.muted)
            cy += row_h
            continue
        if d > 0:
            prefix, num, suffix = "T-", str(d), "DAYS"
        elif d == 0:
            prefix, num, suffix = "T-", "0", "TODAY"
        else:
            prefix, num, suffix = "T+", str(-d), "AGO"
        sf = font(12)
        draw.text((x + 20 + tw(draw, name_line, nf) + 8, cy + 6), suffix, font=sf, fill=STYLE.muted)
        mf = font_mono(16)
        block = prefix + num
        bx = x + w - 24 - tw(draw, block, mf)
        by = cy + 12
        cxr = bx + tw(draw, block, mf) / 2
        cyr = by + 8
        r = 19
        # 环形仪表 + 亮弧（270°）
        draw.arc([cxr - r, cyr - r, cxr + r, cyr + r], 0, 360, fill=STYLE.dim, width=3)
        if FX is not None:
            fxd().arc([cxr - r, cyr - r, cxr + r, cyr + r], -90, 180, fill=STYLE.accent2 + (160,), width=3)
        draw.arc([cxr - r, cyr - r, cxr + r, cyr + r], -90, 180, fill=STYLE.accent2, width=3)
        glow_text((bx, by), block, mf, STYLE.accent2, 2)
        draw.text((bx, by), block, font=mf, fill=STYLE.accent2)
        draw_sparkle(draw, cxr + r + 5, cyr - r + 2, 3, STYLE.pink)
        cy += row_h


def draw_todo(draw, box, data):
    x, y, w, h = box
    title(draw, box, "安排 / 待办")
    todos = data.get("todos") or []
    if not todos:
        placeholder(draw, box, "暂无待办")
        return
    pri_idx = {"高": 0, "中": 1, "低": 2}

    def sort_key(t):
        return (
            1 if t.get("done") else 0,
            pri_idx.get(t.get("priority"), 1),
            t.get("dueDate") or "9999-99-99",
        )

    todos = sorted(todos, key=sort_key)
    gauge_h = 64
    row_h = 48
    content_h = h - PANEL_TITLE_H - gauge_h
    rows = max(1, min(len(todos), int((content_h - 4) / row_h)))
    cy = y + PANEL_TITLE_H + list_start(content_h, rows, row_h)
    for t in todos[:rows]:
        done = bool(t.get("done"))
        text_s = str(t.get("text", ""))
        pri = str(t.get("priority") or "中")
        if pri not in pri_idx:
            pri = "中"
        if STYLE.bg != (255, 255, 255):
            draw.rounded_rectangle([x + 20, cy + 5, x + 37, cy + 22], radius=3, outline=STYLE.accent, width=2)
            if done:
                draw.line([x + 24, cy + 13, x + 28, cy + 18], fill=STYLE.accent2, width=2)
                draw.line([x + 28, cy + 18, x + 34, cy + 9], fill=STYLE.accent2, width=2)
        else:
            draw.rectangle([x + 20, cy + 5, x + 37, cy + 22], outline="black", width=2)
            if done:
                draw.line([x + 24, cy + 13, x + 28, cy + 18], fill="black", width=2)
                draw.line([x + 28, cy + 18, x + 34, cy + 9], fill="black", width=2)

        bx = x + 46
        lf = font(17)
        bw = int(tw(draw, pri, lf)) + 12
        if STYLE.bg != (255, 255, 255):
            if pri == "高":
                draw.rounded_rectangle([bx, cy + 2, bx + bw, cy + 25], radius=7, fill=STYLE.amber)
                draw.text((bx + 6, cy + 4), pri, font=lf, fill=(12, 20, 20))
            elif pri == "中":
                draw.rounded_rectangle([bx, cy + 2, bx + bw, cy + 25], radius=7, outline=STYLE.accent, width=1)
                draw.text((bx + 6, cy + 4), pri, font=lf, fill=STYLE.fg)
            else:
                draw.rounded_rectangle([bx, cy + 2, bx + bw, cy + 25], radius=7, outline=STYLE.dim, width=1)
                draw.text((bx + 6, cy + 4), pri, font=lf, fill=STYLE.muted)
        else:
            if pri == "高":
                draw.rounded_rectangle([bx, cy + 2, bx + bw, cy + 25], radius=6, fill="black")
                draw.text((bx + 6, cy + 4), pri, font=lf, fill="white")
            else:
                draw.rounded_rectangle([bx, cy + 2, bx + bw, cy + 25], radius=6, outline="black", width=1)
                draw.text((bx + 6, cy + 4), pri, font=lf, fill=(110, 110, 110) if pri == "低" else "black")

        tx = bx + bw + 8
        tf = font(22)
        color = STYLE.dim if done else STYLE.fg
        tline = truncate(draw, text_s, tf, w - 20 - (tx - x))
        draw.text((tx, cy + 1), tline, font=tf, fill=color)
        if done:
            wl = tw(draw, tline, tf)
            draw.line([tx, cy + 15, tx + wl, cy + 15], fill=STYLE.dim, width=2)
        due = t.get("dueDate") or ""
        if due:
            draw.text((tx, cy + 25), "截止 " + due, font=font(15), fill=STYLE.muted)
        cy += row_h

    # 电脑终端式加载进度线
    done_n = sum(1 for t in todos if t.get("done"))
    pct = int(round(done_n * 100 / len(todos)))
    gy = y + h - 50
    draw_loading_bar(draw, x + 20, gy, w - 40, pct, "TASKS LOADING // 任务加载")
    txt_stats = "%d/%d 完成 ｜ 优先级排序执行" % (done_n, len(todos))
    draw.text((x + 20, gy + 26), txt_stats, font=font(15), fill=STYLE.muted)
    # 笑脸随完成度变开心
    if STYLE.bg != (255, 255, 255):
        draw_kawaii_face(draw, x + 20 + tw(draw, txt_stats, font(15)) + 16, gy + 34, r=9, smile=pct / 100.0)


def draw_notes(draw, box, notes):
    x, y, w, h = box
    title(draw, box, "AI 笔记")
    if not notes:
        placeholder(draw, box, "暂无笔记")
        return
    row_h = 48
    content_h = h - PANEL_TITLE_H - 8
    rows = max(1, min(len(notes), int((content_h - 4) / row_h)))
    cy = y + PANEL_TITLE_H + list_start(content_h, rows, row_h)
    nf = font(21)
    tf = font(15)
    for idx, n in enumerate(notes[:rows]):
        if isinstance(n, dict):
            text_s = str(n.get("text", ""))
            tags = n.get("tags") or []
        else:
            text_s = str(n)
            tags = []
        line = truncate(draw, text_s, nf, w - 52)
        idxf = font_mono(14)
        draw.text((x + 22, cy + 2), "M%02d" % (idx + 1), font=idxf, fill=STYLE.dim)
        draw.text((x + 58, cy), line, font=nf, fill=STYLE.fg)
        if tags:
            tag_s = "#" + " #".join(str(t) for t in tags[:3])
            draw.text((x + 70, cy + 24), truncate(draw, tag_s, tf, w - 90), font=tf, fill=STYLE.muted)
        if idx == rows - 1:
            cxs = x + 58 + tw(draw, line, nf) + 4
            draw.rectangle([cxs, cy + 2, cxs + 8, cy + 20], fill=STYLE.accent)
        cy += row_h


def draw_quote(draw, box, quote):
    x, y, w, h = box
    title(draw, box, "每日一言")
    if not quote:
        quote = "博观而约取，厚积而薄发。"
    qf = font(25)
    lines = wrap_lines(draw, quote, qf, w - 80)
    line_h = 36
    total = len(lines) * line_h
    cy = y + (h - total) / 2 + 12
    for i, ln in enumerate(lines):
        lx = x + (w - tw(draw, ln, qf)) / 2
        glow_text((lx, cy), ln, qf, STYLE.accent, 4)
        draw.text((lx, cy), ln, font=qf, fill=STYLE.accent)
        cy += line_h
    # 打字光标
    if lines:
        last_w = tw(draw, lines[-1], qf)
        last_lx = x + (w - last_w) / 2
        draw.rectangle([last_lx + last_w + 8, cy - line_h + 6, last_lx + last_w + 17, cy - line_h + 24], fill=STYLE.accent)
    # 装饰引号
    qq = font(30)
    draw.text((x + 22, y + PANEL_TITLE_H + 6), "“", font=qq, fill=STYLE.dim)
    draw.text((x + w - 22 - tw(draw, "”", qq), y + h - 46), "”", font=qq, fill=STYLE.dim)
    draw_sparkle(draw, x + 36, y + PANEL_TITLE_H + 14, 4, STYLE.pink)
    draw_sparkle(draw, x + w - 36, y + h - 34, 4, STYLE.purple)


# ---------------- 数据获取 ----------------
def fetch_text(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AiDash/2.1",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", "ignore")


def fetch_json(url):
    return json.loads(fetch_text(url))


def load_remote(name, local):
    if local:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    base = get_cfg("RAW_BASE", "")
    return fetch_text(base.rstrip("/") + "/" + name)


def load_json(name, local):
    try:
        return json.loads(load_remote(name, local))
    except Exception:
        return {}


def load_text(name, local):
    try:
        return load_remote(name, local)
    except Exception:
        return ""


def wmo(code):
    table = {
        0: "晴", 1: "多云", 2: "阴", 3: "阴",
        45: "雾", 48: "雾",
        51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨",
        56: "冻雨", 57: "冻雨",
        61: "雨", 63: "雨", 65: "雨",
        66: "冻雨", 67: "冻雨",
        71: "雪", 73: "雪", 75: "雪", 77: "雪",
        80: "阵雨", 81: "阵雨", 82: "阵雨",
        85: "阵雪", 86: "阵雪",
    }
    if code in table:
        return table[code]
    if code is not None and code >= 95:
        return "雷雨"
    return "未知"


def fetch_weather(lat, lon, city):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=%s&longitude=%s"
        "&current_weather=true"
        "&hourly=relative_humidity_2m"
        "&daily=weathercode,temperature_2m_max,temperature_2m_min,"
        "precipitation_probability_max,sunrise,sunset"
        "&timezone=auto&forecast_days=5"
    ) % (urllib.parse.quote(str(lat)), urllib.parse.quote(str(lon)))
    try:
        d = fetch_json(url)
    except Exception:
        return None
    try:
        cw = d.get("current_weather") or {}
        temp = round(cw.get("temperature", 0))
        desc = wmo(cw.get("weathercode"))
        hum = "--"
        try:
            times = (d.get("hourly") or {}).get("time") or []
            harr = (d.get("hourly") or {}).get("relative_humidity_2m") or []
            prefix = datetime.now().strftime("%Y-%m-%dT%H:")
            for i, t in enumerate(times):
                if str(t).startswith(prefix):
                    hum = "%d%%" % harr[i]
                    break
        except Exception:
            pass
        wind = round(cw.get("windspeed", 0))
        sub = "湿度 %s ｜ 风速 %d km/h" % (hum, wind)
        fc = []
        dl = d.get("daily") or {}
        days = dl.get("time") or []
        names = ["今天", "明天", "后天"]
        wk = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
        n = min(5, len(days))
        for i in range(n):
            label = names[i] if i < 3 else wk[datetime.strptime(days[i], "%Y-%m-%d").weekday()]
            rain_arr = dl.get("precipitation_probability_max") or []
            rain = rain_arr[i] if i < len(rain_arr) and rain_arr[i] is not None else None
            rain_txt = (" 降水%d%%" % round(rain)) if rain is not None else ""
            line = "%s：%s %d~%d°C%s" % (
                label,
                wmo(dl["weathercode"][i]),
                round(dl["temperature_2m_min"][i]),
                round(dl["temperature_2m_max"][i]),
                rain_txt,
            )
            fc.append(line)
        sr = (dl.get("sunrise") or [""])[0]
        ss = (dl.get("sunset") or [""])[0]
        if sr and ss:
            fc.append("日出 %s ｜ 日落 %s" % (sr[11:16], ss[11:16]))
        return {"cur": "%s %s %d°C" % (city, desc, temp), "sub": sub, "fc": fc}
    except Exception:
        return None


def normalize_feeds(raw):
    cats = []
    order = [
        ("bili", "B站热搜"),
        ("zhihu", "知乎热榜"),
        ("weibo", "微博热搜"),
        ("ithome", "IT之家"),
        ("sspai", "少数派"),
    ]
    for key, label in order:
        items = raw.get(key)
        if isinstance(items, list):
            t = [str(i) for i in items if str(i).strip()][:4]
            if t:
                cats.append((label, t))
    ups = raw.get("ups")
    if isinstance(ups, list):
        for u in ups:
            if not isinstance(u, dict):
                continue
            name = str(u.get("name") or "")
            titles = [str(t) for t in (u.get("titles") or []) if str(t).strip()][:2]
            if name and titles:
                cats.append((name, titles))
    return cats[:4]


def parse_notes_from_md(md_text):
    notes = []
    m = re.search(r"##\s*笔记(.*?)(?:\n##\s|\Z)", md_text, re.S)
    if not m:
        return notes
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.startswith("- "):
            t = line[2:].strip()
            if t and t != "_暂无_":
                tags = re.findall(r"#([^\s#]+)", t)
                clean = re.sub(r"#([^\s#]+)", "", t).strip()
                notes.append({"text": clean or t, "tags": tags})
            if len(notes) >= 6:
                break
    return notes


def days_until(date_str):
    try:
        target = datetime.strptime(str(date_str), "%Y-%m-%d").date()
        return (target - datetime.now().date()).days
    except Exception:
        return None


def get_quotes():
    q = get_cfg("QUOTES", [])
    if isinstance(q, list) and q:
        return q
    return DEFAULT_QUOTES


def fetch_quote_online():
    """实时联网获取古风名言：一言（诗词/哲学）→ 今日诗词 → 失败返回 None"""
    try:
        d = fetch_json("https://v1.hitokoto.cn/?c=i&c=k")
        text = str(d.get("hitokoto") or "").strip()
        if text and len(text) <= 70:
            return text
    except Exception:
        pass
    try:
        d = fetch_json("https://v1.jinrishici.com/all.json")
        text = str(d.get("content") or "").strip()
        origin = str(d.get("origin") or "").strip()
        author = str(d.get("author") or "").strip()
        if text and len(text) <= 70:
            if origin:
                tail = ("——" + author + "《" + origin + "》") if author else ("——《" + origin + "》")
                text = text + tail
            return text
    except Exception:
        pass
    return None


def schedule_position(now, data):
    """当天第几次定时生成（0 起）：按 起始小时 + N×间隔小时 推算。
    默认起始 8 点、间隔 4 小时 → 位置 0~5（08/12/16/20/00/04）。"""
    settings = data.get("settings") or {}
    try:
        uh = max(1, int(settings.get("updateHours") or 4))
        ph = int(settings.get("pushHour") or 8)
    except Exception:
        uh, ph = 4, 8
    return ((now.hour - ph) % 24) // uh


def pick_quote(data, quotes, now, position=None):
    """每日顺序：前 customPerDay 次自定义（按库循环）→ 接着 builtinPerDay 次内置
    → 之后联网，联网失败用内置兜底；settings.quoteOverride 可立即指定某条。"""
    settings = data.get("settings") or {}
    override = settings.get("quoteOverride") or {}
    today = now.strftime("%Y-%m-%d")
    if str(override.get("date", "")) == today and str(override.get("text", "")).strip():
        return str(override["text"]).strip()

    custom = []
    if isinstance(data.get("customQuotes"), list):
        custom = [str(q).strip() for q in data["customQuotes"] if str(q).strip()]
    try:
        cpd = max(0, int(settings.get("customPerDay")) if settings.get("customPerDay") is not None else 2)
        bpd = max(0, int(settings.get("builtinPerDay")) if settings.get("builtinPerDay") is not None else 1)
    except Exception:
        cpd, bpd = 2, 1
    day = now.toordinal()
    if position is None:
        position = schedule_position(now, data)

    if custom and cpd > 0 and position < cpd:
        idx = (day * cpd + position) % len(custom)
        return custom[idx]
    if bpd > 0 and position < cpd + bpd:
        idx = (day * bpd + (position - cpd)) % len(quotes)
        return quotes[idx]

    online = fetch_quote_online()
    if online:
        return online
    return quotes[(day * bpd + position) % len(quotes)]


# ---------------- 布局 ----------------
def _draw_module(draw, name, box, data, feeds, weather, notes, quote):
    panel(draw, box)
    if name == "weather":
        draw_weather(draw, box, weather)
    elif name == "feeds":
        draw_feeds(draw, box, feeds)
    elif name == "countdown":
        draw_countdown(draw, box, data)
    elif name == "todo":
        draw_todo(draw, box, data)
    elif name == "notes":
        draw_notes(draw, box, notes)
    elif name == "quote":
        draw_quote(draw, box, quote)
    else:
        placeholder(draw, box, "未知模块：" + name)


def _span_box(margin, unit, gap, row_y, row_h, col, span):
    """12 列网格中的子面板盒：col=起始列，span=占列数"""
    x0 = margin + col * unit + col * gap
    w0 = span * unit + (span - 1) * gap
    return (int(x0), row_y, int(w0), row_h)


def _distinct(order, prefs, used):
    for p in prefs:
        if p in order and p not in used:
            return p
    for m in order:
        if m not in used:
            return m
    return prefs[0]


def _module_needed_h(name, data, feeds, notes):
    """按当前内容估算一个模块最少需要多高（px），实现“内容驱动高度”"""
    base = PANEL_TITLE_H + 14
    if name == "weather":
        return base + 170
    if name == "feeds":
        cats = feeds or []
        n = 0
        for label, items in cats[:4]:
            n += 30 + min(4, len(items)) * 27
        return base + max(86, n)
    if name == "countdown":
        cnt = len(data.get("countdowns") or [])
        return base + max(44, cnt * 44)
    if name == "todo":
        cnt = min(4, len(data.get("todos") or []))
        return base + max(96, cnt * 48) + 56
    if name == "notes":
        cnt = len(notes or [])
        return base + max(50, cnt * 52)
    if name == "quote":
        return base + 118
    return base + 120


def _distribute_heights(needs, rest, gaps, min_h=110, max_gap_extra=60):
    """混合自适应：内容少→面板保持内容高度、剩余空间变成均匀留白；
    内容多→按比例压缩（不低于 min_h）。"""
    total = sum(needs)
    if total <= rest:
        extra = rest - total
        gap_extra = min(max_gap_extra, int(extra * 0.5 / max(1, gaps)))
        left = extra - gap_extra * gaps
        top_extra = int(left * 0.5)
        return [int(n) for n in needs], top_extra, gap_extra
    scale = rest / float(total)
    hs = [max(min_h, int(round(n * scale))) for n in needs]
    diff = rest - sum(hs)
    if diff and hs:
        hs[-1] += diff
    return hs, 0, 0


def list_start(content_h, rows, row_h, pad=4):
    """面板内内容较少时垂直居中，让留白均匀"""
    used = rows * row_h + pad
    if content_h > used:
        return int((content_h - used) / 2)
    return pad


def build_portrait_dual(now, data, feeds, weather, notes, quote):
    """创意 bento 竖屏：宽窄混排 + 底部全宽名言"""
    global STYLE
    W = PRESETS["portrait_dual"]["w"]
    H = PRESETS["portrait_dual"]["h"]
    base, draw = begin_canvas(W, H, STYLE)
    margin = 16
    gap = 12
    layout = data.get("layout") or {}
    order = [m for m in (layout.get("order") or []) if m in KNOWN_MODULES]
    if not order:
        order = ["weather", "feeds", "countdown", "todo", "notes", "quote"]

    draw_header_portrait(draw, (margin, margin, W - 2 * margin, HEADER_H), now)
    y = margin + HEADER_H + 14
    inner_w = W - 2 * margin
    unit = (inner_w - 11 * gap) / 12.0
    used = []
    m1 = _distinct(order, ["weather"], used); used.append(m1)
    m2 = _distinct(order, ["todo", "countdown"], used); used.append(m2)
    m3 = _distinct(order, ["feeds"], used); used.append(m3)
    m4 = _distinct(order, ["countdown", "notes"], used); used.append(m4)
    m5 = _distinct(order, ["notes", "quote"], used); used.append(m5)
    m6 = _distinct(order, ["quote", "notes"], used); used.append(m6)

    bottom = 16
    rest = H - y - bottom - 2 * gap
    rows = [[m1, m2], [m3, m4, m5], [m6]]
    needs = []
    for r in rows:
        need = max(_module_needed_h(m, data, feeds, notes) for m in r)
        needs.append(min(max(need, 110), 640))
    row_hs, top_extra, gap_extra = _distribute_heights(needs, rest, len(rows) - 1)

    row1 = y + top_extra
    _draw_module(draw, m1, _span_box(margin, unit, gap, row1, row_hs[0], 0, 7), data, feeds, weather, notes, quote)
    _draw_module(draw, m2, _span_box(margin, unit, gap, row1, row_hs[0], 7, 5), data, feeds, weather, notes, quote)
    row2 = row1 + row_hs[0] + gap + gap_extra
    _draw_module(draw, m3, _span_box(margin, unit, gap, row2, row_hs[1], 0, 5), data, feeds, weather, notes, quote)
    _draw_module(draw, m4, _span_box(margin, unit, gap, row2, row_hs[1], 5, 3), data, feeds, weather, notes, quote)
    _draw_module(draw, m5, _span_box(margin, unit, gap, row2, row_hs[1], 8, 4), data, feeds, weather, notes, quote)
    row3 = row2 + row_hs[1] + gap + gap_extra
    _draw_module(draw, m6, _span_box(margin, unit, gap, row3, row_hs[2], 0, 12), data, feeds, weather, notes, quote)
    return finish_canvas()


def build_landscape(now, data, feeds, weather, notes, quote):
    """横屏 bento：上排两大块 + 下排四小格"""
    global STYLE
    W = PRESETS["landscape"]["w"]
    H = PRESETS["landscape"]["h"]
    base, draw = begin_canvas(W, H, STYLE)
    margin = 20
    gap = 14
    layout = data.get("layout") or {}
    order = [m for m in (layout.get("order") or []) if m in KNOWN_MODULES]
    if not order:
        order = ["weather", "feeds", "countdown", "todo", "notes", "quote"]
    inner_w = W - 2 * margin
    unit = (inner_w - 11 * gap) / 12.0

    status_h = 92
    draw_status_bar_landscape(draw, (margin, margin, inner_w, status_h), now)
    y = margin + status_h + gap
    used = []
    m1 = _distinct(order, ["weather"], used); used.append(m1)
    m2 = _distinct(order, ["todo", "feeds"], used); used.append(m2)
    m3 = _distinct(order, ["feeds", "notes"], used); used.append(m3)
    m4 = _distinct(order, ["countdown"], used); used.append(m4)
    m5 = _distinct(order, ["notes", "quote"], used); used.append(m5)
    m6 = _distinct(order, ["quote", "notes"], used); used.append(m6)

    bottom = 20
    rest = H - y - bottom - gap
    rows = [[m1, m2], [m3, m4, m5, m6]]
    needs = []
    for r in rows:
        need = max(_module_needed_h(m, data, feeds, notes) for m in r)
        needs.append(min(max(need, 120), 720))
    row_hs, top_extra, gap_extra = _distribute_heights(needs, rest, len(rows) - 1)
    top_h = row_hs[0]
    bottom_h = row_hs[1]

    _draw_module(draw, m1, _span_box(margin, unit, gap, y + top_extra, top_h, 0, 6), data, feeds, weather, notes, quote)
    _draw_module(draw, m2, _span_box(margin, unit, gap, y + top_extra, top_h, 6, 6), data, feeds, weather, notes, quote)
    row2 = y + top_extra + top_h + gap + gap_extra
    _draw_module(draw, m3, _span_box(margin, unit, gap, row2, bottom_h, 0, 4), data, feeds, weather, notes, quote)
    _draw_module(draw, m4, _span_box(margin, unit, gap, row2, bottom_h, 4, 3), data, feeds, weather, notes, quote)
    _draw_module(draw, m5, _span_box(margin, unit, gap, row2, bottom_h, 7, 3), data, feeds, weather, notes, quote)
    _draw_module(draw, m6, _span_box(margin, unit, gap, row2, bottom_h, 10, 2), data, feeds, weather, notes, quote)
    return finish_canvas()


def build_classic(now, data, feeds, weather, notes, quote):
    global STYLE
    W = PRESETS["classic"]["w"]
    H = PRESETS["classic"]["h"]
    base, draw = begin_canvas(W, H, STYLE)
    layout = data.get("layout") or {}
    order = [m for m in (layout.get("order") or []) if m in KNOWN_MODULES]
    if not order:
        order = ["weather", "feeds", "countdown", "todo", "notes", "quote"]
    heights = layout.get("heights") or {}
    draw_header_portrait(draw, (MARGIN, MARGIN, W - 2 * MARGIN, HEADER_H), now)
    y = MARGIN + HEADER_H + 12
    remaining = H - y - 16 - GAP * (len(order) - 1)
    total_w = sum(max(40, int(heights.get(m, 160))) for m in order)
    scale = remaining / float(total_w) if total_w else 1.0
    for m in order:
        ph = max(40, int(round(int(heights.get(m, 160)) * scale)))
        _draw_module(draw, m, (MARGIN, y, W - 2 * MARGIN, ph), data, feeds, weather, notes, quote)
        y += ph + GAP
    return finish_canvas()


def build(now, data, feeds, weather, notes, quote, preset):
    global STYLE
    if preset == "landscape":
        STYLE = make_style("sci")
        return build_landscape(now, data, feeds, weather, notes, quote)
    if preset == "classic":
        STYLE = make_style("classic")
        return build_classic(now, data, feeds, weather, notes, quote)
    STYLE = make_style("sci")
    return build_portrait_dual(now, data, feeds, weather, notes, quote)


# ---------------- 主流程 ----------------
def main():
    ap = argparse.ArgumentParser(description="生成 AiDash 每日仪表盘图片（v2.1）")
    ap.add_argument("--local", action="store_true", help="读取脚本同目录的本地数据文件（测试用）")
    ap.add_argument("--out", default=None, help="输出文件路径")
    ap.add_argument("--preset", default=None, choices=list(PRESETS.keys()), help="强制指定版式")
    args = ap.parse_args()

    now = datetime.now()
    data = load_json("data.json", args.local)
    md_text = load_text("data.md", args.local)
    feeds_raw = load_json("feeds.json", args.local)

    settings = data.get("settings") or {}
    city = str(settings.get("city") or get_cfg("CITY", "温州"))
    lat = str(settings.get("lat") or get_cfg("LAT", "27.99"))
    lon = str(settings.get("lon") or get_cfg("LON", "120.70"))
    preset = args.preset or str(settings.get("layoutPreset") or DEFAULT_PRESET)
    if preset not in PRESETS:
        preset = DEFAULT_PRESET

    weather = None
    if args.local:
        weather = load_json("weather.json", True) or None
    if not weather:
        try:
            weather = fetch_weather(lat, lon, city)
        except Exception:
            weather = None

    notes = data.get("notes") or []
    if not notes:
        notes = parse_notes_from_md(md_text)
    feeds = normalize_feeds(feeds_raw)
    quotes = get_quotes()
    quote = pick_quote(data, quotes, now)

    img = build(now, data, feeds, weather, notes, quote, preset)
    p = PRESETS[preset]
    out = args.out or get_cfg("OUT_IMAGE", "dashboard_%s.png" % preset)
    img.save(out)
    print("已生成 %s（%dx%d，版式：%s）" % (out, p["w"], p["h"], p["label"]))


if __name__ == "__main__":
    main()
