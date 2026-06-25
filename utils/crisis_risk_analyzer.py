"""危机分析引擎 —— 基于 crisis-response Skill 的规则诊断。"""

from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from utils.path import get_project_root


@dataclass
class CrisisAnalysisResult:
    event_text: str
    crisis_type: str
    crisis_level: str
    alert_color: str
    alert_label: str
    crisis_score: float
    dimension_scores: Dict[str, float]
    response_level: str
    first_response_sla: str
    followup_sla: str
    primary_path: str
    secondary_paths: List[str]
    strategy_reason: str
    key_risks: List[str]
    action_checklist: List[str]
    holding_statement_hint: str
    casualties: Dict[str, int] = field(default_factory=dict)
    escalation_notes: List[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "meta": {"generated_at": self.generated_at, "skill_version": "v1.0", "engine": "rule_based"},
            "input": {"event": self.event_text},
            "diagnosis": {
                "crisis_type": self.crisis_type,
                "crisis_level": self.crisis_level,
                "alert_color": self.alert_color,
                "alert_label": self.alert_label,
                "crisis_score": self.crisis_score,
                "dimension_scores": self.dimension_scores,
                "casualties": self.casualties,
                "escalation_notes": self.escalation_notes,
                "response_level": self.response_level,
            },
            "strategy": {
                "primary_path": self.primary_path,
                "secondary_paths": self.secondary_paths,
                "reason": self.strategy_reason,
            },
            "response_plan": {
                "first_response_sla": self.first_response_sla,
                "followup_sla": self.followup_sla,
                "action_checklist": self.action_checklist,
                "key_risks": self.key_risks,
            },
            "outputs_hint": {"holding_statement": self.holding_statement_hint},
        }


_SEVERITY_KEYWORDS: List[Tuple[str, int]] = [
    (r"死亡|遇难|丧生|身亡|罹难", 35),
    (r"伤亡|受伤|送医|重伤|轻伤", 22),
    (r"爆炸|起火|火灾|泄漏|有毒|瓦斯", 30),
    (r"矿难|透水|坍塌|溃坝|触电|坠井", 28),
    (r"追尾|脱轨|重大事故|特大事故|特别重大", 30),
    (r"大面积晚点|停运|滞留|被困|旅客滞留", 18),
    (r"设备故障|信号故障", 12),
    (r"数据泄露|信息泄露|暗网|黑客", 22),
    (r"造假|欺诈|违规", 18),
]

_SPREAD_KEYWORDS: List[Tuple[str, int]] = [
    (r"热搜第一|热搜榜|全网|刷屏|上热搜", 32),
    (r"抖音|微博|小红书|B站|短视频|视频发酵", 18),
    (r"500%|声量|传播|发酵|舆论", 18),
    (r"媒体曝光|央视|新华社|通报|全国关注", 22),
    (r"\d{3,}名|\d{3,}人|万名|千人", 15),
    (r"17年|最大|史上|罕见|震动|瞩目", 20),
    (r"矿难|安全生产|监管|问责", 15),
]

_EMOTION_KEYWORDS: List[Tuple[str, int]] = [
    (r"愤怒|骂|抵制|声讨|群情激愤|嘲讽", 26),
    (r"道歉|失言|歧视|冒犯|不当言论", 18),
    (r"质疑|不信任|公信力|透明度|隐瞒|反复变化", 26),
    (r"负面情感|情感指数.*[6-9]\d%|[6-9]\d%.*情感", 22),
    (r"失联|家属|悲痛|致哀|哀悼", 20),
]

_URGENCY_KEYWORDS: List[Tuple[str, int]] = [
    (r"18:00|18点|限时|立即|紧急|马上", 26),
    (r"省里|部委|国务院|监管|约谈|省政府|调查组", 24),
    (r"控制措施|依法|停产|整顿|问责|立案", 20),
    (r"发布会|通报会|口径|开发布会", 14),
    (r"2小时|两小时|黄金时间|30分钟|15分钟", 18),
]

_CRISIS_TYPE_RULES: List[Tuple[str, List[str], str]] = [
    ("安全事故", [r"事故|故障|晚点|停运|追尾|脱轨|爆炸|伤亡|火灾|泄漏"], "告知"),
    ("数据泄露", [r"泄露|数据|隐私|暗网|黑客|个人信息"], "告知"),
    ("产品问题", [r"质量|卫生|造假|缺陷|召回|食品安全"], "转换"),
    ("舆论争议", [r"热搜|失言|直播|骂|争议|网友|艺人|明星"], "顺应"),
    ("服务纠纷", [r"投诉|纠纷|服务|态度|退款|维权"], "顺应"),
    ("自然灾害", [r"地震|洪水|台风|暴雨|灾害|救援"], "告知"),
]

_PATH_COMBOS: Dict[str, Tuple[str, List[str], str]] = {
    "事实未明型": ("告知", ["疏导"], "事实尚未完全明朗，先沟通已知信息与不确定性，再引领议题"),
    "群死群伤型": ("告知", ["顺应", "疏导"], "重大伤亡须态度话语优先：致哀、致歉、承诺调查，再通报可核实事实"),
    "责任明确型": ("转换", ["顺应"], "责任边界较清晰，需补偿受损方并真诚致歉"),
    "情绪高涨型": ("顺应", ["疏导"], "公众情绪主导，先倾听共情再疏导理性讨论"),
    "内部混乱型": ("引领", ["告知"], "需先统一内部口径，再对外发布"),
    "默认": ("告知", ["疏导"], "综合告知事实并适度引领舆论"),
}

_LEVEL_TABLE: List[Tuple[float, str, str, str, str, str, str]] = [
    # (min_score, level, color, label, response_level, first_sla, followup_sla)
    (80, "Ⅳ级", "red", "红色预警", "集团总部 + 政府联动应急机制", "15分钟内", "每小时更新一次"),
    (60, "Ⅲ级", "orange", "橙色预警", "国铁集团公关部 / 企业总部公关", "30分钟内", "2小时内跟进通报"),
    (40, "Ⅱ级", "yellow", "黄色预警", "局级 / 事业部公关负责人", "2小时内", "6小时内发布进展"),
    (0, "Ⅰ级", "blue", "蓝色预警", "站段 / 部门公关接口人", "4小时内", "24小时内例行更新"),
]


def _score_keywords(text: str, rules: List[Tuple[str, int]], cap: float = 100) -> float:
    score = 0.0
    for pattern, weight in rules:
        if re.search(pattern, text, re.IGNORECASE):
            score += weight
    return min(score, cap)


def _detect_crisis_type(text: str) -> str:
    for ctype, patterns, _ in _CRISIS_TYPE_RULES:
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                return ctype
    return "舆论争议"


def _detect_scenario_mode(text: str, crisis_type: str, casualties: Optional[Dict[str, int]] = None) -> str:
    casualties = casualties or {}
    deaths = casualties.get("deaths", 0)

    if deaths >= 10 or (deaths >= 3 and crisis_type == "安全事故"):
        return "群死群伤型"
    if re.search(r"调查中|原因不明|待核实|尚未|进一步核实", text) and deaths < 3:
        return "事实未明型"
    if re.search(r"愤怒|骂|热搜|抵制|声讨|失言|质疑|公信", text):
        return "情绪高涨型"
    if re.search(r"口径|内部|统一说法|员工", text):
        return "内部混乱型"
    if re.search(r"责任|赔偿|补偿|道歉|违规|承认", text) or crisis_type in {"产品问题", "服务纠纷"}:
        return "责任明确型"
    return "默认"


def _extract_numbers(text: str) -> List[int]:
    nums: List[int] = []
    for m in re.finditer(r"(\d+)", text):
        try:
            nums.append(int(m.group(1)))
        except ValueError:
            pass
    return nums


def _extract_casualties(text: str) -> Dict[str, int]:
    """从事件描述中提取伤亡结构化数据。"""
    deaths = 0
    injuries = 0
    missing = 0
    affected = 0

    death_patterns = [
        r"(\d+)\s*人?\s*(?:死亡|遇难|丧生|身亡|罹难)",
        r"(?:造成|已有|累计|至少)\s*(\d+)\s*人?\s*(?:死亡|遇难|丧生)",
        r"(?:死亡|遇难|丧生|身亡|罹难)[^\d]{0,10}(\d+)\s*人",
    ]
    injury_patterns = [
        r"(\d+)\s*人?\s*(?:受伤|伤员|送医|重伤|轻伤)",
        r"(?:造成|已有)\s*(\d+)\s*人?\s*受伤",
    ]
    missing_patterns = [
        r"(\d+)\s*人?\s*(?:失联|失踪|下落不明)",
    ]

    for pat in death_patterns:
        for m in re.finditer(pat, text):
            deaths = max(deaths, int(m.group(1)))
    for pat in injury_patterns:
        for m in re.finditer(pat, text):
            injuries = max(injuries, int(m.group(1)))
    for pat in missing_patterns:
        for m in re.finditer(pat, text):
            missing = max(missing, int(m.group(1)))

    for m in re.finditer(r"(?:井下|现场|车内|机上|共)\s*(?:作业|涉及|滞留)?\s*(\d+)\s*人", text):
        affected = max(affected, int(m.group(1)))

    return {"deaths": deaths, "injuries": injuries, "missing": missing, "affected": affected}


def _boost_dimensions_from_casualties(
    severity: float,
    spread: float,
    emotion: float,
    urgency: float,
    casualties: Dict[str, int],
    text: str,
) -> Tuple[float, float, float, float]:
    """按伤亡量级与事件特征加权各维度（对齐课件「态度话语优先」与案例库）。"""
    deaths = casualties["deaths"]
    injuries = casualties["injuries"]
    missing = casualties["missing"]
    total_harm = deaths + missing

    if deaths >= 50:
        severity = min(100, severity + 30)
        spread = min(100, spread + 25)
        emotion = min(100, emotion + 20)
        urgency = min(100, urgency + 25)
    elif deaths >= 30:
        severity = min(100, severity + 22)
        spread = min(100, spread + 18)
        emotion = min(100, emotion + 15)
        urgency = min(100, urgency + 18)
    elif deaths >= 10:
        severity = min(100, severity + 15)
        spread = min(100, spread + 12)
        emotion = min(100, emotion + 10)
        urgency = min(100, urgency + 12)
    elif deaths >= 3 or total_harm >= 5:
        severity = min(100, severity + 10)
        urgency = min(100, urgency + 8)

    if injuries >= 50:
        severity = min(100, severity + 12)
        spread = min(100, spread + 10)
    elif injuries >= 20:
        severity = min(100, severity + 8)

    if re.search(r"特别重大|特大事故|重大矿难|最大.*矿难|17年", text):
        spread = min(100, spread + 15)
        urgency = min(100, urgency + 12)

    if re.search(r"质疑|公信力|反复|变化|不透明|隐瞒", text):
        emotion = min(100, emotion + 18)
        spread = min(100, spread + 10)

    if re.search(r"控制措施|调查组|国务院|省里|监管|约谈|依法", text):
        urgency = min(100, urgency + 15)

    return severity, spread, emotion, urgency


def _apply_casualty_level_floor(
    crisis_score: float,
    casualties: Dict[str, int],
    text: str,
) -> Tuple[float, List[str]]:
    """
    伤亡量级分级下限（参照《生产安全事故报告和调查处理条例》及 crisis-response Ⅳ级标准）。

    特别重大（30人及以上死亡）→ 强制Ⅳ级红色；
    重大（10-29人死亡）→ 至少接近Ⅳ级；
    较大（3-9人死亡）→ 至少Ⅲ级。
    """
    deaths = casualties["deaths"]
    injuries = casualties["injuries"]
    missing = casualties["missing"]
    notes: List[str] = []
    floor = crisis_score

    is_catastrophic = bool(re.search(r"特别重大|特大事故|最大.*矿难|17年.*最大", text))

    if deaths >= 30 or (deaths >= 20 and is_catastrophic):
        floor = max(floor, 88.0)
        notes.append(
            f"特别重大事故（{deaths}人死亡、{missing}人失联）："
            "强制启动Ⅳ级红色预警，15分钟内首次表态，每小时跟进通报"
        )
    elif deaths >= 10:
        floor = max(floor, 82.0)
        notes.append(
            f"重大事故（{deaths}人死亡）：升级至Ⅳ级红色预警，启动集团总部+政府联动机制"
        )
    elif deaths >= 3 or (deaths >= 1 and injuries >= 10):
        floor = max(floor, 68.0)
        notes.append(f"较大伤亡事件（死亡{deaths}人、受伤{injuries}人）：至少Ⅲ级橙色预警")
    elif injuries >= 20:
        floor = max(floor, 62.0)
        notes.append(f"批量受伤事件（{injuries}人受伤）：维持Ⅲ级橙色预警并准备升级")

    return round(floor, 1), notes


def _build_key_risks(text: str, crisis_type: str, level: str, casualties: Optional[Dict[str, int]] = None) -> List[str]:
    casualties = casualties or {}
    deaths = casualties.get("deaths", 0)
    risks: List[str] = []

    if deaths >= 10:
        risks.append("重大人员伤亡：必须态度话语优先（致哀、致歉），再通报可核实事实")
    if deaths >= 30:
        risks.append("特别重大事故：须指定唯一新闻发言人，避免口径前后矛盾（参考王勇平案例）")
    if re.search(r"质疑|变化|不透明|公信力", text):
        risks.append("伤亡数据多次变化将加剧信任危机，须标注数据来源与核实状态")
    if re.search(r"调查中|原因不明|待核实", text):
        risks.append("事实未明时过早下定论，可能引发二次舆情")
    if re.search(r"个别|临时工|外包", text):
        risks.append("存在推卸责任表述风险（一票否决项）")
    if re.search(r"热搜|抖音|微博", text):
        risks.append("社交媒体传播速度快，需成为第一信源")
    if crisis_type == "安全事故" and (deaths > 0 or "伤亡" in text):
        risks.append("涉及人员伤亡，态度话语必须优先于事实细节")
    if level in {"Ⅲ级", "Ⅳ级"}:
        risks.append("高等级事件需指定唯一新闻发言人，避免多头发声")
    if not risks:
        risks.append("持续监测声量变化，准备升级响应级别")
    return risks


def _build_action_checklist(level: str, primary: str, secondary: List[str]) -> List[str]:
    actions = [
        f"启动「{primary}」主路径 +「{'+'.join(secondary)}」辅助路径",
        "准备初始声明（区分已知事实与调查中事项）",
        "同步内部口径，禁止一线人员擅自接受采访",
    ]
    if level in {"Ⅲ级", "Ⅳ级"}:
        actions.insert(0, "立即成立应急公关小组，指定新闻发言人")
        actions.append("准备媒体 Q&A（至少覆盖5个核心问题）")
    if level == "Ⅳ级":
        actions.append("启动与监管部门/政府部门的联动通报机制")
    else:
        actions.append("评估是否需要召开新闻发布会")
    return actions


def _build_holding_hint(text: str, crisis_type: str, casualties: Optional[Dict[str, int]] = None) -> str:
    casualties = casualties or {}
    deaths = casualties.get("deaths", 0)
    injuries = casualties.get("injuries", 0)
    missing = casualties.get("missing", 0)
    snippet = text.strip()[:80] + ("..." if len(text) > 80 else "")

    if deaths >= 3 and crisis_type == "安全事故":
        casualty_line = f"截至目前，已造成{deaths}人遇难"
        if missing:
            casualty_line += f"、{missing}人失联"
        if injuries:
            casualty_line += f"、{injuries}人受伤"
        casualty_line += "。我们对遇难者表示沉痛哀悼，向受伤人员及家属致以诚挚慰问。"
        return (
            f"【关于相关安全事故的紧急声明】\n"
            f"近日，{snippet}\n"
            f"我司/我局已第一时间启动应急预案，相关负责同志已赶赴现场处置。\n"
            f"{casualty_line}\n"
            f"详细原因正在进一步调查中，我们将依法依规及时公布进展。\n"
            f"策略提示：重大伤亡须覆盖价值层（致哀/致歉/慰问）优先于事实细节。"
        )

    return (
        f"【关于相关事件的初始声明】\n"
        f"近日，{snippet} 我司/我局已第一时间启动应急预案。\n"
        f"目前掌握的情况仍在核实中，我们将持续公布调查进展。\n"
        f"策略提示：{crisis_type}类事件应覆盖事实层（已知信息）与价值层（致歉/共情/承诺）。"
    )


def _resolve_level(crisis_score: float) -> Tuple[str, str, str, str, str, str]:
    for row in _LEVEL_TABLE:
        min_score, level, color, label, resp_level, first_sla, followup = row
        if crisis_score >= min_score:
            return level, color, label, resp_level, first_sla, followup
    last = _LEVEL_TABLE[-1]
    return last[1], last[2], last[3], last[4], last[5], last[6]


def analyze_crisis_event(event_text: str) -> CrisisAnalysisResult:
    """对事件描述进行危机分级与策略诊断。"""
    text = (event_text or "").strip()
    if not text:
        raise ValueError("事件描述不能为空")

    casualties = _extract_casualties(text)

    severity = _score_keywords(text, _SEVERITY_KEYWORDS)
    spread = _score_keywords(text, _SPREAD_KEYWORDS)
    emotion = _score_keywords(text, _EMOTION_KEYWORDS)
    urgency = _score_keywords(text, _URGENCY_KEYWORDS)

    nums = _extract_numbers(text)
    if any(n >= 500 for n in nums):
        spread = min(100, spread + 18)
    if any(n >= 100 for n in nums) and re.search(r"旅客|人|滞留|受影响", text):
        spread = min(100, spread + 10)
    if any(n >= 60 for n in nums) and re.search(r"%|情感|负面", text):
        emotion = min(100, emotion + 15)

    severity, spread, emotion, urgency = _boost_dimensions_from_casualties(
        severity, spread, emotion, urgency, casualties, text
    )

    crisis_score = round(severity * 0.38 + spread * 0.27 + emotion * 0.22 + urgency * 0.13, 1)
    crisis_score, escalation_notes = _apply_casualty_level_floor(crisis_score, casualties, text)

    crisis_type = _detect_crisis_type(text)
    scenario = _detect_scenario_mode(text, crisis_type, casualties)

    primary, secondary, reason = _PATH_COMBOS.get(scenario, _PATH_COMBOS["默认"])
    level, color, label, resp_level, first_sla, followup = _resolve_level(crisis_score)
    key_risks = _build_key_risks(text, crisis_type, level, casualties)
    if escalation_notes:
        key_risks = escalation_notes + key_risks
    checklist = _build_action_checklist(level, primary, secondary)
    holding_hint = _build_holding_hint(text, crisis_type, casualties)

    return CrisisAnalysisResult(
        event_text=text,
        crisis_type=crisis_type,
        crisis_level=level,
        alert_color=color,
        alert_label=label,
        crisis_score=crisis_score,
        dimension_scores={
            "severity": round(severity, 1),
            "spread": round(spread, 1),
            "emotion": round(emotion, 1),
            "urgency": round(urgency, 1),
        },
        response_level=resp_level,
        first_response_sla=first_sla,
        followup_sla=followup,
        primary_path=primary,
        secondary_paths=secondary,
        strategy_reason=reason,
        key_risks=key_risks,
        action_checklist=checklist,
        holding_statement_hint=holding_hint,
        casualties=casualties,
        escalation_notes=escalation_notes,
    )


def load_statement_scorer():
    """动态加载 crisis-response-toolkit 评分脚本。"""
    script_path = get_project_root() / "skills" / "crisis-response-toolkit" / "scripts" / "score_response.py"
    if not script_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("score_response", script_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.StatementScorer()


def score_holding_statement(text: str, crisis_type: str) -> Optional[Dict[str, Any]]:
    """对声明草稿进行质量评分。"""
    scorer = load_statement_scorer()
    if scorer is None:
        return None
    type_map = {
        "安全事故": "安全事故",
        "舆论争议": "舆论争议",
        "服务纠纷": "服务纠纷",
        "产品问题": "产品问题",
        "数据泄露": "安全事故",
        "自然灾害": "安全事故",
    }
    mapped = type_map.get(crisis_type, "舆论争议")
    return scorer.analyze(text, mapped)
