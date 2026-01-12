from __future__ import annotations

import argparse


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="idle-ledger")
    sub = parser.add_subparsers(dest="command", required=True)

    debug_p = sub.add_parser("debug", help="Print live snapshots and derived state")
    debug_p.set_defaults(_handler="debug")

    run_p = sub.add_parser("run", help="Run tracker loop (foreground)")
    run_p.set_defaults(_handler="run")

    status_p = sub.add_parser("status", help="Show service status and totals")
    status_p.set_defaults(_handler="status")

    summary_p = sub.add_parser("summary", help="Show totals in hours/minutes")
    summary_p.add_argument(
        "period",
        nargs="?",
        default="today",
        choices=["today", "yesterday", "week"],
        help="Summary period (default: today)",
    )
    summary_p.set_defaults(_handler="summary")

    init_p = sub.add_parser("init", help="Install + enable systemd user service")
    init_p.add_argument("--force", action="store_true", help="Overwrite existing unit")
    init_p.set_defaults(_handler="init")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args._handler == "debug":
        from idle_ledger.cli.debug import main as debug_main

        debug_main()
        return 0

    if args._handler == "run":
        from idle_ledger.cli.run import main as run_main

        run_main()
        return 0

    if args._handler == "status":
        from idle_ledger.cli.status import main as status_main

        return int(status_main())

    if args._handler == "summary":
        from idle_ledger.cli.summary import main as summary_main

        return int(summary_main(period=str(getattr(args, "period", "today"))))

    if args._handler == "init":
        from idle_ledger.cli.init import main as init_main

        return int(init_main(force=bool(getattr(args, "force", False))))

    raise RuntimeError(f"Unknown command: {args._handler}")


if __name__ == "__main__":
    raise SystemExit(main())
