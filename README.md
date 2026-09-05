# TrustRail

**A spend-mandate protocol and agentic checkout layer, built on Razorpay.**

Track 01 — AI Growth & Agentic Commerce · Razorpay Buildathon

TrustRail lets an AI buyer and an AI merchant negotiate and settle a transaction with zero human clicks, and lets a human shop through conversation or voice, while every money-moving decision is checked by deterministic, non-LLM logic before a transaction is settled. LLMs propose. Code disposes.

Two commerce surfaces, one trust layer:

| Surface | Description |
|---|---|
| **Agent-to-Agent (B2B)** | An autonomous buyer AI negotiates directly with a merchant AI against a signed spend mandate. Discounts, bundles, and budget checks are enforced server-side, not by prompt. |
| **Conversational Checkout (B2C)** | A shopper talks or types to an AI storefront that builds a cart, pitches relevant upsells, and checks out through Razorpay, including a recovery flow if payment fails. |

Full technical breakdown, invariants, and the security model: [ARCHITECTURE.md](./ARCHITECTURE.md)

---

## Why this exists

LLMs hallucinate and can be prompt-injected. A system prompt that says "never discount more than 15%" is not a security boundary — it is a suggestion the model can be talked out of. TrustRail is built around one rule: no agent output reaches Razorpay without passing through a fixed set of pure-Python checks (hard caps, regex scrubs, threat classification, and a mandate bounds engine) that cannot be argued with, jailbroken, or socially engineered.

---

## Repository layout

This repository contains three deployable components:

| Component | Description | Port |
|---|---|---|
| `backend/` | FastAPI server — all agents, the bounds engine, Razorpay integration | 8001 |
| `frontend/` | Merchant storefront: catalog, chat/voice checkout, merchant config panel | 3000 |
| `frontend-buyer/` | Agent-to-agent demo UI: mandate configurator and live negotiation wire trace | 3001 |
| `scripts/` | `seed_demo.py` (resets demo state) and `buyer_agent_driver.py` (standalone CLI buyer agent) | — |

---

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/sarathcodes516/razorpay-ai-buildathon.git
cd razorpay-ai-buildathon

# backend
cd backend
pip install -r requirements.txt --break-system-packages
cd ..

# merchant storefront frontend
cd frontend
npm install
cd ..

# agent-to-agent buyer frontend
cd frontend-buyer
npm install
cd ..
```

### 2. Configure environment variables

Create a `.env` file inside `backend/` with the following:

```dotenv
RAZORPAY_KEY_ID=rzp_test_
RAZORPAY_KEY_SECRET=
OPENROUTER_API_KEY=
DEEPGRAM_API_KEY=
```

All four are free to generate for development and testing.

<details>
<summary><strong>RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET</strong></summary>

1. Create an account at [dashboard.razorpay.com/signup](https://dashboard.razorpay.com/signup)
2. Ensure the dashboard is in Test Mode (toggle in the top-left)
3. Go to Settings → API Keys, or navigate directly to [dashboard.razorpay.com/app/keys](https://dashboard.razorpay.com/app/keys)
4. Click Generate Test Key. Copy the Key ID (`rzp_test_...`) and Key Secret immediately — the secret is shown only once.

</details>

<details>
<summary><strong>OPENROUTER_API_KEY</strong></summary>

1. Create an account at [openrouter.ai](https://openrouter.ai)
2. Go to [openrouter.ai/keys](https://openrouter.ai/keys)
3. Click Create Key. No payment method is required to use free-tier models.
4. Copy the generated key (prefixed `sk-or-...`)

TrustRail defaults to the free `minimax/minimax-m3:free` model, set in `backend/app/agents/llm_client.py`. Any OpenRouter-hosted model can be used by changing that one constant.

</details>

<details>
<summary><strong>DEEPGRAM_API_KEY</strong></summary>

1. Create an account at [console.deepgram.com/signup](https://console.deepgram.com/signup) (includes free trial credits)
2. From the dashboard, open API Keys in the left sidebar
3. Click Create a New API Key, name it, and copy the generated value

</details>

### 3. Run the application

Three terminals are required:

```bash
# terminal 1 — backend (FastAPI, port 8001)
cd backend
uvicorn app.main:app --reload --port 8001

# terminal 2 — merchant storefront (port 3000)
cd frontend
npm run dev

# terminal 3 — agent-to-agent buyer UI (port 3001)
cd frontend-buyer
npm run dev
```

Optionally, seed demo catalog and campaign state before the first run:

```bash
python scripts/seed_demo.py
```

Then open:

- **http://localhost:3000** — the conversational storefront (B2C): browse, chat, or use voice to check out, with a merchant config tab for live policy, inventory, and campaign control.
- **http://localhost:3001** — the agent-to-agent demo (B2B): configure a spend mandate and observe a buyer AI negotiate live against the merchant AI, with a full signed wire trace.

A standalone CLI buyer agent is also available for testing outside the browser:

```bash
python scripts/buyer_agent_driver.py --mandate-id <man_xxx> --goal "<what to buy>"
```

---

## Running the tests

```bash
cd backend
pytest
```

29 tests covering bounds-engine rules, agent authentication, the discovery manifest, and the human-approval escalation flow.

---

## Design principles

- **Fail-closed by default.** Any LLM error, timeout, or malformed output resolves to the safe outcome — a rejected offer, never a fabricated one.
- **Nothing is trusted twice.** The settlement layer never re-reads a price or discount from what an LLM stated in chat; it re-derives all figures from the authoritative catalog and mandate state at the moment of payment.
- **Threats are demonstrable, not theoretical.** A prompt-injection attempt during negotiation (for example, instructing the merchant agent to ignore its policy) is flagged, capped, and logged in real time on the wire trace rather than silently blocked.
- **Cryptographic identity, not just API keys.** Discovery, the signed catalog, and settlement are all Ed25519-signed and independently verifiable by the counterparty before any figure is trusted.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.10) |
| LLM | OpenRouter (`minimax/minimax-m3:free`, swappable via one constant) |
| Payments | Razorpay Test Mode — real SDK calls, no mock fallback |
| Cryptography | Ed25519 (agent identity, catalog, settlement) and HMAC-SHA256 (mandates, payment verification) |
| Voice | Deepgram Nova-2, real-time STT over WebSocket |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Testing | pytest |

---

## API surface (selected)

| Method | Path | Purpose |
|---|---|---|
| GET | `/.well-known/trustrail-manifest.json` | Public discovery manifest — merchant public key, endpoints, mandate schema |
| GET | `/api/catalog/agent` | Ed25519-signed, machine-readable catalog |
| POST | `/api/gateway/negotiate` | Streaming B2B negotiation between buyer and merchant AI (NDJSON) |
| POST | `/api/mandate/dynamic` | Issue a signed spend mandate |
| POST | `/api/storefront/chat` | B2C conversational checkout |
| WS | `/api/voice/stream` | Browser-to-Deepgram voice bridge |
| POST | `/api/payments/verify` | Razorpay HMAC signature verification |
| POST | `/api/approvals/{cart_id}/approve` | Human approval for an escalated cart |

Full endpoint list and request/response shapes: [ARCHITECTURE.md](./ARCHITECTURE.md)

---

## Known limitations

Built for a time-boxed buildathon; the following are intentionally out of scope for now:

- In-memory state only — no database; all state resets on restart
- No authentication on the B2C conversational endpoints
- Single hardcoded merchant identity — not multi-tenant
- No CI pipeline configured

---

## License

Licensed under the [MIT License](./LICENSE).
