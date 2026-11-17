PROSPECT SUITE

app/        The platform. Python (Flask) server in app/app.py and app/lib,
            React + Vite client in app/client.
            Install: cd app && pip install -r requirements.txt
                     && npm install && npm run build && python server.py
            See app/README.md for setup, development, deployment and the data pipeline.

analysis/   The Python data pipeline: explore, clean, analyse (pandas, matplotlib).

docs/       CHANGELOG.md and notes from the earlier Prospect Ledger prototype,
            whose scoring and pipeline features now live inside the app.

presentation/   IOADA202_HARMACH_SOULAIMANE_VF.pptx, and build_deck.py which generates it
                (python-pptx).
