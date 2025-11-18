from github import Github
from github import RateLimitExceededException
import getpass
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import json
import os
import time
import random

def handle_rate_limit(func, *args, **kwargs):
    """
    Wrapper function to handle GitHub API rate limiting with exponential backoff
    """
    max_retries = 5
    base_delay = 1
    
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except RateLimitExceededException as e:
            if attempt == max_retries - 1:
                print(f"Rate limit exceeded after {max_retries} attempts. Exiting.")
                raise e
            
            # Calculate delay with exponential backoff and jitter
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            print(f"Rate limit exceeded. Retrying in {delay:.2f} seconds... (attempt {attempt + 1}/{max_retries})")
            time.sleep(delay)
        except Exception as e:
            # For other exceptions, don't retry
            raise e

# Get GitHub personal access token from environment variable or prompt
access_token = os.getenv('GITHUB_TOKEN')
if not access_token:
    try:
        access_token = getpass.getpass("Enter your GitHub personal access token: ")
    except (EOFError, KeyboardInterrupt):
        print("\nError: No GitHub token provided.")
        print("Please set the GITHUB_TOKEN environment variable or run in an interactive terminal.")
        print("Example: export GITHUB_TOKEN='your_token_here'")
        exit(1)

# Replace with the name of the organization
ORG_NAME = "heydovetail"

# Create a PyGitHub instance
g = Github(access_token)

# Get the organization
org = g.get_organization(ORG_NAME)

# Initialize dictionaries to store contribution data
total_contributions = defaultdict(lambda: {
    "name": "N/A", 
    "commits": 0, 
    "prs_created": 0, 
    "prs_merged": 0, 
    "prs_reviewed": 0,
    "total_contributions": 0
})
daily_contributions = defaultdict(lambda: defaultdict(lambda: {
    "commits": 0, 
    "prs_created": 0, 
    "prs_merged": 0, 
    "prs_reviewed": 0
}))
repo_contributions = defaultdict(lambda: defaultdict(lambda: {
    "commits": 0, 
    "prs_created": 0, 
    "prs_merged": 0, 
    "prs_reviewed": 0
}))
user_profiles = {}

# Set the default start date to 6 months ago (timezone-aware)
default_start_date = datetime.now(timezone.utc) - timedelta(days=180)
start_date_str = default_start_date.strftime("%Y-%m-%d")

# Prompt the user for an alternate start date
try:
    alt_start_date = input(f"Enter an alternate start date (YYYY-MM-DD) or press Enter to use the default ({start_date_str}): ")
    if alt_start_date:
        # Make the parsed date timezone-aware (UTC)
        start_date = datetime.strptime(alt_start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        start_date = default_start_date
except (EOFError, KeyboardInterrupt):
    print(f"Using default start date: {start_date_str}")
    start_date = default_start_date

# Get the list of repositories with explicit pagination handling
print("Fetching repository list...")
repos = handle_rate_limit(org.get_repos, type='all', sort='updated', direction='desc')
repos_list = list(repos)  # This forces PyGithub to fetch all pages
total_repos = len(repos_list)

print(f"Found {total_repos} repositories in the {ORG_NAME} organization")
print("Repository names (sorted by most recently updated):")
for i, repo in enumerate(repos_list[:10]):  # Show first 10 repos
    print(f"  {i+1}. {repo.full_name} (updated: {repo.updated_at}, size: {repo.size}KB)")
if total_repos > 10:
    print(f"  ... and {total_repos - 10} more repositories")
    
# Show the largest repositories by size
print("\nLargest repositories by size:")
largest_repos = sorted(repos_list, key=lambda r: r.size, reverse=True)[:5]
for i, repo in enumerate(largest_repos):
    print(f"  {i+1}. {repo.full_name} (size: {repo.size}KB, updated: {repo.updated_at})")

print(f"\nScanning {total_repos} repositories since {start_date_str}...")
print("Press Ctrl+C to stop gracefully at any time...\n")

# Loop through all repositories in the organization
try:
    for idx, repo in enumerate(repos_list, start=1):
        repo_name = repo.full_name
        print(f"\nScanning repository {idx}/{total_repos}: {repo_name}")

        try:
            # Get all contributors for the current repository with rate limiting
            contributors = handle_rate_limit(repo.get_contributors)

            # Get all pull requests for the repository since start date with rate limiting
            all_prs = handle_rate_limit(repo.get_pulls, state='all', sort='created', direction='desc')
            
            # Filter PRs by date
            recent_prs = []
            for pr in all_prs:
                if pr.created_at >= start_date:
                    recent_prs.append(pr)
                else:
                    break  # PRs are sorted by creation date, so we can break early
            
            print(f"   Found {len(recent_prs)} PRs since {start_date.strftime('%Y-%m-%d')}")

            # Loop through contributors and update total contributions
            for contributor in contributors:
                username = contributor.login
                name = contributor.name or "N/A"  # Use "N/A" if the name is not available
                
                # Store user profile info
                if username not in user_profiles:
                    user_profiles[username] = {
                        "name": name,
                        "login": username,
                        "avatar_url": contributor.avatar_url,
                        "html_url": contributor.html_url
                    }
                
                # Get commits for this contributor since the start date with rate limiting
                commits = list(handle_rate_limit(repo.get_commits, author=contributor, since=start_date))
                commit_count = len(commits)
                
                # Count PRs created by this user
                prs_created = sum(1 for pr in recent_prs if pr.user.login == username)
                
                # Count PRs merged by this user (where they are the author and PR was merged)
                prs_merged = sum(1 for pr in recent_prs if pr.user.login == username and pr.merged)
                
                # Count PR reviews by this user
                prs_reviewed = 0
                for pr in recent_prs:
                    try:
                        reviews = handle_rate_limit(pr.get_reviews)
                        prs_reviewed += sum(1 for review in reviews if review.user.login == username)
                    except Exception as e:
                        # Some PRs might not have reviews accessible
                        pass
                
                total_contribs = commit_count + prs_created + prs_merged + prs_reviewed
                
                print(f"\n   {name}: {commit_count} commits, {prs_created} PRs created, {prs_merged} PRs merged, {prs_reviewed} PR reviews")
                
                if total_contribs > 0:
                    total_contributions[username]["name"] = name
                    total_contributions[username]["commits"] += commit_count
                    total_contributions[username]["prs_created"] += prs_created
                    total_contributions[username]["prs_merged"] += prs_merged
                    total_contributions[username]["prs_reviewed"] += prs_reviewed
                    total_contributions[username]["total_contributions"] += total_contribs
                    
                    # Update repo-specific contributions
                    repo_contributions[username][repo_name]["commits"] = commit_count
                    repo_contributions[username][repo_name]["prs_created"] = prs_created
                    repo_contributions[username][repo_name]["prs_merged"] = prs_merged
                    repo_contributions[username][repo_name]["prs_reviewed"] = prs_reviewed
                    
                    # Track daily contributions for commits
                    for commit in commits:
                        commit_date = commit.commit.author.date.strftime("%Y-%m-%d")
                        daily_contributions[username][commit_date]["commits"] += 1
                    
                    # Track daily contributions for PRs
                    for pr in recent_prs:
                        pr_date = pr.created_at.strftime("%Y-%m-%d")
                        if pr.user.login == username:
                            daily_contributions[username][pr_date]["prs_created"] += 1
                            if pr.merged:
                                merge_date = pr.merged_at.strftime("%Y-%m-%d") if pr.merged_at else pr_date
                                daily_contributions[username][merge_date]["prs_merged"] += 1

            print(f"Repository processed. Total unique contributors: {len([u for u in total_contributions if total_contributions[u]['total_contributions'] > 0])}")
        except Exception as e:
            if hasattr(e, 'status') and e.status == 409 and "Git Repository is empty." in str(e.data):
                print("Skipping empty repository.")
            else:
                print(f"Error processing repository: {str(e)}")

except KeyboardInterrupt:
    print(f"\n\nGracefully stopping... Processed {idx-1} of {total_repos} repositories.")
    print("Generating report with data collected so far...")

# Sort the contributions in descending order by total contributions
sorted_contributions = sorted(total_contributions.items(), key=lambda x: x[1]["total_contributions"], reverse=True)

# Save the CSV output
with open("output.csv", "w") as file:
    file.write("Username,Name,Commits,PRs Created,PRs Merged,PR Reviews,Total Contributions\n")
    for username, data in sorted_contributions:
        file.write(f"{username},{data['name']},{data['commits']},{data['prs_created']},{data['prs_merged']},{data['prs_reviewed']},{data['total_contributions']}\n")

# Save comprehensive data as JSON for report generation
comprehensive_data = {
    "organization": ORG_NAME,
    "start_date": start_date.isoformat(),
    "end_date": datetime.now().isoformat(),
    "total_repositories": total_repos,
    "contributors": dict(total_contributions),
    "user_profiles": user_profiles,
    "daily_contributions": {
        user: {date: dict(metrics) for date, metrics in days.items()} 
        for user, days in daily_contributions.items()
    },
    "repo_contributions": {
        user: {repo: dict(metrics) for repo, metrics in repos.items()} 
        for user, repos in repo_contributions.items()
    }
}

# Create reports directory if it doesn't exist
os.makedirs("reports", exist_ok=True)

# Save JSON data
with open("reports/contributions_data.json", "w") as file:
    json.dump(comprehensive_data, file, indent=2, default=str)

print("\nOutput saved to output.csv")
print("Comprehensive data saved to reports/contributions_data.json")
