# Perry Online

Jarvis-style personal finance assistant that runs in your phone's browser.

**Live:** https://basgoncalves.github.io/perry/

- **Perry chat** — type or speak ("How much did I spend on groceries last month?")
- **Spend** — import bank CSVs, auto-categorise, monthly budgets
- **Portfolio** — holdings, gains, optional live prices (free Finnhub key)
- **Market** — heatmap of the ~60 biggest US companies (size = value, colour = today's move) and the total market value over time. Data refreshed hourly by a GitHub Action (`market/build.py`).
- **Goals** — savings targets with projected finish dates
- **Invest** — growth calculator and comparison of investment options (education, not advice)

Privacy: all financial data is stored only in your browser (localStorage). Nothing is uploaded. Use Settings → Export backup to move data between devices.

Install on phone: open the link in Chrome → ⋮ → *Add to Home screen*.
