"""
Perry's abilities — things he can do that aren't part of being Perry.

An ability is a separate program that lives beside the Perry folder, with
its own dependencies and its own environment. Perry knows how to find one
and start it; he doesn't import it. That boundary is the point:

    perry/                      <- the launcher folder
    ├── Perry/                  <- who he is: ears, voice, HUD, sessions
    └── scrooge/                <- what he can do: money

Keeping abilities out of Perry's own `.venv` is what stops a dashboard's
three hundred megabytes of pandas and Streamlit from slowing down a login
that has to feel instant. It also means an ability can break, or be deleted
entirely, without Perry noticing.

    scrooge     the money brain — portfolio, research, watchlist, income
"""
