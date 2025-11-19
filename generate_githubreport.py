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

def improve_display_name(name, email, username):
    """
    Improve display name by extracting from email if name is N/A.
    
    Args:
        name: The original name (might be "N/A")
        email: Email address (might be None)
        username: GitHub username as fallback
    
    Returns:
        Improved display name
    """
    if name and name != "N/A":
        return name
    
    # If we have an email, extract the part before @
    if email and "@" in email:
        email_prefix = email.split("@")[0]
        # Capitalize first letter and return with @ suffix to indicate it's from email
        return f"{email_prefix}@"
    
    # Fallback to username with @ suffix to indicate it's a username
    return f"{username}@"

def generate_html_report(data, output_file="reports/github_report.html"):
    """Generate an interactive HTML report."""
    
    # Prepare data for visualizations
    contributors = data['contributors']
    daily_contributions = data['daily_contributions']
    user_profiles = data['user_profiles']
    
    # Sort contributors by total contributions
    sorted_contributors = sorted(contributors.items(), key=lambda x: x[1]['total_contributions'], reverse=True)
    
    # Calculate total contributions for percentage calculations
    total_contributions_count = sum(c['total_contributions'] for c in contributors.values())
    
    # Generate pie chart data with percentages
    pie_data = []
    colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#FF6B6B', '#4ECDC4']
    for i, (username, contrib_data) in enumerate(sorted_contributors):  # All contributors
        percentage = (contrib_data['total_contributions'] / total_contributions_count * 100) if total_contributions_count > 0 else 0
        
        # Get improved display name
        profile = user_profiles.get(username, {})
        email = profile.get('email')
        display_name = improve_display_name(contrib_data['name'], email, username)
        
        pie_data.append({
            'label': display_name,
            'value': contrib_data['total_contributions'],
            'percentage': round(percentage, 1),
            'color': colors[i % len(colors)],
            'username': username,
            'commits': contrib_data.get('commits', 0),
            'prs_created': contrib_data.get('prs_created', 0),
            'prs_merged': contrib_data.get('prs_merged', 0),
            'prs_reviewed': contrib_data.get('prs_reviewed', 0)
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
            for date, metrics in user_daily.items():
                # Handle both old format (int) and new format (dict)
                if isinstance(metrics, dict):
                    total_day_contributions = (
                        metrics.get('commits', 0) + 
                        metrics.get('prs_created', 0) + 
                        metrics.get('prs_merged', 0) + 
                        metrics.get('prs_reviewed', 0)
                    )
                else:
                    # Backward compatibility with old format
                    total_day_contributions = metrics
                daily_totals[date] += total_day_contributions
        
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
            # Convert daily data to totals for individual charts
            daily_totals = {}
            for date, metrics in user_daily.items():
                if isinstance(metrics, dict):
                    daily_totals[date] = (
                        metrics.get('commits', 0) + 
                        metrics.get('prs_created', 0) + 
                        metrics.get('prs_merged', 0) + 
                        metrics.get('prs_reviewed', 0)
                    )
                else:
                    # Backward compatibility
                    daily_totals[date] = metrics
            
            # Get improved display name
            profile = user_profiles[username]
            email = profile.get('email')
            display_name = improve_display_name(profile['name'], email, username)
            
            individual_data[username] = {
                'name': display_name,
                'total': contributors[username]['total_contributions'],
                'daily': daily_totals,
                'detailed_daily': user_daily  # Keep detailed breakdown for tooltips
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
        
        /* Tooltip styles */
        .tooltip {{
            position: relative;
            cursor: help;
        }}
        .tooltip:hover::after {{
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: #24292e;
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            white-space: nowrap;
            z-index: 1000;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }}
        .tooltip:hover::before {{
            content: '';
            position: absolute;
            bottom: 94%;
            left: 50%;
            transform: translateX(-50%);
            border: 5px solid transparent;
            border-top-color: #24292e;
            z-index: 1000;
        }}
        
        /* Sortable table styles */
        .sortable-header {{
            cursor: pointer;
            user-select: none;
            position: relative;
            padding-right: 20px !important;
        }}
        .sortable-header:hover {{
            background: #e1e4e8;
        }}
        .sortable-header::after {{
            content: '↕️';
            position: absolute;
            right: 8px;
            top: 50%;
            transform: translateY(-50%);
            opacity: 0.5;
            font-size: 12px;
        }}
        .sortable-header.sort-asc::after {{
            content: '↑';
            opacity: 1;
            color: #0366d6;
        }}
        .sortable-header.sort-desc::after {{
            content: '↓';
            opacity: 1;
            color: #0366d6;
        }}
        
        /* Hide user functionality */
        .hide-user-btn {{
            background: #dc3545;
            color: white;
            border: none;
            border-radius: 50%;
            width: 20px;
            height: 20px;
            font-size: 12px;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
            opacity: 0;
            position: absolute;
            right: 5px;
            top: 50%;
            transform: translateY(-50%);
            z-index: 10;
        }}
        .hide-user-btn:hover {{
            background: #c82333;
            transform: translateY(-50%) scale(1.1);
        }}
        .contributors-table tr {{
            position: relative;
            cursor: pointer;
        }}
        .contributors-table td:last-child {{
            position: relative;
        }}
        .contributors-table tr:hover {{
            background-color: #f8f9fa;
        }}
        .contributors-table tr:hover .hide-user-btn {{
            opacity: 1;
        }}
        .hidden-user {{
            display: none !important;
        }}
        .show-all-btn {{
            background: #28a745;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .show-all-btn:hover {{
            background: #218838;
        }}
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}
        
        /* Make pie chart appear clickable */
        #pieChart {{
            cursor: pointer;
        }}
        #pieChart:hover {{
            opacity: 0.9;
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
                <div class="stat-number">{sum(c['total_contributions'] for c in contributors.values())}</div>
                <div class="stat-label">Total Contributions</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{sum(c.get('commits', 0) for c in contributors.values())}</div>
                <div class="stat-label">Commits</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{sum(c.get('prs_created', 0) for c in contributors.values())}</div>
                <div class="stat-label">PRs Created</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{sum(c.get('prs_reviewed', 0) for c in contributors.values())}</div>
                <div class="stat-label">PR Reviews</div>
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
                    <div class="section-header">
                        <h3 style="margin: 0;">Contributors Summary</h3>
                        <button class="show-all-btn" onclick="showAllUsers()" title="Show all hidden users">Show All</button>
                    </div>
                    <table class="contributors-table">
                        <thead>
                            <tr>
                                <th class="sortable-header" data-column="rank" data-type="number">Rank</th>
                                <th class="sortable-header" data-column="name" data-type="string">Name</th>
                                <th class="sortable-header" data-column="total" data-type="number">Total</th>
                                <th class="sortable-header" data-column="commits" data-type="number">Commits</th>
                                <th class="sortable-header" data-column="prs" data-type="number">PRs</th>
                                <th class="sortable-header" data-column="reviews" data-type="number">Reviews</th>
                                <th class="sortable-header" data-column="percentage" data-type="number">%</th>
                            </tr>
                        </thead>
                        <tbody>
                            {generate_contributors_table(sorted_contributors, total_contributions_count, user_profiles)}
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
                <select id="memberSelect" style="padding: 8px; border: 1px solid #e1e4e8; border-radius: 6px; margin-left: 10px;">
                    <option value="">Choose a team member...</option>
                    {generate_member_options(sorted_contributors, user_profiles)}
                </select>
            </div>
            <div class="chart-container">
                <canvas id="timelineChart"></canvas>
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
        window.pieChart = new Chart(pieCtx, {{
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
                                const data = pieData[context.dataIndex];
                                return [
                                    context.label + ': ' + context.parsed + ' (' + data.percentage + '%)',
                                    '  • Commits: ' + data.commits,
                                    '  • PRs Created: ' + data.prs_created,
                                    '  • PRs Merged: ' + data.prs_merged,
                                    '  • PR Reviews: ' + data.prs_reviewed
                                ];
                            }}
                        }}
                    }}
                }},
                onClick: function(event, elements) {{
                    if (elements.length > 0) {{
                        const clickedIndex = elements[0].index;
                        
                        // Get username from stored array (handles hidden users correctly)
                        let clickedUsername = null;
                        if (window.pieChart.usernames && window.pieChart.usernames[clickedIndex]) {{
                            clickedUsername = window.pieChart.usernames[clickedIndex];
                        }} else {{
                            // Fallback to original pieData if usernames array not available
                            const clickedData = pieData[clickedIndex];
                            if (clickedData) {{
                                clickedUsername = clickedData.username;
                            }}
                        }}
                        
                        if (clickedUsername) {{
                            selectUserInTimeline(clickedUsername);
                        }}
                    }}
                }}
            }}
        }});
        
        // Initialize usernames array for pie chart click handling
        window.pieChart.usernames = pieData.map(d => d.username);

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
        const allTeamButton = document.querySelector('.filter-button[data-filter="all"]');
        const memberSelect = document.getElementById('memberSelect');

        // Function to select a user in the timeline (called from pie chart clicks)
        function selectUserInTimeline(username) {{
            // Set the dropdown to the selected user
            memberSelect.value = username;
            
            // Update the timeline chart to show individual data
            updateTimelineChart('individual', username);
            
            // Scroll to the timeline section smoothly
            const timelineChart = document.getElementById('timelineChart');
            const timelineSection = timelineChart.closest('.chart-section');
            if (timelineSection) {{
                timelineSection.scrollIntoView({{ 
                    behavior: 'smooth', 
                    block: 'start' 
                }});
            }}
        }}

        // All Team button resets dropdown and shows team view
        allTeamButton.addEventListener('click', function() {{
            memberSelect.value = ''; // Reset dropdown to "Choose a team member..."
            updateTimelineChart('all', null);
        }});

        // Dropdown selection shows individual member
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


        // Table sorting functionality
        const table = document.querySelector('.contributors-table');
        const headers = table.querySelectorAll('.sortable-header');
        let currentSort = {{ column: 'rank', direction: 'asc' }};

        headers.forEach(header => {{
            header.addEventListener('click', function() {{
                const column = this.dataset.column;
                const type = this.dataset.type;
                
                // Toggle direction if same column, otherwise default to desc for most columns
                let direction = 'desc';
                if (currentSort.column === column) {{
                    direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
                }} else if (column === 'rank') {{
                    direction = 'asc'; // Rank should default to ascending
                }}
                
                sortTable(column, direction, type);
                updateSortIndicators(column, direction);
                
                currentSort = {{ column, direction }};
            }});
        }});

        function sortTable(column, direction, type) {{
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            
            rows.sort((a, b) => {{
                let aVal = a.dataset[column];
                let bVal = b.dataset[column];
                
                if (type === 'number') {{
                    aVal = parseFloat(aVal) || 0;
                    bVal = parseFloat(bVal) || 0;
                }} else {{
                    aVal = aVal.toLowerCase();
                    bVal = bVal.toLowerCase();
                }}
                
                if (direction === 'asc') {{
                    return aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
                }} else {{
                    return aVal > bVal ? -1 : aVal < bVal ? 1 : 0;
                }}
            }});
            
            // Re-append sorted rows
            rows.forEach(row => tbody.appendChild(row));
        }}

        function updateSortIndicators(activeColumn, direction) {{
            headers.forEach(header => {{
                header.classList.remove('sort-asc', 'sort-desc');
                if (header.dataset.column === activeColumn) {{
                    header.classList.add(direction === 'asc' ? 'sort-asc' : 'sort-desc');
                }}
            }});
        }}

        // Set initial sort indicator
        updateSortIndicators('rank', 'asc');

        // User hiding functionality
        let hiddenUsers = JSON.parse(localStorage.getItem('hiddenUsers') || '[]');
        
        function toggleUserVisibility(username) {{
            const index = hiddenUsers.indexOf(username);
            if (index > -1) {{
                hiddenUsers.splice(index, 1);
            }} else {{
                hiddenUsers.push(username);
            }}
            
            localStorage.setItem('hiddenUsers', JSON.stringify(hiddenUsers));
            updateUserVisibility();
            recalculateStats();
            updatePieChart();
        }}
        
        function showAllUsers() {{
            hiddenUsers = [];
            localStorage.setItem('hiddenUsers', JSON.stringify(hiddenUsers));
            updateUserVisibility();
            recalculateStats();
            updatePieChart();
        }}
        
        function updateUserVisibility() {{
            // Update table rows
            const tableRows = document.querySelectorAll('.contributors-table tbody tr');
            tableRows.forEach(row => {{
                const username = row.dataset.username;
                if (hiddenUsers.includes(username)) {{
                    row.classList.add('hidden-user');
                }} else {{
                    row.classList.remove('hidden-user');
                }}
            }});
        }}
        
        function recalculateStats() {{
            const visibleRows = document.querySelectorAll('.contributors-table tbody tr:not(.hidden-user)');
            let totalContributions = 0;
            
            // Calculate new total from visible users
            visibleRows.forEach(row => {{
                totalContributions += parseInt(row.dataset.total) || 0;
            }});
            
            // Update percentages for visible users
            visibleRows.forEach(row => {{
                const userTotal = parseInt(row.dataset.total) || 0;
                const newPercentage = totalContributions > 0 ? (userTotal / totalContributions * 100) : 0;
                
                // Update percentage text
                const percentageCell = row.cells[6];
                const percentageText = percentageCell.querySelector('div').previousSibling;
                percentageText.textContent = newPercentage.toFixed(1) + '%';
                
                // Update percentage bar
                const percentageFill = percentageCell.querySelector('.percentage-fill');
                percentageFill.style.width = newPercentage + '%';
            }});
            
            // Update stats cards
            updateStatsCards();
        }}
        
        function updateStatsCards() {{
            const visibleRows = document.querySelectorAll('.contributors-table tbody tr:not(.hidden-user)');
            let totalContribs = 0, totalCommits = 0, totalPRsCreated = 0, totalReviews = 0;
            
            visibleRows.forEach(row => {{
                const username = row.dataset.username;
                const userData = pieData.find(item => item.username === username);
                if (userData) {{
                    totalContribs += userData.commits + userData.prs_created + userData.prs_merged + userData.prs_reviewed;
                    totalCommits += userData.commits;
                    totalPRsCreated += userData.prs_created;
                    totalReviews += userData.prs_reviewed;
                }}
            }});
            
            // Update stat cards (now 5 cards instead of 6)
            const statCards = document.querySelectorAll('.stat-card .stat-number');
            if (statCards.length >= 5) {{
                statCards[0].textContent = visibleRows.length; // Active Contributors
                statCards[1].textContent = totalContribs.toLocaleString(); // Total Contributions
                statCards[2].textContent = totalCommits.toLocaleString(); // Commits
                statCards[3].textContent = totalPRsCreated.toLocaleString(); // PRs Created
                statCards[4].textContent = totalReviews.toLocaleString(); // PR Reviews
            }}
        }}
        
        function updatePieChart() {{
            const visibleRows = document.querySelectorAll('.contributors-table tbody tr:not(.hidden-user)');
            let totalContributions = 0;
            
            // Calculate total from visible users
            visibleRows.forEach(row => {{
                totalContributions += parseInt(row.dataset.total) || 0;
            }});
            
            // Create new data arrays for visible users only
            const newLabels = [];
            const newData = [];
            const newColors = [];
            const newUsernames = []; // Store usernames for click handling
            
            visibleRows.forEach((row, index) => {{
                const username = row.dataset.username;
                const displayName = row.dataset.name;
                const userTotal = parseInt(row.dataset.total) || 0;
                
                // Find original pie data for this user to get color and other info
                const originalData = pieData.find(item => item.username === username);
                
                newLabels.push(displayName);
                newData.push(userTotal);
                newColors.push(originalData ? originalData.color : pieData[index % pieData.length].color);
                newUsernames.push(username);
            }});
            
            // Update the pie chart
            if (window.pieChart) {{
                window.pieChart.data.labels = newLabels;
                window.pieChart.data.datasets[0].data = newData;
                window.pieChart.data.datasets[0].backgroundColor = newColors;
                // Store usernames for click handling
                window.pieChart.usernames = newUsernames;
                window.pieChart.update();
            }}
        }}
        
        // Initialize user visibility on page load
        document.addEventListener('DOMContentLoaded', function() {{
            updateUserVisibility();
            recalculateStats();
            updatePieChart();
        }});
        
        // Also run after the page is fully loaded
        window.addEventListener('load', function() {{
            updateUserVisibility();
            recalculateStats();
            updatePieChart();
        }});
    </script>
</body>
</html>
"""
    
    # Write the HTML file
    with open(output_file, 'w') as f:
        f.write(html_content)
    
    return output_file


def generate_contributors_table(sorted_contributors, total_contributions_count, user_profiles):
    """Generate HTML for contributors table with detailed breakdown."""
    table_html = ""
    for rank, (username, contrib_data) in enumerate(sorted_contributors, 1):
        percentage = (contrib_data['total_contributions'] / total_contributions_count * 100) if total_contributions_count > 0 else 0
        rank_color = "#1a73e8" if rank <= 3 else "#5f6368"
        
        # Get improved display name
        profile = user_profiles.get(username, {})
        email = profile.get('email')
        display_name = improve_display_name(contrib_data['name'], email, username)
        
        commits = contrib_data.get('commits', 0)
        prs_created = contrib_data.get('prs_created', 0)
        prs_merged = contrib_data.get('prs_merged', 0)
        prs_reviewed = contrib_data.get('prs_reviewed', 0)
        
        # Create tooltip text
        tooltip_text = ""
        if email:
            tooltip_text = f"Email: {email}"
        elif username != display_name.rstrip('@'):
            tooltip_text = f"GitHub: @{username}"
        
        # Create name cell with tooltip (no hide button here)
        name_content = f'<span class="tooltip" data-tooltip="{tooltip_text}">{display_name}</span>' if tooltip_text else display_name
        name_cell = f'<strong>{name_content}</strong>'
        
        table_html += f"""
            <tr data-username="{username}" data-rank="{rank}" data-name="{display_name}" data-total="{contrib_data['total_contributions']}" 
                data-commits="{commits}" data-prs="{prs_created + prs_merged}" data-reviews="{prs_reviewed}" data-percentage="{percentage:.1f}"
                onclick="selectUserInTimeline('{username}')" title="Click to view individual timeline">
                <td><span style="color: {rank_color}; font-weight: bold;">#{rank}</span></td>
                <td>{name_cell}</td>
                <td>{contrib_data['total_contributions']:,}</td>
                <td>{commits:,}</td>
                <td>{prs_created + prs_merged:,}</td>
                <td>{prs_reviewed:,}</td>
                <td>
                    {percentage:.1f}%
                    <div class="percentage-bar">
                        <div class="percentage-fill" style="width: {percentage}%"></div>
                    </div>
                    <button class="hide-user-btn" onclick="event.stopPropagation(); toggleUserVisibility('{username}')" title="Hide this user">−</button>
                </td>
            </tr>
        """
    return table_html

def generate_member_options(sorted_contributors, user_profiles):
    """Generate HTML options for member selection dropdown."""
    options_html = ""
    for rank, (username, contrib_data) in enumerate(sorted_contributors, 1):
        # Get improved display name
        profile = user_profiles.get(username, {})
        email = profile.get('email')
        display_name = improve_display_name(contrib_data['name'], email, username)
        
        options_html += f'<option value="{username}">#{rank} {display_name} ({contrib_data["total_contributions"]} contributions)</option>'
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
        print(f"📈 Total contributions: {sum(c['total_contributions'] for c in data['contributors'].values())}")
        print(f"   • Commits: {sum(c.get('commits', 0) for c in data['contributors'].values())}")
        print(f"   • PRs Created: {sum(c.get('prs_created', 0) for c in data['contributors'].values())}")
        print(f"   • PRs Merged: {sum(c.get('prs_merged', 0) for c in data['contributors'].values())}")
        print(f"   • PR Reviews: {sum(c.get('prs_reviewed', 0) for c in data['contributors'].values())}")
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("Please run github_contributions.py first to generate the data file.")
    except Exception as e:
        print(f"❌ Error generating report: {e}")

if __name__ == "__main__":
    main()