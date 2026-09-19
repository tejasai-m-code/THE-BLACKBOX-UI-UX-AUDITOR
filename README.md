# Autonomous UI Auditor V14

Black-box agentic UI/UX, accessibility, inventory and regression auditor using FastAPI, Playwright and Gemini 2.5 Flash.

## Core loop

`OBSERVE → UNDERSTAND GOAL → CHECK VISIBLE EVIDENCE → PLAN → ACT → VERIFY ACTION → VERIFY GOAL → RECOVER → REPORT`

## Outcomes

- **SUCCESS** — exact requested product/constraints are observed and the requested workflow state is verified.
- **FAILED** — the requested workflow cannot be completed or verified.
- **OUT_OF_STOCK** — the exact requested inventory match exists but stock is zero.
- **UNAVAILABLE** — retained as a detailed reason under failed when no product satisfies the requested constraints.

## Run

From the project folder:

```powershell
python run.py
```

`run.py` automatically selects a free localhost port. If 8000 is already occupied, it uses the next available port and prints the dashboard URL.

Open the printed Dashboard URL.

## Optional Gemini

Create `.env`/environment variable:

```text
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.5-flash
```

The deterministic goal/state engine remains authoritative; Gemini is an assistive planner.

## Demo websites

- ShopEasy V1: `/target/v1`
- ShopEasy V2: `/target/v2`
- TechMart V1: `/target/tech/v1`
- TechMart V2: `/target/tech/v2`

## Main demo flow

1. Run V1 to establish a baseline.
2. Run V2 or use Compare V1 vs V2.
3. V2 is compared by normalized semantic checkpoints, not literal versioned URLs.
4. Use arbitrary natural-language goals.
5. Inspect SUCCESS / FAILED / OUT_OF_STOCK.
6. Open **VIEW FULL REPORT**.
7. Inspect multi-path exploration and prioritized remediation.

## Important design rule

Action verification and goal verification are separate. Typing text into a search field is not proof that the search succeeded. A product being present in a hidden/backend catalog is not proof that it was observed in the browser. Final success requires browser-observed evidence.
