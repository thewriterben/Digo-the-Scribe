"""
Command-line interface for Digo the Scribe.

Usage examples:
    digo status
    digo notes --transcript transcript.txt --title "Q1 Strategy" --date 2026-03-26
    digo report --notes output/notes/2026-03-26_q1_strategy.md
    digo escalate --topic "CFV valuation" --context "..." --reason "..."
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

from digo.agent import DigoAgent

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_status(agent: DigoAgent, _args: argparse.Namespace) -> None:
    console.print(agent.status())


def cmd_notes(agent: DigoAgent, args: argparse.Namespace) -> None:
    console.print("[bold cyan]Digo is processing the transcript…[/bold cyan]")

    if args.transcript:
        notes = agent.take_notes_from_file(
            args.transcript,
            meeting_title=args.title or "",
            meeting_date=args.date or "",
        )
    elif args.text:
        notes = agent.take_notes_from_text(
            args.text,
            meeting_title=args.title or "Untitled Meeting",
            meeting_date=args.date or "",
        )
    else:
        console.print("[red]Error: provide --transcript or --text[/red]")
        sys.exit(1)

    slug = (args.title or "meeting").lower().replace(" ", "_")
    out_path = agent.save_notes(notes, slug)
    console.print(f"\n[green]Notes saved → {out_path}[/green]\n")
    console.print(Markdown(notes))


def cmd_report(agent: DigoAgent, args: argparse.Namespace) -> None:
    notes_path = Path(args.notes)
    if not notes_path.exists():
        console.print(f"[red]Notes file not found: {notes_path}[/red]")
        sys.exit(1)

    notes = notes_path.read_text(encoding="utf-8")
    console.print("[bold cyan]Digo is generating the progress report…[/bold cyan]")
    report = agent.generate_progress_report(notes)
    slug = notes_path.stem
    out_path = agent.save_report(report, slug)
    console.print(f"\n[green]Report saved → {out_path}[/green]\n")
    console.print(Markdown(report))


def cmd_escalate(agent: DigoAgent, args: argparse.Namespace) -> None:
    notice = agent.create_escalation_notice(
        topic=args.topic,
        context=args.context or "",
        reason=args.reason or "Could not confirm from available documents.",
        meeting_title=args.title or "Unknown Meeting",
        meeting_date=args.date or "",
    )
    console.print("\n[bold yellow]Escalation notice:[/bold yellow]\n")
    console.print(notice)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="digo",
        description="Digo the Scribe — Digital Gold Co Hyper Agent",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    sub = parser.add_subparsers(dest="command", required=True)

    # --- status ---
    sub.add_parser("status", help="Show Digo's current status")

    # --- notes ---
    p_notes = sub.add_parser("notes", help="Take notes from a meeting transcript")
    p_notes.add_argument("--transcript", "-t", help="Path to transcript file")
    p_notes.add_argument("--text", help="Raw transcript text (alternative to --transcript)")
    p_notes.add_argument("--title", help="Meeting title")
    p_notes.add_argument("--date", help="Meeting date (YYYY-MM-DD)")

    # --- report ---
    p_report = sub.add_parser("report", help="Generate a progress report from saved notes")
    p_report.add_argument("--notes", "-n", required=True, help="Path to meeting notes file")

    # --- escalate ---
    p_esc = sub.add_parser("escalate", help="Create an escalation notice for Benjamin Snider")
    p_esc.add_argument("--topic", required=True, help="Topic that needs verification")
    p_esc.add_argument("--context", help="Context from the meeting")
    p_esc.add_argument("--reason", help="Why verification is needed")
    p_esc.add_argument("--title", help="Meeting title")
    p_esc.add_argument("--date", help="Meeting date")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _setup_logging(args.verbose)

    agent = DigoAgent()
    warnings = agent.load_resources()
    for w in warnings:
        console.print(f"[yellow]⚠  {w}[/yellow]")

    commands = {
        "status": cmd_status,
        "notes": cmd_notes,
        "report": cmd_report,
        "escalate": cmd_escalate,
    }
    commands[args.command](agent, args)


if __name__ == "__main__":
    main()
