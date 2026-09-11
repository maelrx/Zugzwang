#!/bin/bash
cd /home/maelrx/Documents/ChatGPT/Zugzwang/out/zgx_full_correlation
RUN() { echo "$1|$2"; }
{
RUN ../gemini_fullgames/zgx-full-01-tactical-memory.pgn sf20/zgx-full-01-tactical-memory.json
RUN ../gemini_fullgames/zgx-full-02-spatial-ascii.pgn sf20/zgx-full-02-spatial-ascii.json
RUN ../gemini_fullgames/zgx-full-03-king-safety-history.pgn sf20/zgx-full-03-king-safety-history.json
RUN ../gemini_fullgames/zgx-full-04-grandmaster-black.pgn sf20/zgx-full-04-grandmaster-black.json
RUN ../gemini_fullgames/zgx-full-05-tactical-trio.pgn sf20/zgx-full-05-tactical-trio.json
RUN ../gemini_fullgames/zgx-muse-01-tactical-memory.pgn sf20/zgx-muse-01-tactical-memory.json
RUN ../gemini_fullgames/zgx-muse-02-spatial-ascii.pgn sf20/zgx-muse-02-spatial-ascii.json
RUN ../gemini_fullgames/zgx-muse-03-king-safety-history.pgn sf20/zgx-muse-03-king-safety-history.json
RUN ../gemini_fullgames/zgx-gemini-01-tactical-memory-v2.pgn sf20/zgx-gemini-01-tactical-memory-v2.json
RUN ../gemini_fullgames/zgx-gemini-02-king-safety-prophylaxis-v2.pgn sf20/zgx-gemini-02-king-safety-prophylaxis-v2.json
RUN ../gemini_fullgames/zgx-gemini-03-tactical-guardian-v2.pgn sf20/zgx-gemini-03-tactical-guardian-v2.json
RUN ../luna_fullgames/zgx-luna-01-guard.pgn sf20/zgx-luna-01-guard.json
RUN ../luna_fullgames/zgx-luna-02-deep-history.pgn sf20/zgx-luna-02-deep-history.json
RUN ../luna_fullgames/zgx-luna-03-sentinel-reply.pgn sf20/zgx-luna-03-sentinel-reply.json
RUN ../luna_fullgames/zgx-luna-04-rich-survival.pgn sf20/zgx-luna-04-rich-survival.json
RUN ../luna_fullgames/zgx-luna-05-tactical-memory.pgn sf20/zgx-luna-05-tactical-memory.json
RUN replay_pgn/zgx-glm-01-tactical-memory.pgn sf20/zgx-glm-01-tactical-memory.json
RUN replay_pgn/zgx-opus-01-tactical-memory.pgn sf20/zgx-opus-01-tactical-memory.json
RUN replay_pgn/zgx-opus-02-spatial-ascii.pgn sf20/zgx-opus-02-spatial-ascii.json
RUN replay_pgn/zgx-sonnet-01-tactical-uci.pgn sf20/zgx-sonnet-01-tactical-uci.json
RUN replay_pgn/zgx-muse-r2-01-guard-medium-snapshot.pgn sf20/zgx-muse-r2-01-snapshot.json
RUN ../arena/arena-20260909-005648-1882.pgn sf20/arena-20260909-005648-1882.json
RUN ../arena/arena-20260909-010415-6463.pgn sf20/arena-20260909-010415-6463.json
RUN ../arena/arena-20260909-010612-1101.pgn sf20/arena-20260909-010612-1101.json
RUN ../arena/arena-20260909-011111-9918.pgn sf20/arena-20260909-011111-9918.json
} > runlist.txt
cat runlist.txt | xargs -P 8 -I{} bash -c 'IFS="|" read -r pgn out <<< "{}"; uv run --project /home/maelrx/Documents/ChatGPT/Zugzwang python sf20_analyze.py "$pgn" "$out" >> batch.log 2>&1'
echo "BATCH DONE" >> batch.log
