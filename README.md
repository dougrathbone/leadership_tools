# GitHub Leadership Analysis Tools

A toolkit for analyzing team contributions across a GitHub organization. Collects commits, pull requests, and reviews, then generates an interactive HTML dashboard with team-wide and per-contributor breakdowns, PR cycle-time metrics, and statistical distribution analysis.

## Features

- **Comprehensive data collection**: commits, PRs created, PRs merged, PR reviews, and per-PR cycle times
- **Activity Score**: a single per-contributor metric (commits + reviews) that intentionally excludes PRs to avoid double-counting merged commits
- **Bot filtering**: `[bot]` accounts are excluded from reports by default (configurable)
- **Interactive HTML dashboard**: sortable tables, click-through pie chart, and a per-contributor detail modal
- **PR cycle-time analysis**: median time-to-merge per author with color-coded thresholds (<24h, <72h, ≥72h)
- **Reviewer ratio**: how much each contributor reviews relative to the PRs they create
- **Distribution analysis**: line-graph distributions for Activity Score, Commits, PRs, and Reviews with IQR-based outlier detection
- **Timeline drill-down**: org-wide daily activity plus per-contributor timelines, deep-linkable from the table or pie chart
- **Resilient data collection**: state file with resume support, graceful Ctrl+C handling, exponential-backoff rate-limit handling, and concurrent processing
- **Persistent UI preferences**: hidden contributors are remembered in browser local storage

## Setup

### 1. Clone

```bash
git clone https://github.com/dougrathbone/leadership_tools.git
cd leadership_tools
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install PyGithub
```

### 4. GitHub access token

You need a Personal Access Token with `repo` scope:

1. GitHub → Settings → Developer settings → Personal access tokens
2. Generate a new token (classic) with `repo` scope
3. Either export it as `GITHUB_TOKEN` or enter it when the script prompts

## Usage

### Step 1: Collect contribution data

```bash
export GITHUB_TOKEN=your_token_here
python github_contributions.py
```

What it does:

- Scans every repository in the configured organization
- Collects commits, PRs created, PRs merged, PR reviews, and PR cycle times
- Handles GitHub API rate limiting with exponential backoff and jitter
- Uses concurrent processing for speed
- Writes progress continuously and supports resume after interruption
- Outputs `output.csv` and `reports/contributions_data.json`

Configuration:

- Edit `ORG_NAME` near the top of `github_contributions.py` to target your organization
- Press Ctrl+C at any time to save state and exit cleanly; rerun the script to resume

### Step 2: Generate the interactive report

```bash
python generate_githubreport.py
```

What it does:

- Reads `reports/contributions_data.json`
- Renders a self-contained HTML report at `reports/github_report.html`

Custom paths:

```bash
python generate_githubreport.py --data custom_data.json --output custom_report.html
```

Bot filtering is controlled by the `EXCLUDE_BOTS` constant at the top of `generate_githubreport.py` (default: `True`).

## Report sections

### Team overview
- Summary cards: active contributors, Activity Score total, commits, PRs created, reviews
- Pie chart of contributor share, with click-through to that contributor's timeline
- Sortable contributors table (rank, name, Activity Score, PRs, reviews, cycle time, % share)

### Contributor detail modal
- Click any row or pie slice to open a modal with that contributor's full breakdown, ratios, and trends without leaving the dashboard

### PR cycle time
- Median time-to-merge per author, sorted ascending
- Bar color reflects threshold: green <24h, amber <72h, red ≥72h
- Authors with fewer than 2 merged PRs are omitted to keep the chart meaningful

### Reviewer ratio
- Reviews performed vs. PRs created per contributor, surfacing reviewers who carry more than they ship and vice versa

### Timeline analysis
- Org-wide daily contribution view
- Per-contributor drill-down via dropdown, pie chart, or table row
- Auto-scroll and deep-linkable selection

### Distribution analysis
- Line-graph distributions for Activity Score, Commits, PRs, and Reviews
- IQR-based outlier detection (1.5 × IQR beyond Q1/Q3) with mean, median, and standard deviation called out
- Hover for per-bin detail

## Data collected

For each contributor:

- Commits authored
- PRs created
- PRs merged
- PR reviews performed
- Per-PR cycle times (created → merged)
- Email address (when available, used to improve display names)
- Daily activity history

## File structure

```
leadership_tools/
├── github_contributions.py     # Data collection with state/resume
├── generate_githubreport.py    # HTML report generator
├── README.md
├── .gitignore
├── output.csv                  # Generated CSV export
├── scan_state.pkl              # Resume state (temporary, generated)
└── reports/                    # Generated outputs (gitignored)
    ├── contributions_data.json
    └── github_report.html
```

## Troubleshooting

**`ModuleNotFoundError: github`** — activate the virtual environment and `pip install PyGithub`.

**`Data file not found`** — run `github_contributions.py` first; confirm `reports/contributions_data.json` exists.

**Rate limit messages** — the collector backs off and resumes automatically. Large orgs may take hours; rerunning resumes from the last saved state.

**Permission errors** — confirm the token has `repo` scope, hasn't expired, and that `ORG_NAME` is correct.

**Apparent hang** — large repos take time. The console shows per-repo progress; state is checkpointed, so Ctrl+C is safe.

## Statistical methodology

- **Outlier detection**: IQR method, flagging values beyond Q1 − 1.5×IQR or Q3 + 1.5×IQR
- **Histogram binning**: 10 bins across the observed range
- **Summary stats**: mean, median, standard deviation, quartiles
- **Activity Score**: commits + reviews. PRs are deliberately excluded because merged PRs already manifest as commits, and counting both inflates contribution totals for PR-heavy authors.

## Security

- Never commit your GitHub token. Use `GITHUB_TOKEN` env var or the interactive prompt.
- Generated reports contain identifiable team data — review before sharing externally.
- `.gitignore` excludes `reports/` and the resume state file by default.

## License

Copyright (c) 2026 Doug Rathbone

Licensed under the MIT License. You may obtain a copy at https://opensource.org/licenses/MIT.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED.
