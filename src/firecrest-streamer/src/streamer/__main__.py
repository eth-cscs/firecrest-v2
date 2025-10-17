import click
from streamer.streamer_client import send, receive
from streamer.streamer_server import server
from importlib.metadata import version


def get_version():
    try:
        return version("firecrest-streamer")
    except Exception:
        return "dev"


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Show version and exit.")
@click.pass_context
def cli(ctx, version):
    if version:
        click.echo(f"Firecrest streamer version: {get_version()}")
        ctx.exit()


# Register groups
cli.add_command(send)
cli.add_command(receive)
cli.add_command(server)


if __name__ == "__main__":
    cli()
