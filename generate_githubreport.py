#!/usr/bin/env python3

import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
import argparse

def load_contributions_data(data_file="reports/contributions_data.json"):
    """Load the contributions data from JSON file."""
    if not os.path.exists(data_file):
        raise FileNotFoundError(f"Data file {data_file} not found. Please run github_contributions.py first.")
    
    with open(data_file, 'r') as f:
        return json.load(f)

def generate_html_report(data, output_file="reports/github_report.html"):
    """Generate an interactive HTML report."""
    
    # Prepare data for visualizations
    contributors = data['contributors']
    daily_contributions = data['daily_contributions']
    user_profiles = data['user_profiles']
    
    # Sort contributors by total contributions
    sorted_contributors = sorted(contributors.items(), key=lambda x: x[1]['contributions'], reverse=True)
    
    # Calculate total contributions for percentage calculations
    total_contributions_count = sum(c['contributions'] for c in contributors.values())
    
    # Generate pie chart data with percentages
    pie_data = []
    colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#FF6B6B', '#4ECDC4']
    for i, (username, contrib_data) in enumerate(sorted_contributors):  # All contributors
        percentage = (contrib_data['contributions'] / total_contributions_count * 100) if total_contributions_count > 0 else 0
        pie_data.append({
            'label': contrib_data['name'],
            'value': contrib_data['contributions'],
            'percentage': round(percentage, 1),
            'color': colors[i % len(colors)],
            'username': username
        })
    
    # Generate time series data for aggregate contributions
    all_dates = set()
    for user_daily in daily_contributions.values():
        all_dates.update(user_daily.keys())
    
    if all_dates:
        start_date = min(all_dates)
        end_date = max(all_dates)
        
        # Create daily aggregates
        daily_totals = defaultdict(int)
        for user, user_daily in daily_contributions.items():
            for date, count in user_daily.items():
                daily_totals[date] += count
        
        # Generate complete date range
        current_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        timeline_data = []
        while current_date <= end_dt:
            date_str = current_date.strftime("%Y-%m-%d")
            timeline_data.append({
                'date': date_str,
                'total': daily_totals.get(date_str, 0)
            })
            current_date += timedelta(days=1)
    else:
        timeline_data = []
    
    # Prepare individual contributor data
    individual_data = {}
    for username, user_daily in daily_contributions.items():
        if username in user_profiles:
            individual_data[username] = {
                'name': user_profiles[username]['name'],
                'total': contributors[username]['contributions'],
                'daily': user_daily
            }

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GitHub Contributions Report - {data['organization']}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f6f8fa;
            color: #24292e;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            padding: 30px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 1px solid #e1e4e8;
        }}
        .header h1 {{
            color: #2f363d;
            margin: 0 0 10px 0;
        }}
        .meta-info {{
            color: #586069;
            font-size: 14px;
        }}
        .chart-section {{
            margin: 40px 0;
            padding: 20px;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            background: #fafbfc;
        }}
        .chart-section h2 {{
            margin-top: 0;
            color: #2f363d;
        }}
        .chart-container {{
            position: relative;
            height: 400px;
            margin: 20px 0;
        }}
        .contributors-section {{
            margin-top: 40px;
        }}
        .contributor-list {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }}
        .contributor-card {{
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            padding: 15px;
            background: white;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .contributor-card:hover {{
            border-color: #0366d6;
            box-shadow: 0 2px 8px rgba(3,102,214,0.1);
        }}
        .contributor-card.selected {{
            border-color: #0366d6;
            background: #f1f8ff;
        }}
        .contributor-name {{
            font-weight: 600;
            margin-bottom: 5px;
        }}
        .contributor-stats {{
            color: #586069;
            font-size: 14px;
        }}
        .individual-chart {{
            display: none;
            margin-top: 30px;
        }}
        .individual-chart.active {{
            display: block;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: #f1f8ff;
            border: 1px solid #c8e1ff;
            border-radius: 6px;
            padding: 20px;
            text-align: center;
        }}
        .stat-number {{
            font-size: 32px;
            font-weight: bold;
            color: #0366d6;
            margin-bottom: 5px;
        }}
        .stat-label {{
            color: #586069;
            font-size: 14px;
        }}
        .contributors-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            background: white;
            border-radius: 6px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .contributors-table th,
        .contributors-table td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #e1e4e8;
        }}
        .contributors-table th {{
            background: #f6f8fa;
            font-weight: 600;
            color: #24292e;
        }}
        .contributors-table tr:last-child td {{
            border-bottom: none;
        }}
        .contributors-table tr:hover {{
            background: #f6f8fa;
        }}
        .percentage-bar {{
            background: #e1e4e8;
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 5px;
        }}
        .percentage-fill {{
            height: 100%;
            background: #0366d6;
            transition: width 0.3s ease;
        }}
        .timeline-controls {{
            margin-bottom: 20px;
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }}
        .filter-button {{
            padding: 8px 16px;
            border: 1px solid #e1e4e8;
            background: white;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }}
        .filter-button:hover {{
            border-color: #0366d6;
        }}
        .filter-button.active {{
            background: #0366d6;
            color: white;
            border-color: #0366d6;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>GitHub Contributions Report</h1>
            <div class="meta-info">
                Organization: <strong>{data['organization']}</strong><br>
                Period: {data['start_date'][:10]} to {data['end_date'][:10]}<br>
                Total Repositories: {data['total_repositories']}
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{len(contributors)}</div>
                <div class="stat-label">Active Contributors</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{sum(c['contributions'] for c in contributors.values())}</div>
                <div class="stat-label">Total Contributions</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{data['total_repositories']}</div>
                <div class="stat-label">Repositories</div>
            </div>
        </div>

        <div class="chart-section">
            <h2>Team Contribution Distribution</h2>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px; align-items: start;">
                <div>
                    <div class="chart-container" style="height: 300px;">
                        <canvas id="pieChart"></canvas>
                    </div>
                </div>
                <div>
                    <h3 style="margin-top: 0;">Contributors Summary</h3>
                    <table class="contributors-table">
                        <thead>
                            <tr>
                                <th>Rank</th>
                                <th>Name</th>
                                <th>Contributions</th>
                                <th>Percentage</th>
                            </tr>
                        </thead>
                        <tbody>
                            {generate_contributors_table(sorted_contributors, total_contributions_count)}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="chart-section">
            <h2>Contributions Over Time</h2>
            <div class="timeline-controls">
                <span style="font-weight: 600;">View:</span>
                <button class="filter-button active" data-filter="all">All Team</button>
                <button class="filter-button" data-filter="individual">Select Member</button>
                <select id="memberSelect" style="display: none; padding: 8px; border: 1px solid #e1e4e8; border-radius: 6px;">
                    <option value="">Choose a team member...</option>
                    {generate_member_options(sorted_contributors)}
                </select>
            </div>
            <div class="chart-container">
                <canvas id="timelineChart"></canvas>
            </div>
        </div>

        <div class="contributors-section">
            <h2>Team Members</h2>
            <p>Click on a team member to see their individual contribution timeline:</p>
            <div class="contributor-list">
                {generate_contributor_cards(sorted_contributors, user_profiles)}
            </div>
        </div>

        <div id="individualChart" class="individual-chart">
            <h3 id="individualTitle">Individual Contributions</h3>
            <div class="chart-container">
                <canvas id="individualTimelineChart"></canvas>
            </div>
        </div>
    </div>

    <script>
        // Data
        const pieData = {json.dumps(pie_data)};
        const timelineData = {json.dumps(timeline_data)};
        const individualData = {json.dumps(individual_data)};

        // Pie Chart
        const pieCtx = document.getElementById('pieChart').getContext('2d');
        new Chart(pieCtx, {{
            type: 'pie',
            data: {{
                labels: pieData.map(d => d.label),
                datasets: [{{
                    data: pieData.map(d => d.value),
                    backgroundColor: pieData.map(d => d.color),
                    borderWidth: 1,
                    borderColor: '#fff'
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'right'
                    }},
                    tooltip: {{
                        callbacks: {{
                            label: function(context) {{
                                return context.label + ': ' + context.parsed + ' (' + pieData[context.dataIndex].percentage + '%)';
                            }}
                        }}
                    }}
                }}
            }}
        }});

        // Timeline Chart
        const timelineCtx = document.getElementById('timelineChart').getContext('2d');
        let timelineChart = new Chart(timelineCtx, {{
            type: 'line',
            data: {{
                datasets: [{{
                    label: 'Team - Daily Contributions',
                    data: timelineData.map(d => ({{
                        x: d.date,
                        y: d.total
                    }})),
                    borderColor: '#0366d6',
                    backgroundColor: 'rgba(3, 102, 214, 0.1)',
                    fill: true,
                    tension: 0.1,
                    pointRadius: 2,
                    pointHoverRadius: 4
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{
                    intersect: false,
                    mode: 'index'
                }},
                scales: {{
                    x: {{
                        type: 'time',
                        time: {{
                            unit: 'day',
                            displayFormats: {{
                                day: 'MMM dd',
                                week: 'MMM dd',
                                month: 'MMM yyyy'
                            }},
                            tooltipFormat: 'MMM dd, yyyy'
                        }},
                        title: {{
                            display: true,
                            text: 'Date'
                        }}
                    }},
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Contributions'
                        }}
                    }}
                }},
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top'
                    }},
                    tooltip: {{
                        callbacks: {{
                            title: function(context) {{
                                return new Date(context[0].parsed.x).toLocaleDateString('en-US', {{
                                    weekday: 'short',
                                    year: 'numeric',
                                    month: 'short',
                                    day: 'numeric'
                                }});
                            }},
                            label: function(context) {{
                                return context.dataset.label + ': ' + context.parsed.y + ' contributions';
                            }}
                        }}
                    }}
                }}
            }}
        }});

        // Timeline filter functionality
        const filterButtons = document.querySelectorAll('.filter-button');
        const memberSelect = document.getElementById('memberSelect');

        filterButtons.forEach(button => {{
            button.addEventListener('click', function() {{
                filterButtons.forEach(btn => btn.classList.remove('active'));
                this.classList.add('active');
                
                const filter = this.dataset.filter;
                if (filter === 'individual') {{
                    memberSelect.style.display = 'block';
                }} else {{
                    memberSelect.style.display = 'none';
                    // Reset to show all team data
                    updateTimelineChart('all', null);
                }}
            }});
        }});

        memberSelect.addEventListener('change', function() {{
            const selectedMember = this.value;
            if (selectedMember) {{
                updateTimelineChart('individual', selectedMember);
            }} else {{
                updateTimelineChart('all', null);
            }}
        }});

        function updateTimelineChart(mode, username) {{
            let newData, newLabel, newColor;
            
            if (mode === 'individual' && username && individualData[username]) {{
                const userData = individualData[username];
                const userDates = Object.keys(userData.daily).sort();
                
                if (userDates.length === 0) {{
                    console.log('No data for user:', username);
                    return;
                }}
                
                // Create complete date range for user with proper date objects
                const startDate = new Date(userDates[0]);
                const endDate = new Date(userDates[userDates.length - 1]);
                const completeUserData = [];
                
                for (let d = new Date(startDate); d <= endDate; d.setDate(d.getDate() + 1)) {{
                    const dateStr = d.toISOString().split('T')[0];
                    completeUserData.push({{
                        x: dateStr,
                        y: userData.daily[dateStr] || 0
                    }});
                }}
                
                newData = completeUserData;
                newLabel = `${{userData.name}} - Daily Contributions`;
                newColor = '#28a745';
            }} else {{
                // Use team data with proper x,y format
                newData = timelineData.map(d => ({{
                    x: d.date,
                    y: d.total
                }}));
                newLabel = 'Team - Daily Contributions';
                newColor = '#0366d6';
            }}
            
            timelineChart.data.datasets[0].data = newData;
            timelineChart.data.datasets[0].label = newLabel;
            timelineChart.data.datasets[0].borderColor = newColor;
            timelineChart.data.datasets[0].backgroundColor = newColor.replace('#', 'rgba(').replace(')', ', 0.1)').replace('#0366d6', 'rgba(3, 102, 214, 0.1)').replace('#28a745', 'rgba(40, 167, 69, 0.1)');
            timelineChart.update();
        }}

        // Individual contributor selection and chart
        let individualChart = null;
        const contributorCards = document.querySelectorAll('.contributor-card');
        const individualChartDiv = document.getElementById('individualChart');
        const individualTitle = document.getElementById('individualTitle');

        contributorCards.forEach(card => {{
            card.addEventListener('click', function() {{
                // Remove previous selection
                contributorCards.forEach(c => c.classList.remove('selected'));
                
                // Select current card
                this.classList.add('selected');
                
                // Get username
                const username = this.dataset.username;
                const userData = individualData[username];
                
                if (userData) {{
                    // Show individual chart
                    individualChartDiv.classList.add('active');
                    individualTitle.textContent = `${{userData.name}} - Individual Contributions`;
                    
                    // Prepare data for individual chart
                    const userDates = Object.keys(userData.daily).sort();
                    const userContributions = userDates.map(date => ({{
                        date: date,
                        count: userData.daily[date]
                    }}));
                    
                    // Destroy existing chart
                    if (individualChart) {{
                        individualChart.destroy();
                    }}
                    
                    // Create new chart
                    const individualCtx = document.getElementById('individualTimelineChart').getContext('2d');
                    individualChart = new Chart(individualCtx, {{
                        type: 'bar',
                        data: {{
                            labels: userContributions.map(d => d.date),
                            datasets: [{{
                                label: 'Contributions',
                                data: userContributions.map(d => d.count),
                                backgroundColor: '#28a745',
                                borderColor: '#22863a',
                                borderWidth: 1
                            }}]
                        }},
                        options: {{
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {{
                                x: {{
                                    type: 'time',
                                    time: {{
                                        unit: 'day',
                                        displayFormats: {{
                                            day: 'MMM dd'
                                        }}
                                    }}
                                }},
                                y: {{
                                    beginAtZero: true
                                }}
                            }},
                            plugins: {{
                                legend: {{
                                    display: false
                                }}
                            }}
                        }}
                    }});
                }}
            }});
        }});
    </script>
</body>
</html>
"""
    
    # Write the HTML file
    with open(output_file, 'w') as f:
        f.write(html_content)
    
    return output_file

def generate_contributor_cards(sorted_contributors, user_profiles):
    """Generate HTML for contributor cards."""
    cards_html = ""
    for rank, (username, contrib_data) in enumerate(sorted_contributors, 1):
        if username in user_profiles:
            profile = user_profiles[username]
            rank_color = "#1a73e8" if rank <= 3 else "#5f6368"
            cards_html += f"""
                <div class="contributor-card" data-username="{username}">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div class="contributor-name">{profile['name']}</div>
                        <span style="color: {rank_color}; font-weight: bold; font-size: 18px;">#{rank}</span>
                    </div>
                    <div class="contributor-stats">
                        @{username} • {contrib_data['contributions']} contributions
                    </div>
                </div>
            """
    return cards_html

def generate_contributors_table(sorted_contributors, total_contributions_count):
    """Generate HTML for contributors table with percentages."""
    table_html = ""
    for rank, (username, contrib_data) in enumerate(sorted_contributors, 1):
        percentage = (contrib_data['contributions'] / total_contributions_count * 100) if total_contributions_count > 0 else 0
        rank_color = "#1a73e8" if rank <= 3 else "#5f6368"
        table_html += f"""
            <tr>
                <td><span style="color: {rank_color}; font-weight: bold;">#{rank}</span></td>
                <td><strong>{contrib_data['name']}</strong></td>
                <td>{contrib_data['contributions']:,}</td>
                <td>
                    {percentage:.1f}%
                    <div class="percentage-bar">
                        <div class="percentage-fill" style="width: {percentage}%"></div>
                    </div>
                </td>
            </tr>
        """
    return table_html

def generate_member_options(sorted_contributors):
    """Generate HTML options for member selection dropdown."""
    options_html = ""
    for rank, (username, contrib_data) in enumerate(sorted_contributors, 1):
        options_html += f'<option value="{username}">#{rank} {contrib_data["name"]} ({contrib_data["contributions"]} contributions)</option>'
    return options_html

def main():
    parser = argparse.ArgumentParser(description='Generate GitHub contributions HTML report')
    parser.add_argument('--data', default='reports/contributions_data.json',
                       help='Path to contributions data JSON file')
    parser.add_argument('--output', default='reports/github_report.html',
                       help='Output HTML file path')
    
    args = parser.parse_args()
    
    try:
        # Load data
        print(f"Loading contributions data from {args.data}...")
        data = load_contributions_data(args.data)
        
        # Generate report
        print(f"Generating HTML report...")
        output_file = generate_html_report(data, args.output)
        
        print(f"✅ Report generated successfully: {output_file}")
        print(f"📊 Found {len(data['contributors'])} contributors")
        print(f"📈 Total contributions: {sum(c['contributions'] for c in data['contributors'].values())}")
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("Please run github_contributions.py first to generate the data file.")
    except Exception as e:
        print(f"❌ Error generating report: {e}")

if __name__ == "__main__":
    main()