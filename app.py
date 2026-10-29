#!/usr/bin/env python3
"""
Edited! - Autonomous AI Video Editor Agent Web Application
Built for the Meta Global AI Developer Hackathon 2026
Theme: "Build for Your World"
Powered by Meta Muse Wonder 1.0 & FFmpeg
"""

import os
import sys
import json
import time
import uuid
import mimetypes
import shutil
import threading
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, SimpleHTTPRequestHandler

import cutter
import meta_agent

PORT = int(os.environ.get("PORT", 8000))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
CLIPS_DIR = os.path.join(BASE_DIR, "clips")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(CLIPS_DIR, exist_ok=True)


class EditedRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Enable CORS and caching headers
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            return self.serve_file(os.path.join(STATIC_DIR, "index.html"), "text/html")
        elif path.startswith("/static/"):
            rel_path = path[len("/static/"):]
            return self.serve_file(os.path.join(STATIC_DIR, rel_path))
        elif path.startswith("/uploads/"):
            rel_path = path[len("/uploads/"):]
            return self.serve_file(os.path.join(UPLOADS_DIR, rel_path))
        elif path.startswith("/clips/"):
            rel_path = path[len("/clips/"):]
            return self.serve_file(os.path.join(CLIPS_DIR, rel_path))
        elif path == "/api/status":
            api_key_set = bool(os.environ.get("MODEL_API_KEY", "").strip())
            payload = {
                "status": "ready",
                "ffmpeg_available": cutter.check_ffmpeg(),
                "meta_api_key_configured": api_key_set,
                "model": meta_agent.DEFAULT_MODEL,
                "hackathon_theme": "Build for Your World",
                "clips_count": len([f for f in os.listdir(CLIPS_DIR) if f.endswith(".mp4")])
            }
            return self.send_json(payload)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/upload":
            self.handle_upload()
        elif path == "/api/analyze":
            self.handle_analyze()
        elif path == "/api/cut":
            self.handle_cut()
        else:
            self.send_error(404, "Endpoint not found")

    def handle_upload(self):
        try:
            content_type = self.headers.get("Content-Type", "")
            content_length = int(self.headers.get("Content-Length", 0))

            if not content_type.startswith("multipart/form-data"):
                # Handle direct binary upload with filename in header
                filename = self.headers.get("X-Filename", f"upload_{int(time.time())}.mp4")
                # Sanitize filename
                clean_name = os.path.basename(filename).replace(" ", "_")
                file_path = os.path.join(UPLOADS_DIR, clean_name)
                
                with open(file_path, "wb") as f:
                    remaining = content_length
                    while remaining > 0:
                        chunk_size = min(65536, remaining)
                        data = self.rfile.read(chunk_size)
                        if not data:
                            break
                        f.write(data)
                        remaining -= len(data)

                info = cutter.get_video_info(file_path)
                return self.send_json({
                    "success": True,
                    "filename": clean_name,
                    "url": f"/uploads/{clean_name}",
                    "duration": info["duration"],
                    "width": info["width"],
                    "height": info["height"]
                })

            # Multipart parser
            boundary = content_type.split("boundary=")[1].encode()
            raw_data = self.rfile.read(content_length)

            parts = raw_data.split(b"--" + boundary)
            saved_filename = None
            for part in parts:
                if b'filename="' in part:
                    header_part, file_data = part.split(b"\r\n\r\n", 1)
                    # Strip trailing \r\n
                    file_data = file_data.rstrip(b"\r\n")
                    # Extract filename
                    h_lines = header_part.decode(errors="ignore")
                    for line in h_lines.splitlines():
                        if "filename=" in line:
                            fn = line.split('filename="')[1].split('"')[0]
                            saved_filename = f"{int(time.time())}_{os.path.basename(fn).replace(' ', '_')}"
                            dest = os.path.join(UPLOADS_DIR, saved_filename)
                            with open(dest, "wb") as f:
                                f.write(file_data)
                            break

            if saved_filename:
                dest = os.path.join(UPLOADS_DIR, saved_filename)
                info = cutter.get_video_info(dest)
                return self.send_json({
                    "success": True,
                    "filename": saved_filename,
                    "url": f"/uploads/{saved_filename}",
                    "duration": info["duration"],
                    "width": info["width"],
                    "height": info["height"]
                })
            else:
                return self.send_json({"error": "No valid video file uploaded"}, 400)

        except Exception as e:
            return self.send_json({"error": str(e)}, 500)

    def handle_analyze(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)

            filename = data.get("filename")
            user_transcript = data.get("transcript", "")
            api_key = data.get("api_key", "").strip() or None

            video_path = os.path.join(UPLOADS_DIR, filename)
            if not os.path.exists(video_path):
                return self.send_json({"error": "Video file not found"}, 404)

            info = cutter.get_video_info(video_path)
            duration = info.get("duration", 60.0)

            # If user didn't enter transcript, provide context from video file
            text_to_analyze = user_transcript
            if not text_to_analyze or len(text_to_analyze.strip()) < 10:
                text_to_analyze = f"Raw creator video footage recorded for Hive/social media. Filename: {filename}. Video length: {duration:.1f}s. Contains spoken founder/creator presentation, explaining the tool, why editing takes so long, and showing the demo."

            # Call Meta Agent
            analysis = meta_agent.analyze_video_transcript(
                transcript_or_description=text_to_analyze,
                video_duration_seconds=duration,
                api_key=api_key
            )

            return self.send_json({
                "success": True,
                "video_info": info,
                "analysis": analysis
            })

        except Exception as e:
            return self.send_json({"error": str(e)}, 500)

    def handle_cut(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)

            filename = data.get("filename")
            start_time = float(data.get("start_time", 0.0))
            end_time = float(data.get("end_time", 20.0))
            crop_mode = data.get("crop_mode", "crop_9_16")
            full_title = data.get("title", "") or ""
            caption = data.get("subtitle_text") or data.get("opening_quote") or data.get("caption") or ""
            hook_title = "".join(c for c in full_title.replace(" ", "_") if c.isalnum() or c == "_")[:20] or "clip"

            input_path = os.path.join(UPLOADS_DIR, filename)
            if not os.path.exists(input_path):
                return self.send_json({"error": "Original video not found"}, 404)

            clip_id = f"clip_{int(time.time())}_{hook_title}.mp4"
            output_path = os.path.join(CLIPS_DIR, clip_id)

            success = cutter.cut_vertical_clip(
                input_path=input_path,
                output_path=output_path,
                start_time=start_time,
                end_time=end_time,
                crop_mode=crop_mode,
                caption_text=caption,
                subtitle_style=data.get("subtitle_style", "bold_yellow"),
                enable_zoom=bool(data.get("enable_zoom", True)),
                enable_progress_bar=bool(data.get("enable_progress_bar", True)),
                auto_subtitles=bool(data.get("auto_subtitles", False)),
                subtitle_size=data.get("subtitle_size", "medium"),
                subtitle_position=data.get("subtitle_position", "bottom"),
                uppercase=bool(data.get("uppercase", True)),
                words_per_chunk=int(data.get("words_per_chunk", 3)),
            )

            if success:
                return self.send_json({
                    "success": True,
                    "clip_name": clip_id,
                    "clip_url": f"/clips/{clip_id}",
                    "duration": round(end_time - start_time, 1),
                    "crop_mode": crop_mode
                })
            else:
                return self.send_json({"error": "FFmpeg failed to process video clip"}, 500)

        except Exception as e:
            return self.send_json({"error": str(e)}, 500)

    def serve_file(self, full_path, content_type=None):
        if not os.path.exists(full_path):
            self.send_error(404, "File not found")
            return

        if not content_type:
            content_type, _ = mimetypes.guess_type(full_path)
            content_type = content_type or "application/octet-stream"

        file_size = os.path.getsize(full_path)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(file_size))
        self.end_headers()

        with open(full_path, "rb") as f:
            shutil.copyfileobj(f, self.wfile)

    def send_json(self, data, status_code=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_server():
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, EditedRequestHandler)
    print("=" * 60)
    print(" ⚡ Edited! - Meta AI Video Editor Agent")
    print(f" 🚀 Running at http://localhost:{PORT}")
    print(f" 🧠 Powered by Meta Muse Wonder 1.0 (dev.meta.ai)")
    print(f" 🎬 FFmpeg Engine: {'Active' if cutter.check_ffmpeg() else 'Missing'}")
    print("=" * 60)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Edited!] Server stopped gracefully.")


if __name__ == "__main__":
    run_server()
