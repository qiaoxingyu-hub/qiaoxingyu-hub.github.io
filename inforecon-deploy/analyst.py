"""InfoRecon 分析引擎 - 调用 DeepSeek API 进行结构化预测"""
import json, os, sys, re
sys.path.insert(0, os.path.dirname(__file__))

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

import config

# ── 提示词模板 ──

STOCK_PROMPT = """当前日期：2026年06月17日

你是一位专业的A股分析师，请对以下预测请求进行深度分析。

【预测标的】{target}
【预测方向】{direction}
【时间框架】{timeframe}
【类别】股票分析

请使用联网搜索功能，按以下框架搜索最新信息并分析。

## 第1层：宏观环境
（列出2-3条当前对A股最重要的宏观因素，每条配一句影响分析，每条约30字）
- 因素1：[一句话] → 影响
- 因素2：[一句话] → 影响

## 第2层：行业/板块
（列出2-3条{target}所属行业的最新动态，每条配一句影响分析）
- 动态1：[一句话] → 影响
- 动态2：[一句话] → 影响

## 第3层：个股信息
（列出2-3条{target}自身的最新情况）
- 信息1：[一句话]
- 信息2：[一句话]

## 最终输出
- 方向判断：[{direction} / 反向 / 不确定]
- 信心指数：[1-10]
- 核心逻辑：30字以内
- 关键风险点：1个
- 目标价位区间：
"""

GENERAL_PROMPT = """你是一位专业的分析师，请对以下预测请求进行深度分析。

【预测主题】{target}
【预测方向】{direction}
【时间框架】{timeframe}
【类别】{category}

请使用联网搜索功能，按以下框架搜索最新信息并分析。

## 关键信息
（列出3-5条最相关的最新动态，每条配一句影响分析）
- [一句话] → 影响

## 最终输出
- 方向判断：[{direction} / 反向 / 不确定]
- 信心指数：[1-10]
- 核心逻辑：30字以内
- 关键不确定因素：
"""


def analyze(target, direction="上涨", timeframe="2周", category="stock"):
    """调用 DeepSeek API 进行分析，返回结构化结果"""
    if not config.DEEPSEEK_API_KEY:
        return {"error": "未配置DeepSeek API Key", "detail": "请在config.py中填写或设置环境变量 DEEPSEEK_API_KEY"}

    if OpenAI is None:
        return {"error": "缺少依赖", "detail": "请安装: pip install openai"}

    prompt_template = STOCK_PROMPT if category == "stock" else GENERAL_PROMPT
    prompt = prompt_template.format(target=target, direction=direction, timeframe=timeframe, category=category)

    client = OpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_BASE_URL)

    try:
        resp = client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": "你是 InfoRecon AI 分析师。请使用联网搜索获取最新信息，严格按照格式回复。不要用markdown格式，用纯文本。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        content = resp.choices[0].message.content.strip()
        result = parse_response(content, direction)
        result["raw"] = content
        return result

    except Exception as e:
        return {"error": f"API调用失败: {str(e)}", "detail": str(e)}


def parse_response(content, default_direction):
    """从 DeepSeek 回复中提取结构化字段"""
    result = {"direction": "unknown", "confidence": 5, "logic": "", "risk": "", "sections": {}}

    lines = content.split("\n")
    current_section = None
    section_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("## "):
            if current_section and section_lines:
                result["sections"][current_section] = section_lines
            current_section = line.lstrip("# ").strip()
            section_lines = []
        elif current_section:
            section_lines.append(line)

    if current_section and section_lines:
        result["sections"][current_section] = section_lines

    # Extract structured fields
    for line in lines:
        if "目标价位" in line:
            import re as re2
            nums = re2.findall(r"\d+\.?\d*", line)
            if len(nums) >= 2:
                result["target_price"] = f"{nums[0]}-{nums[1]}"

        if "方向判断" in line:
            for d in ["上涨", "下跌", "涨", "跌", "横盘"]:
                if d in line:
                    result["direction"] = d
                    break
        if "信心指数" in line:
            nums = re.findall(r"\d+", line)
            if nums:
                result["confidence"] = min(int(nums[0]), 10)
        if "核心逻辑" in line:
            seg = line.split("：")[-1] if "：" in line else line.split(":")[-1] if ":" in line else ""
            result["logic"] = seg.strip()
        if "关键风险" in line or "不确定" in line:
            seg = line.split("：")[-1] if "：" in line else line.split(":")[-1] if ":" in line else ""
            result["risk"] = seg.strip()

    return result


if __name__ == "__main__":
    r = analyze("三安光电（600703）", "上涨", "1周")
    print(json.dumps(r, ensure_ascii=False, indent=2))
