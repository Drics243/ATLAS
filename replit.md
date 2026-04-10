# Workspace

## Overview

pnpm workspace monorepo using TypeScript, plus a Python Telegram bot (ATLAS 1.0 / BUAT SENDIRI).

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5
- **Database**: PostgreSQL + Drizzle ORM
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)

## Python Telegram Bot (ATLAS 1.0 / BUAT SENDIRI)

### Purpose
A Telegram trading signal bot that analyzes forex, indices, metals, energy, crypto, and Solana meme coins.

### Files
- `main.py` — Bot entry point, handlers, ConversationHandler for equity flow
- `markets.py` — Complete market symbol mapping (300+ instruments) + `resolve_symbol()`
- `analyzer.py` — Yahoo Finance data fetching, DexScreener meme data, economic calendar
- `signals.py` — Technical analysis (EMA, RSI, ATR, swing levels, BUY/SELL/NO ENTRY logic)
- `ai_narrator.py` — AI narrative generation via Groq API (llama3-8b-8192)
- `history.py` — Per-user analysis history (last 10 entries)
- `user_session.py` — Session management stored in `sessions.json`
- `requirements.txt` — Python dependencies

### Required Environment Variables
- `TELEGRAM_BOT_TOKEN` — From @BotFather on Telegram
- `GROQ_API_KEY` — From console.groq.com (free tier available)

### Deployment Files
- `Procfile` — `worker: python main.py`
- `railway.json` — Railway deployment config
- `.env.example` — Template for required env vars

### Bot Commands
- `/start` — Welcome message
- `/analyze <pair>` — Full market analysis (triggers equity flow if first time)
- `/calendar` — Today's economic events
- `/calendar week` — Full week calendar
- `/history` — Last 10 analyses
- `/reset_profile` — Clear equity/game plan settings
- `/help` — Full guide

### Supported Markets
- Forex: 70+ pairs (major, minor, exotic)
- Metals: Gold, Silver, Platinum, Palladium, Copper
- Energy: WTI Oil, Brent, Natural Gas
- Indices: US (NAS100, US30, SPX500), Global (DAX, FTSE, Nikkei, etc.)
- Crypto CEX: BTC, ETH, SOL, BNB, XRP
- Meme coins: Any Solana contract address via DexScreener

### Python Dependencies
- `python-telegram-bot==20.7`
- `httpx~=0.25.2`
- `groq==0.9.0`
- `python-dotenv==1.0.0`

## TypeScript Key Commands

- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- `pnpm --filter @workspace/api-server run dev` — run API server locally

See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details.
