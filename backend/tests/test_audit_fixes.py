"""Regression checks for the 2026-10 audit fixes (docs/audit-2026-10-08.md).

Run from the repo root:  venv/bin/python -m unittest backend.tests.test_audit_fixes -v
"""
import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import quote

from fastapi.testclient import TestClient

from backend.config import EXPORTS_DIR, UPLOADS_DIR, is_safe_media_path, media_ref_basename
from backend.main import app
from backend.schemas.render import RenderSettingsModel
from backend.services import download_service
from backend.utils.jobs import MAX_FINISHED_JOBS, prune_finished_jobs
from backend.utils.text import normalize_source_url


class PathGuardTests(unittest.TestCase):
    def test_basename_is_taken_after_decoding(self):  # F02
        self.assertEqual(media_ref_basename("/api/video/" + quote("../../outside.txt", safe="")), "outside.txt")
        self.assertEqual(media_ref_basename("/api/video/upload_ab12_clip.mp4?t=1"), "upload_ab12_clip.mp4")

    def test_safe_media_path(self):
        self.assertTrue(is_safe_media_path(UPLOADS_DIR / "x.mp4"))
        self.assertFalse(is_safe_media_path(UPLOADS_DIR / ".." / ".." / ".." / "x.mp4"))
        self.assertFalse(is_safe_media_path("/etc/hostname"))

    def test_raw_download_never_copies_files_outside_media_dirs(self):  # F02
        with tempfile.TemporaryDirectory() as outside:
            secret = Path(outside) / "secret.txt"
            secret.write_text("not for download")
            rel = Path("..") / ".." / ".." / ".." / ".." / ".." / ".." / ".." / ".." / secret.relative_to("/")
            v_url = "http://example.invalid/" + quote(str(rel), safe="")
            job_id = "test-traversal"
            out_path = EXPORTS_DIR / "test_traversal_raw.mp4"
            download_service.raw_download_jobs[job_id] = {"status": "starting"}
            try:
                with mock.patch.object(download_service, "download_full_raw_video", side_effect=RuntimeError("offline")):
                    asyncio.run(download_service.run_raw_download_job(job_id, v_url, str(out_path), out_path.name))
                self.assertEqual(download_service.raw_download_jobs[job_id]["status"], "failed")
                self.assertFalse(out_path.exists())
            finally:
                download_service.raw_download_jobs.pop(job_id, None)
                out_path.unlink(missing_ok=True)

    def test_render_settings_only_accept_uploaded_files(self):  # F05
        self.assertIsNone(RenderSettingsModel(bgm_file_path="/etc/hostname").bgm_file_path)
        self.assertIsNone(RenderSettingsModel(watermark_file_path=str(UPLOADS_DIR / ".." / ".." / "cookies.txt")).watermark_file_path)
        inside = str(UPLOADS_DIR / "bgm_1234_song.mp3")
        self.assertEqual(RenderSettingsModel(hook_sfx_file_path=inside).hook_sfx_file_path, inside)


class RequestGuardTests(unittest.TestCase):
    # POST to an unknown batch: 404 when the request passes the guards, so a failing guard changes nothing on disk.
    URL = "/api/render-batch/does-not-exist/retry"

    def setUp(self):
        env = mock.patch.dict(os.environ, {"CHEAT_CLIP_API_KEY": "", "ADMIN_API_KEY": ""})
        env.start()
        self.addCleanup(env.stop)
        self.client = TestClient(app, base_url="http://localhost")

    def test_cross_site_post_is_blocked(self):  # F04
        r = self.client.post(self.URL, headers={"Origin": "https://example.com"})
        self.assertEqual(r.status_code, 403)

    def test_local_frontend_post_is_allowed(self):
        for origin in ("http://localhost:5173", "http://127.0.0.1:8000"):
            self.assertEqual(self.client.post(self.URL, headers={"Origin": origin}).status_code, 404)
        self.assertEqual(self.client.post(self.URL).status_code, 404)  # non-browser clients send no Origin

    def test_foreign_host_header_is_rejected(self):  # F04 (DNS rebinding)
        self.assertEqual(self.client.get("/api/fonts", headers={"Host": "attacker.example"}).status_code, 400)
        self.assertEqual(self.client.get("/api/fonts").status_code, 200)


class AccessKeyTests(unittest.TestCase):  # F03
    KEY = "test-key-0123456789abcdef"

    def setUp(self):
        env = mock.patch.dict(os.environ, {"CHEAT_CLIP_API_KEY": self.KEY, "ADMIN_API_KEY": ""})
        env.start()
        self.addCleanup(env.stop)
        self.client = TestClient(app, base_url="http://localhost")

    def test_every_api_call_needs_the_key(self):
        self.assertEqual(self.client.get("/api/fonts").status_code, 401)
        self.assertEqual(self.client.get("/api/fonts", headers={"X-API-Key": self.KEY}).status_code, 200)
        self.assertEqual(self.client.get("/api/fonts", headers={"Authorization": f"Bearer {self.KEY}"}).status_code, 200)
        self.assertEqual(self.client.get("/api/fonts", headers={"X-API-Key": "wrong"}).status_code, 401)
        self.assertEqual(self.client.get("/openapi.json").status_code, 401)
        self.assertEqual(self.client.get("/api/health").status_code, 200)  # exempt for health checks

    def test_ui_session_cookie(self):
        self.assertEqual(self.client.get("/api/auth/status").json(), {"required": True, "authenticated": False})
        self.assertEqual(self.client.post("/api/auth/session", json={"key": "wrong"}).status_code, 401)
        r = self.client.post("/api/auth/session", json={"key": self.KEY})
        self.assertEqual(r.status_code, 200)
        cookie = r.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=strict", cookie)
        self.assertNotIn(self.KEY.lower(), cookie)  # derived token, never the raw key
        # The client keeps the cookie like a browser: <video>, EventSource and downloads need no header.
        self.assertEqual(self.client.get("/api/fonts").status_code, 200)
        self.assertTrue(self.client.get("/api/auth/status").json()["authenticated"])

    def test_admin_endpoint_accepts_header_or_session(self):
        url = "/api/cleanup-expired-temp?max_age_hours=1000000"  # deletes nothing younger than ~114 years
        self.assertEqual(self.client.post(url).status_code, 401)
        self.assertEqual(self.client.post(url, headers={"X-API-Key": self.KEY}).status_code, 200)
        self.client.post("/api/auth/session", json={"key": self.KEY})
        self.assertEqual(self.client.post(url).status_code, 200)


class EmojiFontTests(unittest.TestCase):
    def test_bundled_emoji_renders_in_color_at_any_size(self):  # F18
        from backend.video_engine import render_emoji_image
        for size in (40, 85, 120):
            im = render_emoji_image("\U0001F525", size)
            self.assertIsNotNone(im, "no usable color emoji font")
            self.assertLess(abs(im.width - size), size * 0.5)
            colors = {px[:3] for px in im.get_flattened_data() if px[3] > 0} if hasattr(im, "get_flattened_data") \
                else {px[:3] for px in im.getdata() if px[3] > 0}
            self.assertGreater(len(colors), 10)  # color glyph, not a monochrome outline


class HelperTests(unittest.TestCase):
    def test_normalize_source_url(self):  # F16
        self.assertEqual(normalize_source_url("https://youtu.be/abc", "abc"), "https://youtu.be/abc")
        self.assertEqual(normalize_source_url("", "upload_12ab"), "/api/video/upload_12ab")
        self.assertEqual(normalize_source_url("dQw4w9WgXcQ", None), "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(normalize_source_url("garbage", "dQw4w9WgXcQ"), "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(normalize_source_url(None, None), "")

    def test_prune_keeps_running_jobs(self):  # F13
        jobs = {f"done{i}": {"status": "ready"} for i in range(MAX_FINISHED_JOBS + 5)}
        jobs["running"] = {"status": "downloading"}
        linked = {k: object() for k in jobs}
        prune_finished_jobs(jobs, lambda j: j["status"] == "ready", linked)
        self.assertEqual(len(jobs), MAX_FINISHED_JOBS + 1)
        self.assertIn("running", jobs)
        self.assertNotIn("done0", jobs)
        self.assertNotIn("done0", linked)


if __name__ == "__main__":
    unittest.main()
