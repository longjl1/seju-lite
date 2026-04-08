from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text


console = Console()


def print_chat_banner(session_key: str) -> None:
    title = Text("seju-lite CLI", style="bold cyan")
    subtitle = Text(f"session: {session_key}", style="dim")
    body = Text.assemble(
        ("Chat locally with the current runtime.\n", "white"),
        ("Type ", "dim"),
        ("/exit", "bold yellow"),
        (" to quit.", "dim"),
    )
    console.print(Panel.fit(Text.assemble(title, "\n", subtitle, "\n\n", body), border_style="cyan"))


def print_user_prompt() -> str:
    return "[bold #a2d2ff]You[/bold #a2d2ff] > "


def prompt_user() -> str:
    return console.input(print_user_prompt())


def print_assistant_reply(reply: str) -> None:
    console.print()
    console.print("[bold #9966CC]● Seju >[/bold #9966CC]")
    console.print(reply or "")
    console.print()


def print_error_reply(reply: str) -> None:
    console.print()
    console.print(Rule("[bold red]Error[/bold red]", style="red"))
    console.print(Panel(reply or "", border_style="red", padding=(0, 1)))
    console.print()


def print_goodbye() -> None:
    console.print("[dim]Bye.[/dim]")


def print_config_summary(config_path: str, app_name: str, provider_label: str) -> None:
    panel_text = Text.assemble(
        ("Config OK\n", "bold green"),
        (f"{config_path}\n", "white"),
        ("App: ", "dim"),
        (f"{app_name}\n", "cyan"),
        ("Provider: ", "dim"),
        (provider_label, "magenta"),
    )
    console.print(Panel.fit(panel_text, border_style="green"))


def print_tools_table(defs: list[dict]) -> None:
    table = Table(title="Registered Tools", header_style="bold cyan")
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("Description", style="white")
    for item in defs:
        fn = item.get("function", {})
        name = fn.get("name", "<unknown>")
        desc = fn.get("description", "")
        table.add_row(str(name), str(desc))
    console.print(table)


def print_provider_response(content: str, tool_calls: list) -> None:
    console.print(Panel(content or "", title="Provider Response", border_style="magenta"))
    if not tool_calls:
        return
    table = Table(title="Tool Calls", header_style="bold yellow")
    table.add_column("Name", style="yellow", no_wrap=True)
    table.add_column("Arguments", style="white")
    for tc in tool_calls:
        table.add_row(str(tc.name), str(tc.arguments))
    console.print(table)
