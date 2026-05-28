# cli.py
import click
from blastmap import __version__
from pathlib import Path
from .core import build_graph, render_graph


@click.group()
@click.version_option(version=__version__, prog_name="blastmap")
def main():
    """Blastmap — instantly visualize any Python codebase's dependency graph."""
    pass


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--output", "-o", default="blastmap.html", help="Output HTML file name.")
def scan(path, output):
    """Scan a Python repo and generate an interactive dependency graph.

    PATH is the root of the repository to scan. Defaults to current directory.
    """
    repo_path = Path(path).resolve()
    click.echo(f"Scanning: {repo_path}")

    G = build_graph(str(repo_path))

    connected = {n for n, d in G.degree() if d > 0}
    click.echo(f"Nodes: {G.number_of_nodes()} | Connected: {len(connected)} | Edges: {G.number_of_edges()}")

    top = sorted(G.in_degree(), key=lambda x: x[1], reverse=True)[:3]
    if top:
        click.echo("Most critical files:")
        for node, deg in top:
            click.echo(f"  {node} ({deg} dependents)")

    output_path = Path(output).resolve()
    render_graph(G, output=str(output_path))
    click.echo(f"Graph saved to: {output_path}")
    click.echo("Open it in your browser to explore.")


if __name__ == "__main__":
    main()