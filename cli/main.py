"""Command-line entry point for Eylo operations."""

import os
import platform
import subprocess
from typing import Optional
import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from api_cli import CliOverrides, register_api_commands

AVAILABLE_SERVICES = [
    "redis-7",
    "eylo-server",
    "postgres-17",
    # "coturn"
]

# Initialize typer app and rich console
app = typer.Typer(help="CLI tool to manage your Eylo Docker project.")
console = Console()

_DATA_DUMP_FILE = "data_backup.dump"
_PG_CLIENT = "pgcli"
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_PG_HOST = os.getenv("PG_HOST", "localhost")
_PG_PORT = int(os.getenv("PG_PORT", "5432"))
_PG_USER = os.getenv("PG_USER", "eylo")
_PG_DB = os.getenv("PG_DB", "eylo")
_PG_PASSWORD = os.getenv("PG_PASSWORD", "eylo")


# Get paths
CLI_DIR = Path(__file__).parent
SERVER_DIR = CLI_DIR.parent / "server"
SERVER_VENV_PYTHON = SERVER_DIR / ".venv" / "bin" / "python"


@app.command(help="Start the Docker services")
def start(
    services: Optional[list[str]] = typer.Option(
        [],
        help="Specific services to start --services postgres-17  --services redis-7 --services eylo-server",
    ),
):
    # flake8: noqa E501
    """
    Start the Docker services.

    This command launches the Docker containers for the specified services or all available services if none are specified.

    Examples:
        $ eylo start
        $ eylo start --services eylo-server  --services postgres-17  --services redis-7

    Options:
        --services: List of services to start. If not provided, all available services will be started.
                    Valid services include: [list depends on AVAILABLE_SERVICES constant].
    """
    console.print("[bold blue]Starting Docker services...[/]")

    if services:
        services = [service for service in services if service in AVAILABLE_SERVICES]
    else:
        services = AVAILABLE_SERVICES

    args = ["up", "-d"] + services
    result = docker_compose(args, stream_output=True)

    if result:
        console.print("[bold green]Services started successfully! 🚀[/]")
    else:
        console.print("[bold red]Failed to start services ❌[/]")


@app.command(help="Stop the Docker services")
def stop(
    services: Optional[list[str]] = typer.Option(
        [],
        help="Specific services to stop --services postgres-17  --services redis-7 --services eylo-server",
    ),
):
    """Stop the Docker services"""
    console.print("[bold blue]Stopping Docker services...[/]")
    if services:
        services = [service for service in services if service in AVAILABLE_SERVICES]
    else:
        services = AVAILABLE_SERVICES
    args = ["stop"] + services
    result = docker_compose(args, stream_output=True)

    if result:
        console.print("[bold green]Services stopped successfully! 🛑[/]")
    else:
        console.print("[bold red]Failed to stop services ❌[/]")


@app.command(help="Reset the Docker services")
def reset():
    """Reset the Docker services"""
    console.print("[bold blue]Resetting Docker services...[/]")
    args = ["down", "--volumes", "--remove-orphans"]
    result = docker_compose(args, stream_output=True)

    if result:
        console.print("[bold green]Services reset successfully! 🔄[/]")
    else:
        console.print("[bold red]Failed to reset services ❌[/]")
        return False


@app.command(help="Build the Docker services")
def build():
    """Build the Docker services"""
    console.print("[bold blue]Building Docker services...[/]")
    args = ["build"]
    result = docker_compose(args, stream_output=True)

    if result:
        console.print("[bold green]Services built successfully! 🏗[/]")
    else:
        console.print("[bold red]Failed to build services ❌[/]")


@app.command(help="Re-Build the Docker services")
def rebuild():
    """Re-Build the Docker services"""
    console.print("[bold blue]Re-Building Docker services...[/]")
    args = ["build", "--no-cache"]
    result = docker_compose(args, stream_output=True)

    if result:
        console.print("[bold green]Services re-built successfully! 🏗[/]")
    else:
        console.print("[bold red]Failed to re-build services ❌[/]")


@app.command(help="View logs from Docker services")
def logs(
    service: Optional[str] = typer.Argument(
        None, help="Specific service to view logs for"
    ),
):
    """View logs from Docker services"""
    args = ["logs", "--follow"]
    if service:
        args.append(service)

    console.print(
        f"[bold blue]Streaming logs{' for ' + service if service else ''}...[/]"
    )
    console.print("[yellow]Press Ctrl+C to stop viewing logs[/]")

    # Logs should always be streamed
    docker_compose(args, stream_output=True)


@app.command(help="SSH into a service container")
def ssh(
    service: str = typer.Argument(default="eylo-server", help="Service to SSH into"),
):
    """SSH into a service container"""
    console.print(f"[bold blue]SSH into {service} container...[/]")

    args = ["exec", "-ti", service, "/bin/bash"]
    result = docker_compose(args, stream_output=True)

    if not result:
        console.print("[bold red]Failed to SSH into container ❌[/]")
        return False

    console.print("[bold green]Exited SSH session 🚪[/]")


@app.command(help="Run widget dev server")
def widget(
    port: int = typer.Option(5174, help="Port to run the widget server on"),
    mode: str = typer.Option("dev", help="Mode to run the widget server in"),
    ui: bool = typer.Option(True, help="Run the widget UI server (default: True)"),
    preact: bool = typer.Option(
        True, help="Run the widget Preact server (default: False)"
    ),
):
    """Run widget dev server using Vite"""
    console.print("[bold blue]Starting widget dev server...[/]")

    try:
        cmd = ["pnpm", "vite", "--port", str(port), "--mode", mode]
        console.print(f"[dim]Running: {' '.join(cmd)}[/]")
        cwd = "widget"
        if ui:
            if preact:
                cwd = "widget/preact-ui"
            else:
                raise typer.BadParameter(
                    "Cannot run widget UI without Preact. Use --preact to run Preact UI."
                )

        subprocess.run(
            cmd,
            check=True,
            cwd=cwd,  # Set working directory to widget folder
        )

    except subprocess.CalledProcessError as e:
        console.print("[bold red]Failed to start widget server ❌[/]", e)
        return False

    console.print("[bold green]Widget server started successfully! 🚀[/]")


@app.command(help="Build preact-widget")
def build_widget():
    """Build the Preact widget (includes SDK and UI build)"""
    console.print("[bold blue]Building Preact widget...[/]")

    widget_path = Path(PROJECT_ROOT) / "widget"
    preact_ui_path = widget_path / "preact-ui"

    try:
        # Step 1: Clean widget SDK directory (node_modules and dist)
        console.print("[dim]Cleaning widget SDK directory...[/]")
        widget_node_modules = widget_path / "node_modules"
        widget_dist = widget_path / "dist"

        if widget_node_modules.exists():
            console.print(f"[dim]Removing {widget_node_modules}[/]")
            shutil.rmtree(widget_node_modules)
        if widget_dist.exists():
            console.print(f"[dim]Removing {widget_dist}[/]")
            shutil.rmtree(widget_dist)

        # Step 2: Build widget SDK
        console.print("[dim]Installing dependencies for widget SDK...[/]")
        subprocess.run(["pnpm", "install"], check=True, cwd=widget_path)

        console.print("[dim]Building widget SDK...[/]")
        subprocess.run(["pnpm", "build"], check=True, cwd=widget_path)
        console.print("[bold green]✓ Widget SDK built successfully![/]")

        # Step 3: Clean preact-ui directory (node_modules and dist)
        console.print("[dim]Cleaning preact-ui directory...[/]")
        preact_node_modules = preact_ui_path / "node_modules"
        preact_dist = preact_ui_path / "dist"

        if preact_node_modules.exists():
            console.print(f"[dim]Removing {preact_node_modules}[/]")
            shutil.rmtree(preact_node_modules)
        if preact_dist.exists():
            console.print(f"[dim]Removing {preact_dist}[/]")
            shutil.rmtree(preact_dist)

        # Step 4: Build preact-ui
        console.print("[dim]Installing dependencies for preact-ui...[/]")
        subprocess.run(["pnpm", "install"], check=True, cwd=preact_ui_path)

        console.print("[dim]Building preact-ui...[/]")
        subprocess.run(["pnpm", "build"], check=True, cwd=preact_ui_path)
        console.print("[bold green]✓ Preact UI built successfully![/]")

    except subprocess.CalledProcessError as e:
        console.print("[bold red]Failed to build widget ❌[/]", e)
        return False

    console.print("[bold green]Preact widget built successfully! 🚀[/]")
    return True


# run backend server
@app.command(help="Run backend server")
def backend(
    mode: str = typer.Option("dev", help="Mode to run the backend server in"),
    port: int = typer.Option(8000, help="Port to run the backend server on"),
    workers: int = typer.Option(1, help="Number of workers to run"),
    # mode: str = typer.Option("dev", help="Mode to run the backend server in"),
):
    """Run backend server using Uvicorn"""
    console.print("[bold blue]Starting backend server...[/]")
    _env = "local" if mode == "dev" else "prod"
    _workers = workers if mode != "dev" else 1
    try:
        env = os.environ.copy()
        env["ENV"] = _env  # Add password to environment
        cmd = ["uv", "run", "fastapi", "run", "--port", str(port)]
        if mode == "dev":
            cmd.append("--reload")
        if mode == "prod":
            cmd.extend(
                [
                    "--workers",
                    str(_workers),
                ]
            )

        console.print(f"[dim]Running: {' '.join(cmd)}[/]")
        subprocess.run(
            cmd, check=True, cwd="server"
        )  # Set working directory to server folder

    except subprocess.CalledProcessError as e:
        console.print("[bold red]Failed to start backend server ❌[/]", e)
        return False


# Alias: be (backend)
@app.command(name="be", help="Alias for 'backend' command")
def be(
    mode: str = typer.Option("dev", help="Mode to run the backend server in"),
    port: int = typer.Option(8000, help="Port to run the backend server on"),
    workers: int = typer.Option(1, help="Number of workers to run"),
):
    """Alias for backend command."""
    backend(mode=mode, port=port, workers=workers)


@app.command(help="Run the PostgreSQL-backed durable worker")
def durable_worker():
    console.print("[bold blue]Starting durable worker...[/]")
    try:
        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "eylo.agent_run_worker",
        ]
        console.print(f"[dim]Running: {' '.join(cmd)}[/]")
        subprocess.run(
            cmd, check=True, cwd="server"
        )  # Set working directory to server folder

    except subprocess.CalledProcessError as e:
        console.print("[bold red]Failed to start durable worker ❌[/]", e)
        return False

    console.print("[bold green]Durable worker stopped cleanly.[/]")


# connect to the database
@app.command(help="Connect to the database")
def db():
    """Connect to the database using psql"""
    console.print("[bold blue]Connecting to the database...[/]")

    try:
        env = os.environ.copy()
        env["PGPASSWORD"] = _PG_PASSWORD  # Add password to environment
        cmd = [
            _PG_CLIENT,
            "--host",
            _PG_HOST,
            "--port",
            str(_PG_PORT),
            "--user",
            _PG_USER,
            "--dbname",
            _PG_DB,
        ]
        subprocess.run(cmd, check=True, env=env)

    except subprocess.CalledProcessError as e:
        console.print("[bold red]Failed to connect to the database ❌[/]", e)
        return False

    console.print("[bold green]Connected to the database successfully! 🚀[/]")


@app.command(help="Prepare Seed Data")
def prepare_seed_data():
    console.print("[bold blue]Preparing seed data...[/]")
    try:
        file_path = os.path.join(
            os.path.dirname(__file__), "..", "data", _DATA_DUMP_FILE
        )
        env = os.environ.copy()
        env["PGPASSWORD"] = _PG_PASSWORD  # Add password to environment
        cmd = [
            "pg_dump",
            "-U",
            _PG_USER,
            "-h",
            _PG_HOST,
            "-p",
            str(_PG_PORT),
            "-d",
            _PG_DB,
            "--data-only",
            "--no-owner",
            "--format=custom",
            "-f",
            file_path,
        ]
        subprocess.run(cmd, check=True, env=env)

    except subprocess.CalledProcessError as e:
        console.print("[bold red]Failed to prepare seed data ❌[/]", e)
        return False

    console.print("[bold green]Seed data prepared successfully! 🚀[/]")


@app.command(help="Restore Seed Data")
def restore_seed_data():
    console.print("[bold blue]Restoring seed data...[/]")
    try:
        file_path = os.path.join(
            os.path.dirname(__file__), "..", "data", _DATA_DUMP_FILE
        )
        env = os.environ.copy()
        env["PGPASSWORD"] = _PG_PASSWORD  # Add password to environment
        cmd = [
            "pg_restore",
            "-U",
            _PG_USER,
            "-h",
            _PG_HOST,
            "-p",
            str(_PG_PORT),
            "-d",
            _PG_DB,
            "-t",
            "agent_agents",
            "-t",
            "agent_tools",
            "-t",
            "contact_contacts",
            "-t",
            "integration_v2_installations",
            "-t",
            "integration_v2_tools",
            "-t",
            "connection_connections",
            "-t",
            "member_members",
            "-t",
            "organization_organizations",
            "--data-only",
            "--disable-triggers",
            "--no-owner",
            "--single-transaction",
            "--verbose",
            file_path,
        ]

        # # EOF

        subprocess.run(cmd, check=True, env=env)

    except subprocess.CalledProcessError as e:
        console.print("[bold red]Failed to restore seed data ❌[/]", e)
        return False

    console.print("[bold green]Seed data restored successfully! 🚀[/]")


_FULL_DUMP_FILE = "full_backup.sql"


@app.command(help="Dump entire database (schema + data) for migration")
def dump_all(
    output_file: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (defaults to data/full_backup.dump)",
    ),
    host: str = typer.Option(_PG_HOST, "--host", "-h", help="Source database host"),
    port: int = typer.Option(_PG_PORT, "--port", "-p", help="Source database port"),
    user: str = typer.Option(_PG_USER, "--user", "-U", help="Database user"),
    db: str = typer.Option(_PG_DB, "--db", "-d", help="Database name"),
    password: str = typer.Option(_PG_PASSWORD, "--password", help="Database password"),
):
    """
    Dump the entire database (schema + data) for host-to-host migration.

    Creates a full pg_dump in custom format that can be restored with restore-all.

    Examples:
        $ eylo dump-all
        $ eylo dump-all --host prod-db.example.com --port 5432
        $ eylo dump-all --output /tmp/migration.dump
    """
    console.print("[bold blue]Dumping entire database...[/]")

    file_path = output_file or os.path.join(_DATA_DIR, _FULL_DUMP_FILE)

    try:
        env = os.environ.copy()
        env["PGPASSWORD"] = password
        cmd = [
            "pg_dump",
            "-U",
            user,
            "-h",
            host,
            "-p",
            str(port),
            "-d",
            db,
            "--no-owner",
            "--no-acl",
            "--format=plain",
            "--verbose",
            "-f",
            file_path,
        ]
        console.print(f"[dim]Running: {' '.join(cmd)}[/]")
        subprocess.run(cmd, check=True, env=env)

    except subprocess.CalledProcessError as e:
        console.print("[bold red]Failed to dump database ❌[/]", e)
        return False

    file_size = os.path.getsize(file_path)
    console.print(f"[bold green]Database dumped successfully! 🚀[/]")
    console.print(f"[dim]File: {file_path} ({file_size / 1024 / 1024:.1f} MB)[/]")


@app.command(help="Restore entire database from dump (for migration)")
def restore_all(
    input_file: Optional[str] = typer.Option(
        None,
        "--input",
        "-i",
        help="Input dump file path (defaults to data/full_backup.sql)",
    ),
    host: str = typer.Option(_PG_HOST, "--host", "-h", help="Target database host"),
    port: int = typer.Option(_PG_PORT, "--port", "-p", help="Target database port"),
    user: str = typer.Option(_PG_USER, "--user", "-U", help="Database user"),
    db: str = typer.Option(_PG_DB, "--db", "-d", help="Database name"),
    password: str = typer.Option(_PG_PASSWORD, "--password", help="Database password"),
    clean: bool = typer.Option(
        False, "--clean", "-c", help="Drop existing objects before restoring"
    ),
):
    """
    Restore entire database from a dump file for host-to-host migration.

    Restores a plain SQL dump created with dump-all.
    The dump is a readable .sql file you can edit before restoring.

    Examples:
        $ eylo restore-all
        $ eylo restore-all --host new-db.example.com --port 5432
        $ eylo restore-all --input /tmp/migration.sql --clean
    """
    file_path = input_file or os.path.join(_DATA_DIR, _FULL_DUMP_FILE)

    if not os.path.exists(file_path):
        console.print(f"[bold red]Dump file not found: {file_path} ❌[/]")
        return False

    file_size = os.path.getsize(file_path)
    console.print(
        f"[bold blue]Restoring database from {file_path} ({file_size / 1024 / 1024:.1f} MB)...[/]"
    )

    try:
        env = os.environ.copy()
        env["PGPASSWORD"] = password

        psql_cmd = [
            "psql",
            "-U",
            user,
            "-h",
            host,
            "-p",
            str(port),
            "-d",
            db,
            "--single-transaction",
            "-v",
            "ON_ERROR_STOP=1",
            "-f",
            file_path,
        ]

        console.print(f"[dim]Running: {' '.join(psql_cmd)}[/]")
        subprocess.run(psql_cmd, check=True, env=env)

    except subprocess.CalledProcessError as e:
        console.print("[bold red]Failed to restore database ❌[/]", e)
        return False

    console.print("[bold green]Database restored successfully! 🚀[/]")


@app.command(help="Cleanup __pycache__ files")
def pyclean():
    cmd = ["find", ".", "-regex", "^.*\\(__pycache__\\|\\.py[co]\\)$", "-delete"]
    try:
        console.print(f"[dim]Running: {' '.join(cmd)}[/]")
        subprocess.run(cmd, check=True)
        console.print("[bold green]__pycache__ files cleaned successfully! 🧹[/]")
    except subprocess.CalledProcessError as e:
        console.print("[bold red]Failed to clean __pycache__ files ❌[/]", e)
        return False


@app.command(help="Generate DBML diagram from database")
def dbml(
    output: str = typer.Option(
        "database.dbml", "--output", "-o", help="Output DBML file path"
    ),
    host: str = typer.Option(_PG_HOST, "--host", help="Database host"),
    port: int = typer.Option(_PG_PORT, "--port", help="Database port"),
    user: str = typer.Option(_PG_USER, "--user", help="Database user"),
    db: str = typer.Option(_PG_DB, "--db", help="Database name"),
    password: str = typer.Option(_PG_PASSWORD, "--password", help="Database password"),
):
    """
    Generate a DBML diagram file from the database schema using db2dbml.

    Requires: npm install -g dbdocs

    Examples:
        $ eylo dbml
        $ eylo dbml --output schema.dbml
        $ eylo dbml --host prod-db.example.com --db mydb
    """
    console.print("[bold blue]Generating DBML from database...[/]")

    connection_string = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    cmd = ["dbdocs", "db2dbml", "postgres", connection_string, "-o", output]

    try:
        # Mask password in displayed command
        display_conn = f"postgresql://{user}:****@{host}:{port}/{db}"
        display_cmd = ["dbdocs", "db2dbml", "postgres", display_conn, "-o", output]
        console.print(f"[dim]Running: {' '.join(display_cmd)}[/]")
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        console.print("[bold red]Failed to generate DBML ❌[/]", e)
        return False
    except FileNotFoundError:
        console.print(
            "[bold red]dbdocs not found. Install it with: npm install -g dbdocs[/]"
        )
        return False

    console.print(f"[bold green]DBML generated successfully! 🚀[/]")
    console.print(f"[dim]Output: {output}[/]")


############
## UTILS
############
SCRIPT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)  # Assuming main.py is in the cli directory
PROJECT_ROOT = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..")
)  # Project root is one level up from cli

EYLO_DOCKER_COMPOSE_FILE = os.path.join(
    PROJECT_ROOT, "docker", "eylo", "docker-compose.yml"
)
WEBRTC_DOCKER_COMPOSE_FILE = os.path.join(
    PROJECT_ROOT, "docker", "webrtc", "docker-compose.yml"
)


def docker_compose(args, stream_output=False):
    """Run a docker-compose command with the specified arguments"""
    docker_compose_file = EYLO_DOCKER_COMPOSE_FILE

    cmd = ["docker", "compose", "-f", docker_compose_file] + args

    try:
        if stream_output:
            # Stream output directly to console
            console.print(f"[dim]Running: {' '.join(cmd)}[/]")
            result = subprocess.run(cmd, check=True)
            return True
        else:
            # Capture output for processing
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return result
    except subprocess.CalledProcessError as e:
        if not stream_output and hasattr(e, "stderr"):
            error_message = e.stderr if e.stderr else str(e)
            console.print(f"[bold red]Error executing command:[/] {' '.join(cmd)}")
            console.print(f"[red]{error_message}[/]")
        return False


############
## DEPLOYMENTS
############


@app.command(help="Check current deployment version on S3")
def check_deployment(
    app_name: str = typer.Argument(..., help="Application name: widget"),
    bucket: Optional[str] = typer.Option(
        None, help="S3 bucket name", envvar="AWS_S3_BUCKET"
    ),
    bucket_path: str = typer.Option(
        "eylo-widget",
        help="S3 bucket path prefix",
        envvar="AWS_S3_BUCKET_PATH_WIDGET",
    ),
    profile: Optional[str] = typer.Option(
        None, help="AWS profile to use", envvar="AWS_PROFILE"
    ),
    region: str = typer.Option("us-east-1", help="AWS region", envvar="AWS_REGION"),
):
    """
    Check the current deployment version and metadata for an application on S3.

    Example:
        $ eylo check-deployment widget
    """
    from deploy_frontend import get_s3_deployment_info
    from datetime import datetime

    if not bucket:
        console.print("[bold red]AWS_S3_BUCKET environment variable is required[/]")
        return False

    app_configs = {
        "widget": {
            "bucket": bucket,
            "bucket_path": bucket_path,
        },
    }

    if app_name not in app_configs:
        console.print(
            f"[bold red]Unknown app: {app_name}. Valid options: {', '.join(app_configs.keys())}[/]"
        )
        return False

    config = app_configs[app_name]
    console.print(f"[bold blue]Checking deployment info for {app_name}...[/]")

    info = get_s3_deployment_info(
        bucket=config["bucket"],
        bucket_path=config["bucket_path"],
        profile=profile,
        region=region,
    )

    if info:
        console.print(f"[bold green]Deployment Info for {app_name}:[/]")
        console.print(f"  Version: [cyan]{info['version']}[/]")

        # Format timestamp if available
        if info["timestamp"] != "unknown":
            try:
                ts = int(info["timestamp"])
                dt = datetime.fromtimestamp(ts)
                console.print(
                    f"  Deployed: [cyan]{dt.strftime('%Y-%m-%d %H:%M:%S')}[/]"
                )
            except:
                console.print(f"  Timestamp: [cyan]{info['timestamp']}[/]")

        console.print(f"  ETag: [cyan]{info['etag']}[/]")
        console.print(f"  Last Modified: [cyan]{info['last_modified']}[/]")
        return True
    else:
        console.print(f"[bold red]Failed to get deployment info for {app_name}[/]")
        return False


@app.command(help="Build widget and copy to server/static/widget")
def build_and_copy_widget():
    """
    Build widget for server deployment.

    This command:
    1. Removes server/static/widget
    2. Cleans widget directory (removes node_modules, dist)
    3. Runs pnpm install && pnpm build in widget
    4. Cleans widget/preact-ui directory (removes node_modules, dist)
    5. Runs pnpm install && pnpm build in widget/preact-ui
    6. Copies widget/preact-ui/dist to server/static/widget

    Example:
        $ eylo build-and-copy-widget
    """
    import shutil
    from pathlib import Path

    console.print("[bold blue]Building widget for server deployment...[/]")

    # Step 1: Remove server/static/widget
    widget_static_path = Path(PROJECT_ROOT) / "server" / "static" / "widget"
    if widget_static_path.exists():
        console.print(f"[dim]Removing {widget_static_path}[/]")
        shutil.rmtree(widget_static_path)

    # Step 2: Clean widget directory
    widget_path = Path(PROJECT_ROOT) / "widget"
    console.print("[dim]Cleaning widget directory...[/]")

    widget_node_modules = widget_path / "node_modules"
    widget_dist = widget_path / "dist"

    if widget_node_modules.exists():
        console.print(f"[dim]Removing {widget_node_modules}[/]")
        shutil.rmtree(widget_node_modules)
    if widget_dist.exists():
        console.print(f"[dim]Removing {widget_dist}[/]")
        shutil.rmtree(widget_dist)

    # Step 3: Install and build widget
    try:
        console.print("[dim]Running pnpm install in widget...[/]")
        subprocess.run(["pnpm", "install"], check=True, cwd=widget_path)

        console.print("[dim]Running pnpm build in widget...[/]")
        subprocess.run(["pnpm", "build"], check=True, cwd=widget_path)
    except subprocess.CalledProcessError as e:
        console.print("[bold red]Failed to build widget ❌[/]")
        return False

    # Step 4: Clean widget/preact-ui directory
    preact_ui_path = widget_path / "preact-ui"
    console.print("[dim]Cleaning widget/preact-ui directory...[/]")

    preact_node_modules = preact_ui_path / "node_modules"
    preact_dist = preact_ui_path / "dist"

    if preact_node_modules.exists():
        console.print(f"[dim]Removing {preact_node_modules}[/]")
        shutil.rmtree(preact_node_modules)
    if preact_dist.exists():
        console.print(f"[dim]Removing {preact_dist}[/]")
        shutil.rmtree(preact_dist)

    # Step 5: Install and build widget/preact-ui
    try:
        console.print("[dim]Running pnpm install in widget/preact-ui...[/]")
        subprocess.run(["pnpm", "install"], check=True, cwd=preact_ui_path)

        console.print("[dim]Running pnpm build in widget/preact-ui...[/]")
        subprocess.run(["pnpm", "build"], check=True, cwd=preact_ui_path)
    except subprocess.CalledProcessError as e:
        console.print("[bold red]Failed to build preact-ui ❌[/]")
        return False

    # Step 6: Copy dist to server/static/widget
    console.print("[dim]Copying dist to server/static/widget...[/]")
    preact_dist_path = preact_ui_path / "dist"
    if preact_dist_path.exists():
        shutil.copytree(preact_dist_path, widget_static_path)
        console.print(
            "[bold green]Widget built and copied to server/static/widget successfully! 🚀[/]"
        )
        return True
    else:
        console.print("[bold red]Preact-ui dist directory not found ❌[/]")
        return False


@app.command(help="Deploy widget to S3 with CloudFront CDN (for third-party embedding)")
def deploy_widget(
    bucket: Optional[str] = typer.Option(
        None, help="S3 bucket name", envvar="AWS_S3_BUCKET"
    ),
    bucket_path: str = typer.Option(
        "eylo-widget",
        help="S3 bucket path prefix",
        envvar="AWS_S3_BUCKET_PATH_WIDGET",
    ),
    distribution_id: Optional[str] = typer.Option(
        None,
        help="CloudFront distribution ID for cache invalidation",
        envvar="AWS_CLOUDFRONT_DISTRIBUTION_ID_WIDGET",
    ),
    profile: Optional[str] = typer.Option(
        None, help="AWS profile to use", envvar="AWS_PROFILE"
    ),
    region: str = typer.Option("us-east-1", help="AWS region", envvar="AWS_REGION"),
    skip_build: bool = typer.Option(False, help="Skip building before deploy"),
):
    """
    Deploy widget to S3/CloudFront for third-party embedding with ETag-based caching.

    This ensures:
    - Fast loading via CloudFront CDN
    - Automatic cache invalidation with ETags
    - Fixed filename for third-party developers

    Examples:
        $ eylo deploy-widget
        $ eylo deploy-widget --skip-build
    """
    import shutil
    from pathlib import Path

    # Build widget if not skipped
    if not skip_build:
        console.print("[bold blue]Building widget...[/]")

        widget_path = Path(PROJECT_ROOT) / "widget"
        console.print("[dim]Cleaning widget directory...[/]")

        widget_node_modules = widget_path / "node_modules"
        widget_dist = widget_path / "dist"

        if widget_node_modules.exists():
            shutil.rmtree(widget_node_modules)
        if widget_dist.exists():
            shutil.rmtree(widget_dist)

        try:
            console.print("[dim]Running pnpm install in widget...[/]")
            subprocess.run(["pnpm", "install"], check=True, cwd=widget_path)

            console.print("[dim]Running pnpm build in widget...[/]")
            subprocess.run(["pnpm", "build"], check=True, cwd=widget_path)
        except subprocess.CalledProcessError:
            console.print("[bold red]Failed to build widget ❌[/]")
            return False

        preact_ui_path = widget_path / "preact-ui"
        console.print("[dim]Cleaning widget/preact-ui directory...[/]")

        preact_node_modules = preact_ui_path / "node_modules"
        preact_dist = preact_ui_path / "dist"

        if preact_node_modules.exists():
            shutil.rmtree(preact_node_modules)
        if preact_dist.exists():
            shutil.rmtree(preact_dist)

        try:
            console.print("[dim]Running pnpm install in widget/preact-ui...[/]")
            subprocess.run(["pnpm", "install"], check=True, cwd=preact_ui_path)

            console.print("[dim]Running pnpm build in widget/preact-ui...[/]")
            subprocess.run(["pnpm", "build"], check=True, cwd=preact_ui_path)
        except subprocess.CalledProcessError:
            console.print("[bold red]Failed to build preact-ui ❌[/]")
            return False

        console.print("[bold green]Widget built successfully! ✓[/]")

    # Deploy to S3/CloudFront with custom cache headers
    from deploy_frontend import deploy_widget_to_cdn

    return deploy_widget_to_cdn(
        bucket=bucket,
        bucket_path=bucket_path,
        distribution_id=distribution_id,
        build_dir="widget/preact-ui/dist",
        profile=profile,
        region=region,
        project_root=PROJECT_ROOT,
    )


############
## MAIN
############


def show_welcome():
    """Show a welcome message with available commands"""
    platform_info = platform.platform()
    console.print(
        Panel.fit(
            f"[bold green]Eylo Project CLI[/]\n"
            f"[blue]System: {platform_info}[/]\n"
            f"[blue]Project directory: {os.getcwd()}[/]\n"
            "\nAvailable commands:\n"
            "Docker commands:\n"
            "  • [bold]start[/]: Start Docker services\n"
            "  • [bold]stop[/]: Stop Docker services\n"
            "  • [bold]reset[/]: Reset Docker services\n"
            "  • [bold]build[/]: Build Docker services\n"
            "  • [bold]rebuild[/]: Re-build Docker services\n"
            "  • [bold]logs[/]: View Docker logs\n"
            "  • [bold]ssh[/]: SSH into a service container\n"
            "  • [bold]db[/]: Connect to the database\n"
            "\nDevelopment commands:\n"
            "  • [bold]backend[/]: Run backend server\n"
            "  • [bold]db[/]: Connect to database\n"
            "\nDatabase commands:\n"
            "  • [bold]prepare-seed-data[/]: Prepare seed data\n"
            "  • [bold]restore-seed-data[/]: Restore seed data\n"
            "\nUtility commands:\n"
            "  • [bold]pyclean[/]: Cleanup __pycache__ files\n"
            "\nOptions:\n"
            "  • Use [bold]start/stop --services[/] to target specific services\n"
            "  • Use [bold]backend --port[/] to customize backend server\n"
            "\nUse [bold]--help[/] with any command for more information",
            title="Welcome",
            border_style="blue",
        )
    )


@app.callback(invoke_without_command=True)
def root_command(
    context: typer.Context,
    base_url: Optional[str] = typer.Option(
        None,
        "--base-url",
        envvar="EYLO_BASE_URL",
        help="Override the configured API origin for this command",
    ),
    organization_id: Optional[str] = typer.Option(
        None,
        "--organization-id",
        "--org-id",
        envvar="EYLO_ORGANIZATION_ID",
        help="Override the configured organization UUID for this command",
    ),
    token: Optional[str] = typer.Option(
        None,
        "--token",
        envvar="EYLO_TOKEN",
        help="Override the stored bearer token; prefer EYLO_TOKEN to shell history",
    ),
):
    """Set shared API context and show orientation when no command is selected."""
    context.ensure_object(dict)["api_overrides"] = CliOverrides(
        base_url=base_url,
        organization_id=organization_id,
        token=token,
    )
    if context.invoked_subcommand is None:
        show_welcome()


register_api_commands(app, console)


if __name__ == "__main__":
    app()
