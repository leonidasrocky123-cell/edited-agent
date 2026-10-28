# Edited! 🎬
> **Autonomous AI Video Editing Agent powered by Meta Muse**

Edited! is a lightweight, local-first AI video editing agent that transforms raw long-form footage into viral 9:16 short-form clips. Using Meta's Muse models (`muse-spark-1.3`), Edited! identifies conversational hooks, crops footage intelligently, animates dynamic captions, and generates platform-ready vertical video in seconds.

Built for the **Meta Global AI Developer Hackathon 2026**.

---

## ⚡ Key Features

- **🧠 Meta Muse Hook Detection:** Analyzes video transcripts and speech patterns using `muse-spark-1.3` to identify viral hook candidates, emotional peaks, and punchy cliffhangers.
- **🎙️ Zero-Cost Local Transcription:** Embedded speech-to-text powered by `faster-whisper` for word-accurate timestamps with zero external API fees or privacy exposure.
- **📐 Smart 9:16 Auto-Reframing:** High-performance FFmpeg pipeline supporting center-crop reframing and blurred cinematic side padding.
- **💬 Dynamic Caption Variations:**
  - **Bold Viral (Hormozi style):** High-contrast yellow punchwords with thick outlines in 2–3 word bursts.
  - **Clean Creator:** Minimalist crisp white subtitles at lower-third.
  - **Dark Box / Pill:** Semi-transparent high-contrast readable badges.
  - Customizable typography scale, vertical anchor (top / center / bottom), and casing.
- **🎯 Dynamic Camera Punch-In:** Configurable 2.5s opening hook zoom to immediately capture viewer attention.
- **🔒 Local-First & Privacy Preserving:** Video bytes never leave your workstation—inference stays focused on metadata and transcript planning.

---

## 🏗️ Architecture

