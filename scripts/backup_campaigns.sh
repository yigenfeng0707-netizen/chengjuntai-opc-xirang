#!/usr/bin/env bash
# 备份成军台战役与指标到 backups/YYYYMMDD
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DAY=$(date +%Y%m%d)
DEST="$ROOT/backups/$DAY"
mkdir -p "$DEST"
cp -a "$ROOT/content_factory/data/campaigns" "$DEST/" 2>/dev/null || true
cp -a "$ROOT/content_factory/data/campaign_metrics.json" "$DEST/" 2>/dev/null || true
cp -a "$ROOT/bid_telecom.db" "$DEST/" 2>/dev/null || true
echo "backup => $DEST"
