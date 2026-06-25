"""危机传播 CLI —— /crisis 命令界面。"""

from __future__ import annotations

import json
from typing import Optional

from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from cli.display import console, print_status
from utils.crisis_risk_analyzer import analyze_crisis_event, score_holding_statement
from utils.path import get_project_root
from utils.skill_registry import format_active_skills_for_prompt, get_skill_registry


_ALERT_STYLES = {
    "blue": ("bold blue", "🔵"),
    "yellow": ("bold yellow", "🟡"),
    "orange": ("bold orange1", "🟠"),
    "red": ("bold red", "🔴"),
}


def _load_crisis_skill_context() -> str:
    registry = get_skill_registry()
    skill = registry.skills.get("crisis_response")
    if skill and skill.content:
        return skill.content.strip()
    path = get_project_root() / "skills" / "crisis-response.md"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def _generate_ai_plan(event_text: str, analysis_dict: dict) -> str:
    """调用 LLM 基于 crisis-response Skill 生成完整处置方案。"""
    from langchain_core.messages import HumanMessage, SystemMessage
    from model.factory import get_react_model

    skill_ctx = _load_crisis_skill_context()
    system = (
        "你是 PRClaw 危机传播管理专家。严格遵循以下 Skill 指令输出完整危机处置方案。\n\n"
        f"{skill_ctx}\n\n"
        "输出要求：\n"
        "1. 先给出危机诊断（等级、预警色、响应层级）\n"
        "2. 给出策略路径及理由\n"
        "3. 生成：初始声明、正式道歉信（如需要）、媒体Q&A（5条）、内部口径\n"
        "4. 给出质量自评（事实层/价值层/路径适配）及响应时间表\n"
        "5. 使用 Markdown 格式，语言简洁专业"
    )
    user = (
        f"【事件输入】\n{event_text}\n\n"
        f"【规则引擎预诊断（供参考）】\n```json\n{json.dumps(analysis_dict, ensure_ascii=False, indent=2)}\n```\n\n"
        "请基于 crisis-response Skill 输出完整处置方案。"
    )

    model = get_react_model()
    response = model.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    content = getattr(response, "content", "") or str(response)
    return content.strip()


def _print_analysis_report(result, quality_report: Optional[dict] = None) -> None:
    style, icon = _ALERT_STYLES.get(result.alert_color, ("bold white", "⚪"))

    console.print()
    console.print(
        Panel(
            f"[{style}]{icon} {result.alert_label}  ·  {result.crisis_level}[/{style}]\n"
            f"[white]综合危机指数：[/white][bold]{result.crisis_score}[/bold] / 100\n"
            f"[dim]危机类型：{result.crisis_type} ｜ 响应层级：{result.response_level}[/dim]",
            title="[bold cyan]危机预警诊断[/bold cyan]",
            border_style=result.alert_color if result.alert_color != "orange" else "dark_orange",
            padding=(1, 2),
        )
    )

    dim_table = Table(show_header=True, header_style="bold magenta", border_style="cyan")
    dim_table.add_column("维度", style="cyan", width=12)
    dim_table.add_column("得分", style="yellow", width=8)
    dim_table.add_column("说明", style="white")
    dim_table.add_row("严重程度", str(result.dimension_scores["severity"]), "人身伤害、事故等级、安全影响")
    dim_table.add_row("传播热度", str(result.dimension_scores["spread"]), "热搜、社交平台、声量增幅")
    dim_table.add_row("情感烈度", str(result.dimension_scores["emotion"]), "公众愤怒、抵制、信任危机")
    dim_table.add_row("处置紧迫", str(result.dimension_scores["urgency"]), "上级时限、发布会、黄金时间")
    if result.casualties and any(result.casualties.values()):
        c = result.casualties
        dim_table.add_row(
            "伤亡概况",
            f"亡{c['deaths']}/伤{c['injuries']}/失联{c['missing']}",
            "结构化提取，用于分级下限判定",
        )
    console.print()
    console.print(dim_table)

    plan_table = Table(show_header=True, header_style="bold green", border_style="green", title="响应方案")
    plan_table.add_column("项目", style="cyan", width=16)
    plan_table.add_column("内容", style="white")
    plan_table.add_row("首次表态时限", result.first_response_sla)
    plan_table.add_row("跟进通报节奏", result.followup_sla)
    plan_table.add_row("主策略路径", result.primary_path)
    plan_table.add_row("辅助路径", " + ".join(result.secondary_paths))
    plan_table.add_row("策略说明", result.strategy_reason)
    console.print()
    console.print(plan_table)

    console.print("\n[bold yellow]行动清单[/bold yellow]")
    for i, action in enumerate(result.action_checklist, 1):
        console.print(f"  {i}. {action}")

    console.print("\n[bold red]风险提示[/bold red]")
    for note in result.key_risks:
        console.print(f"  • {note}")

    console.print()
    console.print(
        Panel(
            result.holding_statement_hint,
            title="[bold]初始声明框架（待完善）[/bold]",
            border_style="dim",
            padding=(1, 2),
        )
    )

    if quality_report:
        grade = quality_report.get("grade", "-")
        total = quality_report.get("total_score", "-")
        console.print()
        console.print(
            f"[bold cyan]声明质量评分[/bold cyan]：{total} 分 ｜ 等级 [bold]{grade}[/bold]"
        )
        suggestions = quality_report.get("suggestions") or []
        if suggestions:
            console.print("[dim]优化建议：[/dim]")
            for s in suggestions[:5]:
                console.print(f"  - {s}")

    console.print()


def run_crisis_command(raw: str) -> None:
    """
    处理 /crisis 命令。

    用法：
      /crisis              交互输入事件（默认调用 AI）
      /crisis <事件描述>    规则诊断 + AI 完整处置方案
    """
    text = raw.strip()
    use_ai = True
    event_text = ""

    if not text or text == "/crisis":
        console.print()
        console.print("[bold cyan]危机传播分析[/bold cyan] —— 基于 crisis-response Skill")
        console.print("[dim]请输入事件描述（Enter 空行取消）[/dim]")
        event_text = Prompt.ask("[bold cyan]事件[/bold cyan]").strip()
        if not event_text:
            console.print("[yellow]已取消[/yellow]")
            return
        ai_choice = Prompt.ask(
            "[dim]是否调用 AI 生成完整处置方案？[/dim] [cyan](Y/n)[/cyan]",
            default="Y",
        ).strip().lower()
        use_ai = ai_choice not in {"n", "no", "否"}
    elif text.startswith("/crisis "):
        event_text = text[len("/crisis "):].strip()
    else:
        event_text = text

    if not event_text:
        console.print("[yellow]用法：/crisis [事件描述][/yellow]")
        return

    print_status("正在分析危机风险...", "info")

    try:
        result = analyze_crisis_event(event_text)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        return

    analysis_dict = result.to_dict()
    quality = score_holding_statement(result.holding_statement_hint, result.crisis_type)
    if quality:
        analysis_dict["quality_report"] = {
            "total_score": quality.get("total_score"),
            "grade": quality.get("grade"),
            "veto": quality.get("veto"),
        }

    _print_analysis_report(result, quality)

    active_preview = format_active_skills_for_prompt(event_text)
    if active_preview and "crisis_response" in active_preview:
        console.print("[dim]✓ crisis_response Skill 已匹配激活[/dim]\n")

    if use_ai:
        print_status("正在调用 AI 生成完整处置方案（crisis-response Skill）...", "info")
        try:
            ai_text = _generate_ai_plan(event_text, analysis_dict)
            console.print()
            console.print(
                Panel(
                    Markdown(ai_text),
                    title="[bold green]AI 完整处置方案[/bold green]",
                    border_style="green",
                    padding=(1, 2),
                )
            )
        except Exception as exc:
            console.print(f"[red]AI 生成失败：{exc}[/red]")
            console.print("[yellow]规则引擎诊断结果仍有效，可基于上方方案手动完善。[/yellow]")

    console.print("[dim]结构化 JSON 已就绪，可用于作业提交或系统对接。[/dim]")
    console.print(
        Panel(
            json.dumps(analysis_dict, ensure_ascii=False, indent=2),
            title="[dim]JSON 输出[/dim]",
            border_style="dim",
        )
    )
    console.print()
