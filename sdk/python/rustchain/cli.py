"""CLI wrapper for the RustChain SDK.

Install with: pip install rustchain[cli]
Usage: rustchain health | rustchain balance <wallet> | rustchain miners | rustchain epoch
"""

from __future__ import annotations

import json
import sys


def main() -> None:
    """Entry point for the `rustchain` CLI command."""
    try:
        import click
    except ImportError:
        print("CLI requires click: pip install rustchain[cli]", file=sys.stderr)
        sys.exit(1)

    @click.group()
    @click.option("--node", default="https://50.28.86.131", help="RustChain node URL")
    @click.pass_context
    def cli(ctx: click.Context, node: str) -> None:
        """RustChain CLI — interact with RustChain nodes from the terminal."""
        from rustchain.client import RustChainClient

        ctx.ensure_object(dict)
        ctx.obj["client"] = RustChainClient(base_url=node)

    @cli.command()
    @click.pass_context
    def health(ctx: click.Context) -> None:
        """Check node health."""
        h = ctx.obj["client"].health()
        click.echo(json.dumps(h.model_dump(), indent=2))

    @cli.command()
    @click.pass_context
    def epoch(ctx: click.Context) -> None:
        """Get current epoch info."""
        e = ctx.obj["client"].epoch()
        click.echo(json.dumps(e.model_dump(), indent=2))

    @cli.command()
    @click.pass_context
    def miners(ctx: click.Context) -> None:
        """List active miners."""
        ms = ctx.obj["client"].miners()
        for m in ms:
            click.echo(f"{m.miner_id}  {m.device_family or '?':>10}  {m.status or 'unknown'}")

    @cli.command()
    @click.argument("wallet_id")
    @click.pass_context
    def balance(ctx: click.Context, wallet_id: str) -> None:
        """Check RTC balance for a wallet."""
        b = ctx.obj["client"].balance(wallet_id)
        click.echo(f"Balance: {b.balance} RTC (pending: {b.pending})")

    @cli.command()
    @click.argument("miner_id")
    @click.pass_context
    def attestation(ctx: click.Context, miner_id: str) -> None:
        """Check attestation status for a miner."""
        a = ctx.obj["client"].attestation_status(miner_id)
        click.echo(json.dumps(a.model_dump(), indent=2))

    cli()


if __name__ == "__main__":
    main()
