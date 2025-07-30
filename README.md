# GitHub Leadership Analysis Tools

A comprehensive toolkit for analyzing team contributions across GitHub organizations. Generate detailed reports with interactive visualizations to understand team productivity, individual contributor patterns, and organization-wide development activity.

## Features

- **Data Collection**: Fetch contribution data from any GitHub organization
- **Interactive Reports**: HTML dashboards with charts and team member drill-downs
- **Contribution Analysis**: Pie charts, tables with percentages, and ranked contributors
- **Timeline Visualization**: Organization and individual daily contribution patterns
- **Flexible Date Ranges**: Analyze any time period (default: 6 months)

## Setup

### 1. Clone and Navigate
```bash
git clone <your-repo-url>
cd leadership_tools
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install PyGithub
```

### 4. GitHub Access Token
You'll need a GitHub Personal Access Token with repository access:

1. Go to GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token (classic) with `repo` scope
3. Keep the token secure - you'll enter it when running the collection script

## Usage

### Step 1: Collect Contribution Data

```bash
python github_contributions.py
```

**What it does:**
- Prompts for your GitHub personal access token
- Asks for date range (default: 6 months ago to today)
- Scans all repositories in the configured organization
- Outputs: `output.csv` and `reports/contributions_data.json`

**Configuration:**
- Edit `ORG_NAME` variable in the script to target your organization
- Default organization: `"heydovetail"`

### Step 2: Generate Interactive Report

```bash
python generate_githubreport.py
```

**What it does:**
- Reads data from `reports/contributions_data.json`
- Generates interactive HTML report
- Outputs: `reports/github_report.html`

**Custom options:**
```bash
# Use custom data file
python generate_githubreport.py --data custom_data.json

# Save to custom location
python generate_githubreport.py --output custom_report.html

# Both options
python generate_githubreport.py --data custom_data.json --output custom_report.html
```

## Report Features

The generated HTML report includes:

### 📊 **Contribution Distribution**
- **Pie Chart**: Visual breakdown of team contributions
- **Contributors Table**: Ranked list with names, contribution counts, and percentages
- **Visual Percentage Bars**: Easy comparison of contributor activity

### 📈 **Timeline Analysis**
- **Organization View**: Daily contributions across all team members
- **Individual Drill-down**: Select any team member to see their personal contribution pattern
- **Interactive Controls**: Switch between team and individual views
- **6-Month History**: Complete day-by-day activity tracking

### 👥 **Team Overview**
- **Ranked Contributors**: Clear hierarchy with #1, #2, #3 rankings
- **Clickable Team Cards**: Select members for individual timeline analysis
- **Summary Statistics**: Total contributors, contributions, and repositories

## File Structure

```
leadership_tools/
├── github_contributions.py     # Data collection script
├── generate_githubreport.py    # Report generation script
├── CLAUDE.md                   # AI assistant guidance
├── README.md                   # This file
├── .gitignore                  # Git ignore rules
├── output.csv                  # CSV export (generated)
├── reports/                    # Generated reports (ignored by git)
│   ├── contributions_data.json # Raw data
│   └── github_report.html      # Interactive report
└── venv/                       # Python virtual environment
```

## Troubleshooting

### Common Issues

**"Module not found: github"**
```bash
pip install PyGithub
```

**"Data file not found"**
- Run `github_contributions.py` first to collect data
- Check that `reports/contributions_data.json` exists

**"API rate limit exceeded"**
- GitHub has rate limits for API requests
- Wait and retry, or use a token with higher limits
- Large organizations may take time to process

**"Empty repository" errors**
- These are normal and automatically skipped
- Indicates repositories with no commits

### Configuration

**Change target organization:**
1. Edit `github_contributions.py`
2. Update `ORG_NAME = "your-org-name"`

**Analyze different time periods:**
- The script will prompt for custom date ranges
- Enter dates in YYYY-MM-DD format
- Press Enter to use default (6 months)

## Security Notes

- **Never commit your GitHub token** to version control
- Generated reports may contain sensitive team information
- The `.gitignore` file excludes reports and data files
- Review generated reports before sharing externally

## License

[Add your license information here]