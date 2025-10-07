import click
from streamer.streamer_client import send, receive
from streamer.streamer_server import server


@click.group()
def cli():
    pass


# Register groups
cli.add_command(send)
cli.add_command(receive)
cli.add_command(server)


if __name__ == "__main__":
    cli()
