# Ping Render keep‑alive URL every 5 minutes (and allow manual run)
# ضع هذا الملف في المسار: .github/workflows/keepalive-ping.yml
name: Keep Render Alive (ping)

on:
  schedule:
    - cron: "*/5 * * * *"   # كل 5 دقائق
  workflow_dispatch:        # يتيح التشغيل اليدوي من واجهة GitHub Actions

jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Ping render URL
        run: |
          URL="https://nerlma8alat.onrender.com/"
          echo "Pinging $URL"
          curl -fsS --max-time 10 "$URL" || (echo "Ping failed" && exit 1)
