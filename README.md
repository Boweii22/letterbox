# Letterbox cloud demo

Source-linked letter explanations, speech and confirmed reminders. This package is prepared for Render’s free Docker web service, with Google’s free hosted Gemma 4 API. It is not deployed until a real public URL has been verified.

## Deploy
Publish this folder alone to GitHub. Create a Render Docker web service from that repository, select **Free**, and add `GEMMA_API_KEY` as a secret environment variable. Do not enable billing for Google or select paid Render plans. Render supplies `RENDER_EXTERNAL_HOSTNAME`; the app accepts that exact HTTPS origin. No Ollama server or developer laptop is needed.

## Privacy and limitations
Use fictional or redacted input. Photos/text go to Render for English Tesseract OCR. Only selected source sentences go to Google-hosted Gemma; Google’s free API may use submitted content to improve its products. Letterbox does not intentionally save letters, and temporary OCR files are deleted. Exact quotes, numeric checks and condition checks support review; they do not prove interpretation or OCR accuracy.

Free Render services sleep after 15 minutes idle and take roughly a minute to wake. Storage is ephemeral; local feedback and request counters can be lost on restart. Gemma is capped at 60 attempted requests per runtime day, plus per-visitor throttling and one expensive request at a time. This is a demo, not guaranteed always-on hosting or an absolute usage ceiling. There is no paid model fallback.

Optional sponsor secrets: `SENTRY_DSN`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `SERPAPI_API_KEY`, `MONGODB_URI`. Their quotas/credits are separate: leave paid provider keys unset when the account has no free allowance. Voice and official-source search require separate consent. Sentry/Atlas receive anonymous metrics only. Atlas needs approved hosting egress access. No credentials are included here.

The app code is MIT licensed; model/provider terms remain separate. Existing local Gemma and independently demonstrated Mastra/Temporal workflows remain in the full source package; this lightweight web deployment does not claim those workflows run in its container.
