# GitHub Leadership Analysis Tools

A comprehensive toolkit for analyzing team contributions across GitHub organizations. Generate detailed reports with interactive visualizations to understand team productivity, individual contributor patterns, and organization-wide development activity.

## Features

- **Comprehensive Data Collection**: Fetch commits, PRs created, PRs merged, and PR reviews from any GitHub organization
- **Interactive Reports**: HTML dashboards with sortable tables, interactive charts, and team member drill-downs
- **Advanced Analytics**: Statistical distribution analysis with outlier detection
- **User Management**: Hide/show team members with persistent local storage
- **Timeline Visualization**: Organization and individual daily contribution patterns
- **Resilient Processing**: State saving, resume functionality, and graceful interruption handling
- **Rate Limit Handling**: Exponential backoff with jitter for GitHub API throttling
- **Concurrent Processing**: Multi-threaded data collection for improved performance

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
3. Keep the token secure - you can set it as `GITHUB_TOKEN` environment variable or enter it when prompted

## Usage

### Step 1: Collect Contribution Data

```bash
# Using environment variable (recommended)
export GITHUB_TOKEN=your_token_here
python github_contributions.py

# Or let the script prompt you for the token
python github_contributions.py
```

**What it does:**
- Scans all repositories in the configured organization
- Collects commits, PRs created, PRs merged, and PR reviews
- Handles GitHub API rate limiting with exponential backoff
- Uses concurrent processing for improved performance
- Saves progress continuously and supports resume functionality
- Outputs: `output.csv` and `reports/contributions_data.json`

**Features:**
- **Progress Indicators**: Shows repository progress, contributor count, and ETA
- **State Management**: Automatically saves state and can resume if interrupted
- **Email Collection**: Gathers contributor email addresses for better identification
- **Graceful Interruption**: Press Ctrl+C to save progress and exit cleanly

**Configuration:**
- Edit `ORG_NAME` variable in the script to target your organization
- Default organization: `"heydovetail"`

### Step 2: Generate Interactive Report

```bash
python generate_githubreport.py
```

**What it does:**
- Reads data from `reports/contributions_data.json`
- Generates comprehensive interactive HTML report
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

The generated HTML report includes multiple interactive sections:

### 📊 **Team Overview Dashboard**
- **Statistics Cards**: Active contributors, total contributions, commits, PRs created, and PR reviews
- **Pie Chart**: Visual breakdown of team contributions with click-to-select functionality
- **Contributors Table**: Sortable table with detailed metrics and hide/show functionality

### 👥 **Interactive Contributors Table**
- **Sortable Columns**: Click any column header to sort (rank, name, total, commits, PRs, reviews, percentage)
- **User Management**: Hide users with the "−" button (appears on hover, positioned at row end)
- **Click Navigation**: Click any row to jump to that user's individual timeline
- **Persistent Settings**: Hidden users are saved in browser local storage
- **Smart Display Names**: Uses email prefixes when names are "N/A"
- **Tooltips**: Hover over names to see email addresses or GitHub usernames

### 📈 **Timeline Analysis**
- **Organization View**: Daily contributions across all team members
- **Individual Drill-down**: Select any team member from dropdown or pie chart
- **Interactive Controls**: Seamless switching between team and individual views
- **Smooth Navigation**: Automatic scrolling when selecting users from pie chart or table
- **Complete History**: Day-by-day activity tracking for the selected time period

### 📊 **Distribution Analysis (NEW)**
- **Statistical Histograms**: Four distribution charts for Total Contributions, Commits, PRs, and Reviews
- **Outlier Detection**: Automatically identifies and highlights statistical outliers in red
- **Statistical Summary**: Real-time display of mean, median, standard deviation, and outlier counts
- **Interactive Tooltips**: Hover over histogram bars to see detailed statistics
- **Professional Visualization**: Clean, responsive grid layout with consistent styling

### 🎯 **Advanced Features**
- **Local Storage Integration**: User preferences persist across browser sessions
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Performance Optimized**: Efficient data handling and chart rendering
- **Accessibility**: Proper ARIA labels and keyboard navigation support

## Data Collected

For each contributor, the system tracks:

- **Commits**: Direct code contributions to repositories
- **PRs Created**: Pull requests authored by the contributor
- **PRs Merged**: Pull requests that were successfully merged
- **PR Reviews**: Code reviews performed on other contributors' PRs
- **Email Addresses**: For better contributor identification
- **Daily Activity**: Granular day-by-day contribution tracking

## File Structure

```
leadership_tools/
├── github_contributions.py     # Data collection script with state management
├── generate_githubreport.py    # Advanced report generation script
├── CLAUDE.md                   # AI assistant guidance
├── README.md                   # This file
├── .gitignore                  # Git ignore rules
├── output.csv                  # CSV export (generated)
├── scan_state.pkl             # Resume state file (temporary)
├── reports/                    # Generated reports (ignored by git)
│   ├── contributions_data.json # Raw contribution data
│   └── github_report.html      # Interactive report
└── venv/                       # Python virtual environment
```

## Advanced Usage

### Resume Interrupted Scans
If data collection is interrupted, simply run the script again:
```bash
python github_contributions.py
```
The script will detect the saved state and offer to resume from where it left off.

### Environment Variables
```bash
# Set GitHub token (recommended for automation)
export GITHUB_TOKEN=your_token_here

# Run collection
python github_contributions.py
```

### Large Organizations
For organizations with many repositories and contributors:
- The script uses concurrent processing to improve speed
- Progress indicators show estimated completion time
- State is saved after each repository to prevent data loss
- API rate limiting is handled automatically

## Troubleshooting

### Common Issues

**"Module not found: github"**
```bash
# Make sure you're in the virtual environment
source venv/bin/activate
pip install PyGithub
```

**"Data file not found"**
- Run `github_contributions.py` first to collect data
- Check that `reports/contributions_data.json` exists

**"API rate limit exceeded"**
- The script handles this automatically with exponential backoff
- For very large organizations, collection may take several hours
- Consider running during off-peak hours for faster processing

**"Permission denied" errors**
- Ensure your GitHub token has appropriate repository access
- Check that the organization name is correct
- Verify the token hasn't expired

**Script appears frozen**
- Large repositories may take time to process
- Check the progress indicators for current status
- The script saves state continuously, so interruption is safe

### Performance Tips

**For Large Organizations:**
- Run during off-peak hours for better API performance
- Consider breaking analysis into smaller date ranges
- Use a dedicated machine that won't sleep during long runs

**For Better Reports:**
- Ensure contributor emails are available for better name display
- Hide inactive or former team members using the report's hide functionality
- Use the distribution analysis to identify contribution patterns

## Security Notes

- **Never commit your GitHub token** to version control
- Generated reports may contain sensitive team information
- The `.gitignore` file excludes reports and data files
- Review generated reports before sharing externally
- Local storage in browsers may contain user preferences

## Statistical Analysis

The distribution analysis uses standard statistical methods:

- **Outlier Detection**: Uses the IQR (Interquartile Range) method (1.5 × IQR beyond Q1/Q3)
- **Histogram Binning**: Automatically creates 10 bins based on data range
- **Statistical Measures**: Calculates mean, median, standard deviation, and quartiles
- **Visual Indicators**: Red bars indicate bins containing statistical outliers

This helps identify:
- High-performing contributors who significantly exceed team averages
- Distribution patterns (normal, skewed, bimodal)
- Team balance and specialization areas
- Potential areas for workload redistribution

## License

[Add your license information here]