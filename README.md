Reddit-to-Shorts Content Automation EngineAn autonomous Python pipeline that transforms trending Reddit debates into high-retention, fully rendered vertical videos (YouTube Shorts) with human-like AI voiceovers, topic-specific dynamic backgrounds, and animated data charts.

[Reddit API Ingestion] 
       │
[Divergence Modeling] ──> [Gemini AI Analysis]
                                │
[YouTube Shorts Upload] <── [MoviePy Video Render] <── [Kokoro AI Voice]

✨ Key FeaturesSmart Data Filtering: Automatically fetches high-friction discussions from Reddit based on a custom conflict-scoring math engine.Upstream Data Fixes: Uses Google Gemini to classify arguments into clean statistics, directly in Google Sheets to prevent video rendering bugs.Local Offline Voice AI: Uses an ultra-lightweight open-source voice model (Kokoro-ONNX) running natively on your CPU with custom pacing adjustments for snappy delivery.Dynamic Video Canvas: Combines custom topic-specific AI artwork backgrounds, animated horizontal parallax panning, and clean metric pie charts into a perfect 1080x1920 portrait short.Auto-Cleanup Hygiene: Vaporizes all temporary background images and sliced .wav audio clips the exact millisecond a video finishes rendering to save drive space.Set-and-Forget Uploads: Programmatically authenticates via Google OAuth v2 to stream completed video files straight to your YouTube Shorts grid, tracking pipeline status back to Google Sheets.
