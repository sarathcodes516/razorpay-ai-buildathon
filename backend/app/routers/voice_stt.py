"""
voice_stt.py — WebSocket proxy between the browser and Deepgram's live STT API.

Architecture:
  Browser (mic audio as raw PCM)
      ↕  WebSocket  /api/voice/stream
  FastAPI (this file)
      ↕  WebSocket  wss://api.deepgram.com/v1/listen
  Deepgram Nova-2

The browser sends raw 16-bit PCM audio chunks; this proxy forwards them to
Deepgram and relays the transcript events back to the browser as JSON lines:
  {"type": "interim", "text": "i want a"}
  {"type": "final",   "text": "i want a beanie"}

Uses the raw `websockets` library instead of the Deepgram SDK because the SDK
is on a major version that has an incompatible async API with our stack.
"""
import asyncio
import json
import os

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")

# Deepgram streaming STT endpoint — Nova-2, auto-detect encoding (accepts WebM/Opus from browser)
DEEPGRAM_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?model=nova-2"
    "&language=en-US"
    "&smart_format=true"
    "&interim_results=true"
    "&endpointing=300"
)


@router.websocket("/api/voice/stream")
async def voice_stream(websocket: WebSocket):
    """
    Bidirectional proxy:
      - browser  → FastAPI: raw PCM bytes
      - Deepgram → FastAPI: JSON transcript events
      - FastAPI  → browser: {"type":"interim"|"final", "text":"..."}
    """
    await websocket.accept()

    if not DEEPGRAM_API_KEY:
        await websocket.send_text(
            json.dumps({"type": "error", "text": "DEEPGRAM_API_KEY not configured."})
        )
        await websocket.close()
        return

    try:
        async with websockets.connect(
            DEEPGRAM_URL,
            additional_headers={"Authorization": f"Token {DEEPGRAM_API_KEY}"},
            # Increase limits for audio payloads
            max_size=2 * 1024 * 1024,
        ) as dg_ws:

            async def browser_to_deepgram():
                """Forward raw PCM bytes from the browser to Deepgram."""
                try:
                    while True:
                        data = await websocket.receive_bytes()
                        await dg_ws.send(data)
                except WebSocketDisconnect:
                    pass
                except Exception:
                    pass
                finally:
                    # Tell Deepgram we're done sending audio
                    try:
                        await dg_ws.send(json.dumps({"type": "CloseStream"}))
                    except Exception:
                        pass

            async def deepgram_to_browser():
                """Relay Deepgram transcript events back to the browser."""
                try:
                    async for message in dg_ws:
                        evt = json.loads(message)
                        # Only forward speech events that have a transcript
                        channel = evt.get("channel", {})
                        alts = channel.get("alternatives", [])
                        if not alts:
                            continue
                        text = alts[0].get("transcript", "").strip()
                        if not text:
                            continue
                        is_final = evt.get("is_final", False)
                        await websocket.send_text(
                            json.dumps({
                                "type": "final" if is_final else "interim",
                                "text": text,
                            })
                        )
                except Exception:
                    pass

            # Run both directions concurrently; stop as soon as either finishes
            await asyncio.gather(
                browser_to_deepgram(),
                deepgram_to_browser(),
                return_exceptions=True,
            )

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_text(
                json.dumps({"type": "error", "text": str(exc)})
            )
        except Exception:
            pass
