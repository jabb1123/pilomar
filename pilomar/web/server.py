#!/usr/bin/env python3
"""FastAPI web server for Pilomar telescope control.

Exposes the Application's core operations via a browser UI using HTMX
for lightweight, no-JS-framework interactivity.

Usage (via __main__.py):
    python pilomar/app/main.py --web [--port PORT]

Direct run (development):
    from pilomar.web.server import create_app, run
    from pilomar.app.main import Application
    app_instance = Application(project_root)
    app_instance.initialize()
    fastapi_app = create_app(app_instance)
    run(fastapi_app, port=8080)
"""

from __future__ import annotations

import collections
import datetime
import glob
import io
import mimetypes
import os
import threading
import traceback
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")


# ---------------------------------------------------------------------------
# Shared operation state (one active long-running task at a time)
# ---------------------------------------------------------------------------

class _OpState:
    """Thread-safe record of the current background operation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.running: bool = False
        self.description: str = ""
        self.result: str = ""
        self.error: str = ""
        self._log_ring: collections.deque[str] = collections.deque(maxlen=200)

    def start(self, description: str) -> None:
        with self._lock:
            self.running = True
            self.description = description
            self.result = ""
            self.error = ""

    def finish(self, result: str = "OK") -> None:
        with self._lock:
            self.running = False
            self.result = result

    def fail(self, error: str) -> None:
        with self._lock:
            self.running = False
            self.error = error

    def append_log(self, line: str) -> None:
        with self._lock:
            self._log_ring.append(line)

    def recent_log(self) -> list[str]:
        with self._lock:
            return list(self._log_ring)

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "running": self.running,
                "description": self.description,
                "result": self.result,
                "error": self.error,
            }


def create_app(pilomar_app: Any) -> FastAPI:  # pilomar_app: pilomar.app.main.Application
    """Create and return the FastAPI application bound to *pilomar_app*."""

    app = FastAPI(title="Pilomar Web UI", docs_url=None, redoc_url=None)
    templates = Jinja2Templates(directory=_TEMPLATES_DIR)
    op = _OpState()

    # ------------------------------------------------------------------
    # Helper: build status dict consumed by templates / JSON endpoint
    # ------------------------------------------------------------------

    def _status() -> dict:
        ctx = pilomar_app.ctx
        params = ctx.parameters

        target_name: str = "None"
        if ctx.target:
            target_name = (
                ctx.target.get("name", str(ctx.target))
                if isinstance(ctx.target, dict)
                else str(ctx.target)
            )

        motor_info: dict = {}
        if ctx.direct_driver is not None:
            d = ctx.direct_driver
            motor_info = {
                "mode": "direct GPIO",
                "az_deg": round(d.az_degrees(), 2),
                "alt_deg": round(d.alt_degrees(), 2),
                "tracking": ctx.direct_tracker is not None
                and getattr(ctx.direct_tracker, "running", False),
            }
        elif ctx.motor_controls:
            motor_info = {"mode": "microcontroller", "az_deg": None, "alt_deg": None}
        else:
            motor_info = {"mode": "none"}

        location: str = "Not set"
        if params and params.home_lat:
            location = f"{params.home_lat}, {params.home_lon or ''}"

        utc_now = datetime.datetime.now(datetime.timezone.utc)

        return {
            "target": target_name,
            "location": location,
            "utc": utc_now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "camera": "connected" if ctx.camera else "not connected",
            "motor": motor_info,
            "session": "active" if ctx.session else "none",
            "op": op.to_dict(),
        }

    # ------------------------------------------------------------------
    # Helper: resolve a searchgroup/searchterm to a Skyfield handle
    # and set ctx.target
    # ------------------------------------------------------------------

    def _set_target(searchgroup: str, searchterm: str) -> str | None:
        """Set ctx.target; return None on success or an error string."""
        ctx = pilomar_app.ctx
        tc = pilomar_app._target_chooser  # noqa: SLF001

        try:
            if searchgroup == "solar" and tc is not None:
                result = tc.choose_solar(prechosen=searchterm.lower())
                if result:
                    ctx.target = result
                    return None
                return f"Unknown solar body: {searchterm}"

            if searchgroup in ("messier", "ngc", "hipparcos") and tc is not None:
                chooser_map = {
                    "messier": tc.choose_messier,
                    "ngc": tc.choose_ngc,
                    "hipparcos": tc.choose_hipparcos,
                }
                result = chooser_map[searchgroup](prechosen=searchterm)
                if result:
                    ctx.target = result
                    return None
                return f"Target not found: {searchterm}"

            if searchgroup == "radec":
                # searchterm = "RA,Dec" e.g. "18.615,38.784"
                parts = searchterm.split(",")
                if len(parts) != 2:
                    return "radec searchterm must be 'ra_hours,dec_degrees'"
                ra, dec = float(parts[0].strip()), float(parts[1].strip())
                if tc is not None:
                    result = tc.radec_object(
                        prechosen=f"ra 0 {int(ra)} {(ra % 1)*60:.0f} 0.0 dec {int(dec)} 0 0.0"
                    )
                    if result:
                        ctx.target = result
                        return None
                # Fallback: store coords without handle
                ctx.target = {
                    "name": f"RA {ra:.3f}h Dec {dec:.3f}°",
                    "searchgroup": "radec",
                    "searchterm": searchterm,
                }
                return None

            if searchgroup == "altaz":
                parts = searchterm.split(",")
                if len(parts) != 2:
                    return "altaz searchterm must be 'alt_deg,az_deg'"
                alt, az = float(parts[0].strip()), float(parts[1].strip())
                ctx.target = {
                    "name": f"ALT {alt:.1f}° AZ {az:.1f}°",
                    "searchgroup": "altaz",
                    "searchterm": searchterm,
                }
                return None

        except Exception as exc:  # pylint: disable=broad-except
            return f"Error setting target: {exc}"

        return f"Unsupported searchgroup: {searchgroup}"

    # ------------------------------------------------------------------
    # Background task runners
    # ------------------------------------------------------------------

    def _run_goto() -> None:
        op.start("GOTO target")
        try:
            pilomar_app._goto_target_direct()  # noqa: SLF001
            op.finish("Slew complete")
        except Exception as exc:  # pylint: disable=broad-except
            op.fail(str(exc))
            op.append_log(traceback.format_exc())

    def _run_home() -> None:
        op.start("Home altitude axis")
        try:
            ctx = pilomar_app.ctx
            if ctx.direct_driver is not None:
                ctx.direct_driver.home_altitude()
                op.finish("Homing complete")
            else:
                op.fail("No direct driver available")
        except Exception as exc:  # pylint: disable=broad-except
            op.fail(str(exc))

    def _run_observation() -> None:
        op.start("Observation run")
        try:
            pilomar_app._start_observation_run()  # noqa: SLF001
            op.finish("Observation complete")
        except Exception as exc:  # pylint: disable=broad-except
            op.fail(str(exc))

    # ------------------------------------------------------------------
    # Routes — full pages
    # ------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return templates.TemplateResponse(
            request,
            "index.html",
            {"status": _status()},
        )

    # ------------------------------------------------------------------
    # Routes — HTMX partials (return fragments for hx-get/hx-post swap)
    # ------------------------------------------------------------------

    @app.get("/partials/status", response_class=HTMLResponse)
    async def partial_status(request: Request):
        return templates.TemplateResponse(
            request,
            "partials/status.html",
            {"status": _status()},
        )

    @app.get("/partials/log", response_class=HTMLResponse)
    async def partial_log(request: Request):
        lines = op.recent_log()
        # Also pull from pilomar log file if available
        ctx = pilomar_app.ctx
        if ctx.main_log and hasattr(ctx.main_log, "_buffer"):
            lines = list(ctx.main_log._buffer)[-100:] + lines  # noqa: SLF001
        return templates.TemplateResponse(
            request,
            "partials/log.html",
            {"lines": lines[-50:]},
        )

    # ------------------------------------------------------------------
    # Routes — API actions (return partial status fragment so HTMX can
    #           update the status panel without a full page reload)
    # ------------------------------------------------------------------

    @app.post("/api/target", response_class=HTMLResponse)
    async def api_set_target(
        request: Request,
        background_tasks: BackgroundTasks,
        searchgroup: str = Form(...),
        searchterm: str = Form(...),
    ):
        err = _set_target(searchgroup, searchterm)
        status = _status()
        status["flash"] = err if err else f"Target set: {searchterm}"
        status["flash_ok"] = err is None
        return templates.TemplateResponse(
            request,
            "partials/status.html",
            {"status": status},
        )

    @app.post("/api/goto", response_class=HTMLResponse)
    async def api_goto(request: Request, background_tasks: BackgroundTasks):
        if op.running:
            status = _status()
            status["flash"] = "Another operation is already running."
            status["flash_ok"] = False
            return templates.TemplateResponse(
                request, "partials/status.html", {"status": status}
            )
        if pilomar_app.ctx.target is None:
            status = _status()
            status["flash"] = "No target selected."
            status["flash_ok"] = False
            return templates.TemplateResponse(
                request, "partials/status.html", {"status": status}
            )
        background_tasks.add_task(_run_goto)
        status = _status()
        status["flash"] = "Slew started…"
        status["flash_ok"] = True
        return templates.TemplateResponse(
            request, "partials/status.html", {"status": status}
        )

    @app.post("/api/home", response_class=HTMLResponse)
    async def api_home(request: Request, background_tasks: BackgroundTasks):
        if op.running:
            status = _status()
            status["flash"] = "Another operation is already running."
            status["flash_ok"] = False
            return templates.TemplateResponse(
                request, "partials/status.html", {"status": status}
            )
        background_tasks.add_task(_run_home)
        status = _status()
        status["flash"] = "Homing altitude axis…"
        status["flash_ok"] = True
        return templates.TemplateResponse(
            request, "partials/status.html", {"status": status}
        )

    @app.post("/api/observation/start", response_class=HTMLResponse)
    async def api_obs_start(request: Request, background_tasks: BackgroundTasks):
        if op.running:
            status = _status()
            status["flash"] = "Another operation is already running."
            status["flash_ok"] = False
            return templates.TemplateResponse(
                request, "partials/status.html", {"status": status}
            )
        if pilomar_app.ctx.target is None:
            status = _status()
            status["flash"] = "No target selected."
            status["flash_ok"] = False
            return templates.TemplateResponse(
                request, "partials/status.html", {"status": status}
            )
        background_tasks.add_task(_run_observation)
        status = _status()
        status["flash"] = "Observation started…"
        status["flash_ok"] = True
        return templates.TemplateResponse(
            request, "partials/status.html", {"status": status}
        )

    @app.post("/api/observation/stop", response_class=HTMLResponse)
    async def api_obs_stop(request: Request):
        ctx = pilomar_app.ctx
        if ctx.direct_tracker is not None:
            ctx.direct_tracker.stop()
        if op.running:
            # Signal the op to stop (if cooperative)
            op.finish("Stopped by user")
        status = _status()
        status["flash"] = "Observation / tracking stopped."
        status["flash_ok"] = True
        return templates.TemplateResponse(
            request, "partials/status.html", {"status": status}
        )

    @app.post("/api/tracking/start", response_class=HTMLResponse)
    async def api_tracking_start(request: Request):
        ctx = pilomar_app.ctx
        if ctx.direct_tracker is None:
            status = _status()
            status["flash"] = "No direct tracker available."
            status["flash_ok"] = False
            return templates.TemplateResponse(
                request, "partials/status.html", {"status": status}
            )
        try:
            ctx.direct_tracker.start()
            status = _status()
            status["flash"] = "Tracking started."
            status["flash_ok"] = True
        except RuntimeError as exc:
            status = _status()
            status["flash"] = str(exc)
            status["flash_ok"] = False
        return templates.TemplateResponse(
            request, "partials/status.html", {"status": status}
        )

    @app.post("/api/tracking/stop", response_class=HTMLResponse)
    async def api_tracking_stop(request: Request):
        ctx = pilomar_app.ctx
        if ctx.direct_tracker is not None:
            ctx.direct_tracker.stop()
        status = _status()
        status["flash"] = "Tracking stopped."
        status["flash_ok"] = True
        return templates.TemplateResponse(
            request, "partials/status.html", {"status": status}
        )

    # JSON fallback for scripts / curl
    @app.get("/api/status")
    async def api_status_json():
        return JSONResponse(_status())

    @app.get("/api/op")
    async def api_op_json():
        return JSONResponse(op.to_dict())

    # ------------------------------------------------------------------
    # Gallery helpers
    # ------------------------------------------------------------------

    def _image_root() -> Path | None:
        """Return the image root path from folder_handler or parameters."""
        ctx = pilomar_app.ctx
        if ctx.folder_handler is not None:
            return Path(ctx.folder_handler.image_root)
        if ctx.parameters is not None:
            p = ctx.parameters
            if getattr(p, "use_usb_storage", False):
                return Path(getattr(p, "usb_path", "/media/pi"))
            return Path(getattr(p, "sd_path", "/")) / "data"
        return None

    def _list_sessions() -> list[dict]:
        """Return sorted list of {campaign, session, path, count} dicts."""
        root = _image_root()
        if root is None:
            return []
        sessions = []
        for light_dir in sorted(
            glob.glob(str(root / "campaign_*" / "session_*" / "light")),
            reverse=True,
        ):
            p = Path(light_dir)
            jpgs = sorted(p.glob("*.jpg"), key=lambda f: f.stat().st_mtime, reverse=True)
            if not jpgs:
                continue
            sessions.append(
                {
                    "campaign": p.parent.parent.name,
                    "session": p.parent.name,
                    "path": str(p),
                    "count": len(jpgs),
                    "latest_mtime": jpgs[0].stat().st_mtime,
                }
            )
        return sessions

    def _session_images(campaign: str, session: str) -> list[dict]:
        """Return image metadata list for a specific session."""
        root = _image_root()
        if root is None:
            return []
        light_dir = root / campaign / session / "light"
        if not light_dir.exists():
            return []
        images = []
        for f in sorted(light_dir.glob("*.jpg"), key=lambda x: x.stat().st_mtime, reverse=True):
            stat = f.stat()
            images.append(
                {
                    "name": f.name,
                    "size_kb": round(stat.st_size / 1024),
                    "mtime": datetime.datetime.fromtimestamp(stat.st_mtime).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "campaign": campaign,
                    "session": session,
                }
            )
        return images

    # ------------------------------------------------------------------
    # Gallery routes
    # ------------------------------------------------------------------

    @app.get("/gallery", response_class=HTMLResponse)
    async def gallery_index(request: Request):
        sessions = _list_sessions()
        return templates.TemplateResponse(
            request, "gallery.html", {"sessions": sessions}
        )

    @app.get("/gallery/{campaign}/{session}", response_class=HTMLResponse)
    async def gallery_session(request: Request, campaign: str, session: str):
        images = _session_images(campaign, session)
        return templates.TemplateResponse(
            request,
            "gallery_session.html",
            {"campaign": campaign, "session": session, "images": images},
        )

    @app.get("/gallery/{campaign}/{session}/img/{filename}")
    async def gallery_image(campaign: str, session: str, filename: str):
        """Serve an individual JPG from the light folder."""
        root = _image_root()
        if root is None:
            return Response("Image root not configured", status_code=503)
        # Sanitise — only allow simple filenames with no path traversal
        fname = Path(filename).name
        if not fname.lower().endswith(".jpg"):
            return Response("Only .jpg files are served", status_code=400)
        img_path = root / campaign / session / "light" / fname
        if not img_path.exists():
            return Response("Not found", status_code=404)
        return FileResponse(str(img_path), media_type="image/jpeg")

    @app.get("/gallery/{campaign}/{session}/thumb/{filename}")
    async def gallery_thumb(campaign: str, session: str, filename: str):
        """Serve a scaled-down thumbnail (max 320 px wide)."""
        root = _image_root()
        if root is None:
            return Response("Image root not configured", status_code=503)
        fname = Path(filename).name
        if not fname.lower().endswith(".jpg"):
            return Response("Only .jpg files are served", status_code=400)
        img_path = root / campaign / session / "light" / fname
        if not img_path.exists():
            return Response("Not found", status_code=404)
        try:
            from PIL import Image as PilImage

            with PilImage.open(img_path) as im:
                im.thumbnail((320, 320))
                buf = io.BytesIO()
                im.save(buf, format="JPEG", quality=75)
                return Response(buf.getvalue(), media_type="image/jpeg")
        except ImportError:
            # Pillow not available — serve the full image
            return FileResponse(str(img_path), media_type="image/jpeg")

    return app


def run(fastapi_app: FastAPI, host: str = "0.0.0.0", port: int = 8080) -> None:
    """Start uvicorn serving *fastapi_app*.  Blocks until terminated."""
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError(
            "uvicorn is required for the web UI. Install it with: pip install uvicorn"
        ) from exc

    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")
