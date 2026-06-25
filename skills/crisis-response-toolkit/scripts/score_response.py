#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
危机声明质量评分脚本 —— score_response.py
基于课件《第十讲：危机传播管理》的"事实-价值"模型
兼容 PRClaw Agent 架构，可被 skill 调用
"""

import re
from typing import Dict, List, Tuple


class StatementScorer:
    """
    危机声明评分器

    评分维度：
    - 事实层（40%）：真相查证 + 利益互惠
    - 价值层（40%）：态度表态 + 情感共情 + 信任重建
    - 路径适配（20%）：策略是否符合危机类型

    一票否决项：
    - 推卸责任（"个别员工""临时工"）
    - 被动语态逃避主语
    - 出现"无可奉告"
    - 承诺整改但无时间节点
    """

    def __init__(self):
        self.WEIGHTS = {
            "facts": 0.40,
            "values": 0.40,
            "path": 0.20,
        }

        self.VETO_KEYWORDS = [
            "个别员工", "个别人员", "临时工", "外包人员",
            "无可奉告", "不便透露", "不便回应",
        ]

        self.FACTS_KEYWORDS = {
            "specific_fact": [
                "经调查", "经核实", "已查明", "确认", "证实",
                "根据", "数据显示", "统计", "记录",
            ],
            "distinguish": [
                "正在调查", "进一步核实", "待确认", "待核实",
                "目前掌握", "已知", "尚不", "暂时无法",
            ],
            "remedy": [
                "补偿", "赔偿", "整改", "处理", "处置",
                "措施", "方案", "改善", "优化",
                "已启动", "已实施", "正在推进",
            ],
        }

        self.VALUES_KEYWORDS = {
            "attitude": [
                "道歉", "致歉", "对不起", "歉意", "抱歉",
                "对不起大家", "诚恳", "痛心",
            ],
            "empathy": [
                "理解", "担忧", "不安", "困扰", "伤害",
                "感同身受", "心痛", "重视", "关切",
            ],
            "trust": [
                "承诺", "保证", "确保", "将", "计划",
                "时间节点", "限时", "限期",
            ],
        }

        self.PATH_RULES = {
            "安全事故": {"primary": "告知", "secondary": ["疏导"], "keyword": "调查"},
            "服务纠纷": {"primary": "顺应", "secondary": ["疏导"], "keyword": "道歉"},
            "舆论争议": {"primary": "顺应", "secondary": ["疏导"], "keyword": "理解"},
            "产品问题": {"primary": "转换", "secondary": ["顺应"], "keyword": "补偿"},
            "自然灾害": {"primary": "告知", "secondary": ["引领"], "keyword": "救援"},
        }

    def check_veto(self, text: str) -> Tuple[bool, str]:
        for keyword in self.VETO_KEYWORDS:
            if keyword in text:
                return True, f"出现禁用词: '{keyword}'"

        passive_patterns = [
            r"被.*发生", r"被.*导致", r"被.*出现",
            r"错误被", r"问题被", r"事故被",
        ]
        for pattern in passive_patterns:
            if re.search(pattern, text):
                return True, f"使用被动语态逃避主语: '{pattern}'"

        if "将" in text and not re.search(r"将.*[0-9]{4}|将.*月底|将.*日内|将.*前", text):
            if "正在调查" not in text:
                return True, "有整改承诺但无时间节点"

        return False, ""

    def score_facts_layer(self, text: str) -> Dict:
        fact_score = 0
        for kw in self.FACTS_KEYWORDS["specific_fact"]:
            if kw in text:
                fact_score += 10
        if re.search(r"[0-9]{4}年|[0-9]+月|[0-9]+日", text):
            fact_score += 10
        if re.search(r"[0-9]+人|[0-9]+万|[0-9]+%", text):
            fact_score += 10
        fact_score = min(fact_score, 50)

        distinguish_score = 0
        for kw in self.FACTS_KEYWORDS["distinguish"]:
            if kw in text:
                distinguish_score += 15
        distinguish_score = min(distinguish_score, 30)

        remedy_score = 0
        for kw in self.FACTS_KEYWORDS["remedy"]:
            if kw in text:
                remedy_score += 8
        remedy_score = min(remedy_score, 20)

        total = fact_score + distinguish_score + remedy_score

        return {
            "total": total,
            "truth_verification": fact_score,
            "distinguish": distinguish_score,
            "remedy": remedy_score,
        }

    def score_values_layer(self, text: str) -> Dict:
        attitude_score = 0
        for kw in self.VALUES_KEYWORDS["attitude"]:
            if kw in text:
                attitude_score += 12
        attitude_score = min(attitude_score, 35)

        empathy_score = 0
        for kw in self.VALUES_KEYWORDS["empathy"]:
            if kw in text:
                empathy_score += 12
        empathy_score = min(empathy_score, 35)

        trust_score = 0
        for kw in self.VALUES_KEYWORDS["trust"]:
            if kw in text:
                trust_score += 10
        if re.search(r"[0-9]{4}年|[0-9]+月|[0-9]+日", text):
            trust_score += 10
        trust_score = min(trust_score, 30)

        total = attitude_score + empathy_score + trust_score

        return {
            "total": total,
            "attitude": attitude_score,
            "empathy": empathy_score,
            "trust": trust_score,
        }

    def score_path_compliance(self, text: str, crisis_type: str) -> Dict:
        if crisis_type not in self.PATH_RULES:
            return {"total": 50, "suggestion": "未识别危机类型，默认给分"}

        rules = self.PATH_RULES[crisis_type]
        score = 0

        if rules["keyword"] in text:
            score += 40

        secondary_keywords = {
            "疏导": ["议题", "意见", "专家", "公告", "通报"],
            "顺应": ["道歉", "理解", "支持", "同情", "关切"],
            "引领": ["统一", "大局", "目标", "方向", "共同体"],
            "转换": ["补偿", "共同", "携手", "合作", "转移"],
        }

        for path in rules["secondary"]:
            if path in secondary_keywords:
                for kw in secondary_keywords[path]:
                    if kw in text:
                        score += 15
                        break

        score = min(score, 100)

        return {
            "total": score,
            "primary_path": rules["primary"],
            "secondary_paths": rules["secondary"],
        }

    def get_grade(self, total_score: float) -> Tuple[str, str]:
        if total_score >= 85:
            return "A", "优秀：可立即发布"
        elif total_score >= 70:
            return "B", "良好：建议微调后发布"
        elif total_score >= 60:
            return "C", "合格：建议复核风险点后再发布"
        else:
            return "D", "不合格：建议重新撰写"

    def get_suggestions(self, scores: Dict) -> List[str]:
        suggestions = []

        if scores["facts"]["total"] < 60:
            suggestions.append("事实层得分偏低，建议补充具体事实、数据，并区分'已知'与'调查中'")

        if scores["values"]["total"] < 60:
            suggestions.append("价值层得分偏低，建议增加道歉/致歉，承认公众情绪，给出具体承诺和时间节点")

        if scores["path"]["total"] < 60:
            suggestions.append("路径适配得分偏低，建议调整策略组合，确保与危机类型匹配")

        if scores["facts"]["truth_verification"] < 30:
            suggestions.append("缺乏具体事实信息，建议补充时间、地点、数据等可验证信息")

        if scores["values"]["empathy"] < 20:
            suggestions.append("缺乏情感共情，建议承认公众的担忧、愤怒或悲伤")

        if scores["values"]["trust"] < 20:
            suggestions.append("缺乏信任重建措施，建议给出具体承诺和时间节点")

        return suggestions

    def analyze(self, text: str, crisis_type: str = "舆论争议") -> Dict:
        veto_triggered, veto_reason = self.check_veto(text)

        facts = self.score_facts_layer(text)
        values = self.score_values_layer(text)
        path = self.score_path_compliance(text, crisis_type)

        total_score = (
            facts["total"] * self.WEIGHTS["facts"]
            + values["total"] * self.WEIGHTS["values"]
            + path["total"] * self.WEIGHTS["path"]
        )

        if veto_triggered:
            total_score = 0

        grade, grade_desc = self.get_grade(total_score)
        suggestions = self.get_suggestions({
            "facts": facts,
            "values": values,
            "path": path,
        })

        return {
            "total_score": round(total_score, 1),
            "grade": grade,
            "grade_description": grade_desc,
            "dimensions": {
                "facts_layer": facts,
                "values_layer": values,
                "path_compliance": path,
            },
            "veto": {
                "triggered": veto_triggered,
                "reason": veto_reason if veto_triggered else None,
            },
            "suggestions": suggestions if not veto_triggered else [f"一票否决: {veto_reason}"],
        }


if __name__ == "__main__":
    scorer = StatementScorer()

    test_text_1 = """
    关于后厨卫生问题的致歉信

    尊敬的消费者：

    近日，媒体曝光我公司某门店后厨存在卫生问题，引发了社会关注，也给您带来了困扰和担忧。对此，我们深表歉意。

    经初步调查，视频反映的问题属实。这一事件反映出我们在食品安全管理方面存在严重不足，我们负有不可推卸的责任。

    目前，我们已采取以下措施：
    1. 涉事门店立即停业整改
    2. 全面排查全国门店后厨卫生
    3. 接受市场监管部门的检查

    我们承诺在30天内完成全面排查，并向社会公布结果。我们再次向所有消费者致以最诚挚的歉意。
    """

    print("=" * 60)
    print("测试1：海底捞式声明（高质量）")
    print("=" * 60)
    result = scorer.analyze(test_text_1, "产品问题")
    print(f"总分: {result['total_score']}")
    print(f"等级: {result['grade']} - {result['grade_description']}")
    print(f"事实层: {result['dimensions']['facts_layer']['total']}")
    print(f"价值层: {result['dimensions']['values_layer']['total']}")
    print(f"路径适配: {result['dimensions']['path_compliance']['total']}")
    if result["suggestions"]:
        print(f"建议: {result['suggestions']}")
    print()

    test_text_2 = """
    对不起。

    我在直播中的言论不恰当，我接受批评。我会在以后注意言行。
    """

    print("=" * 60)
    print("测试2：李佳琦式回应（低质量）")
    print("=" * 60)
    result = scorer.analyze(test_text_2, "舆论争议")
    print(f"总分: {result['total_score']}")
    print(f"等级: {result['grade']} - {result['grade_description']}")
    print(f"事实层: {result['dimensions']['facts_layer']['total']}")
    print(f"价值层: {result['dimensions']['values_layer']['total']}")
    print(f"路径适配: {result['dimensions']['path_compliance']['total']}")
    if result["suggestions"]:
        print(f"建议: {result['suggestions']}")
    print()

    test_text_3 = """
    关于XX事故的声明

    近日，我公司个别员工因操作不当引发事故。我们已经对该员工进行了处理。目前事故原因正在调查中。
    """

    print("=" * 60)
    print("测试3：推卸责任（触发一票否决）")
    print("=" * 60)
    result = scorer.analyze(test_text_3, "安全事故")
    print(f"总分: {result['total_score']}")
    print(f"等级: {result['grade']} - {result['grade_description']}")
    print(f"一票否决: {result['veto']['triggered']}")
    if result["veto"]["triggered"]:
        print(f"否决原因: {result['veto']['reason']}")
