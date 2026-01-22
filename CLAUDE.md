\# Nursery Enrichment Pipeline



\## Quick Start

```bash

cd "C:\\Projects\_Local\\Sweet leaf sales\\nursery-enrichment-pipeline"

.\\venv\\Scripts\\Activate.ps1

py app.py

```

Then open http://127.0.0.1:5000



\## What This Is

Local Flask app that enriches nursery leads for B2B cold email outreach. Transforms Excel lists (business name + address) into scored, tiered, personalized leads ready for Instantly.ai.



\## Tech Stack

\- Python/Flask localhost app

\- SQLite database (data/leads.db)

\- Google Places API for business data

\- Google Gemini API for website analysis

\- Export to Instantly.ai CSV format



\## Project Structure

\- `app.py` - Main Flask application with all routes

\- `database/models.py` - SQLite schema and queries

\- `enrichment/` - Google Places, Gemini AI, web scraper, scorer

\- `exporters/` - Instantly.ai CSV export

\- `importers/` - Excel file import

\- `templates/` - HTML templates

\- `static/` - CSS/JS



\## Build Status

\- ✅ Phase 1-2: Foundation, Google Places enrichment

\- ✅ Phase 3-8: Scraping, AI enrichment, scoring, review UI, personalization, export

\- ⏳ Phase 9: Polish (error handling, rate limiting, logging)



\## Key URLs

\- Upload: http://127.0.0.1:5000/

\- Leads: http://127.0.0.1:5000/leads

\- Export: http://127.0.0.1:5000/export



\## Environment

Requires `.env` file with:

\- GOOGLE\_API\_KEY (Places API)

\- GEMINI\_API\_KEY

