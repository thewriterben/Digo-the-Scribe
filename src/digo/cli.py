"""
Command-line interface for Digo the Scribe.

Usage examples:
    digo status
    digo notes --transcript transcript.txt --title "Q1 Strategy" --date 2026-03-26
    digo report --notes output/notes/2026-03-26_q1_strategy.md
    digo escalate --topic "CFV valuation" --context "..." --reason "..."
    digo listen --title "Q1 Strategy Review" --date 2026-03-26
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

from digo import __version__
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


def cmd_load_resource(agent: DigoAgent, args: argparse.Namespace) -> None:
    path = Path(args.path)
    if not path.exists():
        console.print(f"[red]File not found: {path}[/red]")
        sys.exit(1)
    if path.suffix.lower() != ".pdf":
        console.print("[red]Error: only PDF files are supported.[/red]")
        sys.exit(1)

    try:
        agent.load_resource_from_path(args.name, path)
        console.print(f"[green]Loaded resource '{args.name}' from {path}[/green]")
    except Exception as exc:
        console.print(f"[red]Failed to load resource: {exc}[/red]")
        sys.exit(1)


def cmd_listen(agent: DigoAgent, args: argparse.Namespace) -> None:
    """Start live microphone listening, transcribe, and produce notes."""
    title = args.title or "Live Meeting"
    date = args.date or ""

    # ------------------------------------------------------------------
    # Google Meet session discovery (--meet or --event-id)
    # ------------------------------------------------------------------
    if getattr(args, "meet", False) or getattr(args, "event_id", None):
        try:
            from digo.google_meet import MeetSession

            meet_session: MeetSession | None = None

            if args.event_id:
                console.print(
                    f"[bold cyan]Fetching Google Calendar event '{args.event_id}'…[/bold cyan]"
                )
                meet_session = agent.get_meet_session_by_event_id(args.event_id)
            else:
                console.print("[bold cyan]Looking for upcoming Google Meet sessions…[/bold cyan]")
                meet_session = agent.get_next_meet_session()

            if meet_session is None:
                console.print("[yellow]No Google Meet session found.[/yellow]")
                if not args.title:
                    console.print("[yellow]Falling back to default title 'Live Meeting'.[/yellow]")
            else:
                console.print("\n[green]Found Google Meet session:[/green]")
                console.print(f"  Title: {meet_session.title}")
                console.print(f"  Date: {meet_session.meeting_date}")
                console.print(f"  Meet link: {meet_session.meet_link}")
                if meet_session.participants:
                    console.print(f"  Participants: {', '.join(meet_session.participants)}")
                console.print()

                # Use Meet session metadata if not explicitly overridden
                if not args.title:
                    title = meet_session.title
                if not args.date:
                    date = meet_session.meeting_date

        except ImportError as exc:
            console.print(f"[yellow]Google Meet integration unavailable: {exc}[/yellow]")

    # ------------------------------------------------------------------
    # Audio listener
    # ------------------------------------------------------------------
    try:
        listener = agent.create_listener()
    except ImportError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)

    console.print(f"[bold cyan]Digo is now listening to '{title}'…[/bold cyan]")
    console.print("[dim]Press Ctrl+C to stop listening and generate notes.[/dim]\n")

    listener.start(meeting_title=title, meeting_date=date)

    last_count = 0
    try:
        while listener.is_listening:
            session = listener.get_transcript()
            if session and session.segment_count > last_count:
                for seg in session.segments[last_count:]:
                    console.print(
                        f"  [dim][{seg.timestamp}][/dim] {seg.text}",
                        highlight=False,
                    )
                last_count = session.segment_count
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping listener…[/yellow]")

    session = listener.stop()
    console.print(f"\n[bold green]Captured {session.segment_count} speech segment(s).[/bold green]")

    if session.segment_count == 0:
        console.print("[yellow]No speech was captured. No notes generated.[/yellow]")
        return

    console.print("[bold cyan]Digo is processing the transcript…[/bold cyan]")
    notes = agent.take_notes_from_session(session)
    slug = title.lower().replace(" ", "_")
    out_path = agent.save_notes(notes, slug)
    console.print(f"\n[green]Notes saved → {out_path}[/green]\n")
    console.print(Markdown(notes))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="digo",
        description="Digo the Scribe — Digital Gold Co Hyper Agent",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
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

    # --- load-resource ---
    p_load = sub.add_parser("load-resource", help="Load an additional PDF resource")
    p_load.add_argument("--name", "-n", required=True, help="Display name for the resource")
    p_load.add_argument("--path", "-p", required=True, help="Path to the PDF file")

    # --- listen ---
    p_listen = sub.add_parser(
        "listen",
        help="Listen to a live meeting via microphone and generate notes",
    )
    p_listen.add_argument("--title", help="Meeting title (default: 'Live Meeting')")
    p_listen.add_argument("--date", help="Meeting date (YYYY-MM-DD)")
    p_listen.add_argument(
        "--meet",
        action="store_true",
        default=False,
        help="Auto-discover the next Google Meet session from Google Calendar",
    )
    p_listen.add_argument(
        "--event-id",
        help="Google Calendar event ID of a specific Meet session to use",
    )

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
        "load-resource": cmd_load_resource,
        "listen": cmd_listen,
    }
    commands[args.command](agent, args)


if __name__ == "__main__":
    main()
