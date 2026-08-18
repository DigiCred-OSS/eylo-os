"""Build and deployment helpers for Eylo frontend assets."""

import hashlib
import os
import time
from pathlib import Path
from typing import Optional

import boto3
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

console = Console()


def get_s3_deployment_info(
    bucket: str,
    bucket_path: str,
    profile: Optional[str] = None,
    region: str = "us-east-1",
) -> Optional[dict]:
    """Get deployment metadata from an S3 object (typically index.html).

    Returns dict with deployment-version and deployment-timestamp if available.
    """
    try:
        session_kwargs = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile

        session = boto3.Session(**session_kwargs)
        s3_client = session.client("s3")

        # Check index.html for deployment metadata
        s3_key = f"{bucket_path}/index.html" if bucket_path else "index.html"

        response = s3_client.head_object(Bucket=bucket, Key=s3_key)
        metadata = response.get("Metadata", {})

        return {
            "version": metadata.get("deployment-version", "unknown"),
            "timestamp": metadata.get("deployment-timestamp", "unknown"),
            "etag": response.get("ETag", "").strip('"'),
            "last_modified": response.get("LastModified"),
        }
    except Exception as e:
        console.print(f"[yellow]Could not fetch deployment info: {e}[/]")
        return None


def _get_content_type(file_path: Path) -> str:
    """Get content type based on file extension"""
    extension_map = {
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
        ".ttf": "font/ttf",
        ".eot": "application/vnd.ms-fontobject",
    }
    return extension_map.get(file_path.suffix.lower(), "application/octet-stream")


def deploy_widget_to_cdn(
    bucket: str,
    bucket_path: str,
    distribution_id: Optional[str],
    build_dir: str,
    profile: Optional[str] = None,
    region: str = "us-east-1",
    project_root: str = None,
):
    """Deploy widget to S3/CloudFront with ETag caching for third-party embedding.

    Uses Cache-Control headers with must-revalidate to ensure:
    - Fast loading via CloudFront caching
    - Automatic freshness checks with ETags
    - Fixed filenames for third-party developers
    """
    if project_root is None:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    build_path = Path(project_root) / build_dir

    # Check if build directory exists
    if not build_path.exists():
        console.print(f"[bold red]Build directory not found: {build_path} ❌[/]")
        console.print("[yellow]Tip: Run without --skip-build to build first[/]")
        return False

    # Initialize S3 client
    console.print("[bold blue]Uploading widget to S3 with ETag caching...[/]")
    try:
        session_kwargs = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile

        session = boto3.Session(**session_kwargs)
        s3_client = session.client("s3")

        # Generate deployment version hash from all file contents
        deployment_hash = hashlib.sha256()

        # Get all files to upload
        files_to_upload = []
        for root, _, files in os.walk(build_path):
            for file in files:
                local_path = Path(root) / file
                relative_path = local_path.relative_to(build_path)
                files_to_upload.append((local_path, str(relative_path)))

                # Add file content to deployment hash
                with open(local_path, "rb") as f:
                    deployment_hash.update(f.read())

        deployment_version = deployment_hash.hexdigest()[:12]
        deployment_timestamp = str(int(time.time()))

        console.print(f"[dim]Deployment version: {deployment_version}[/]")
        console.print(f"[dim]Deployment timestamp: {deployment_timestamp}[/]")

        # Check if this version is already deployed (skip unnecessary uploads)
        current_deployment = get_s3_deployment_info(
            bucket=bucket,
            bucket_path=bucket_path,
            profile=profile,
            region=region,
        )
        if current_deployment and current_deployment["version"] == deployment_version:
            console.print(
                f"[bold yellow]✓ Version {deployment_version} is already deployed. Skipping upload.[/]"
            )
            console.print(
                "[dim]Tip: Make changes to your widget code to trigger a new deployment[/]"
            )
            return True

        # Upload files with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            upload_task = progress.add_task(
                "[cyan]Uploading files...", total=len(files_to_upload)
            )

            for local_path, s3_key in files_to_upload:
                # Determine content type
                content_type = _get_content_type(local_path)
                extra_args = {
                    "ContentType": content_type,
                    "Metadata": {
                        "deployment-version": deployment_version,
                        "deployment-timestamp": deployment_timestamp,
                    },
                }

                # Set cache control for widget with ETag validation
                # Cache for 1 hour but must revalidate (uses ETag)
                extra_args["CacheControl"] = "public, max-age=3600, must-revalidate"

                # Prepend bucket_path if provided
                full_s3_key = f"{bucket_path}/{s3_key}" if bucket_path else s3_key

                s3_client.upload_file(
                    str(local_path), bucket, full_s3_key, ExtraArgs=extra_args
                )
                progress.update(upload_task, advance=1)

        s3_location = (
            f"s3://{bucket}/{bucket_path}/" if bucket_path else f"s3://{bucket}/"
        )
        console.print(
            f"[bold green]Uploaded {len(files_to_upload)} files to {s3_location} ✓[/]"
        )

        if distribution_id:
            console.print("[bold blue]Invalidating CloudFront cache...[/]")
            try:
                cloudfront_client = session.client("cloudfront")
                invalidation = cloudfront_client.create_invalidation(
                    DistributionId=distribution_id,
                    InvalidationBatch={
                        "Paths": {"Quantity": 1, "Items": ["/*"]},
                        "CallerReference": str(time.time()),
                    },
                )
                invalidation_id = invalidation["Invalidation"]["Id"]
                console.print(
                    "[bold green]CloudFront invalidation created: "
                    f"{invalidation_id} ✓[/]"
                )
            except Exception as e:
                console.print(
                    "[bold yellow]Warning: Failed to invalidate CloudFront cache: "
                    f"{e}[/]"
                )
        else:
            console.print(
                "[dim]CloudFront distribution not configured; skipping invalidation.[/]"
            )

        console.print("[bold green]Widget deployment completed successfully! 🚀[/]")
        if distribution_id:
            console.print(
                "[dim]The fixed widget URL now benefits from CDN caching and "
                "ETag freshness.[/]"
            )
        else:
            console.print(
                "[dim]Uploaded assets use ETag cache validation; configure "
                "CloudFront to add CDN caching.[/]"
            )
        return True

    except Exception as e:
        console.print(f"[bold red]Deployment failed: {e} ❌[/]")
        return False
