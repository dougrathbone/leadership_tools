from github import Github
from github import RateLimitExceededException
import getpass
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import json
import os
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import signal
import pickle

def handle_rate_limit(func, *args, **kwargs):
    """
    Wrapper function to handle GitHub API rate limiting with exponential backoff and timeouts
    """
    max_retries = 5
    base_delay = 1
    timeout_seconds = 30  # 30 second timeout for requests
    
    for attempt in range(max_retries):
        try:
            # Set timeout for the request if it's a GitHub API call
            if hasattr(func, '__self__') and hasattr(func.__self__, '_requester'):
                # This is a PyGithub method, set timeout on the underlying requester
                original_timeout = getattr(func.__self__._requester, '_timeout', None)
                func.__self__._requester._timeout = timeout_seconds
            
            result = func(*args, **kwargs)
            
            # Restore original timeout
            if hasattr(func, '__self__') and hasattr(func.__self__, '_requester'):
                if original_timeout is not None:
                    func.__self__._requester._timeout = original_timeout
                else:
                    delattr(func.__self__._requester, '_timeout')
            
            return result
            
        except RateLimitExceededException as e:
            if attempt == max_retries - 1:
                print(f"Rate limit exceeded after {max_retries} attempts. Exiting.")
                raise e
            
            # Calculate delay with exponential backoff and jitter
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            print(f"Rate limit exceeded. Retrying in {delay:.2f} seconds... (attempt {attempt + 1}/{max_retries})")
            time.sleep(delay)
            
        except Exception as e:
            # Handle timeouts and connection errors with retry
            if any(keyword in str(e).lower() for keyword in ['timeout', 'connection', 'network', 'read timed out']):
                if attempt == max_retries - 1:
                    print(f"Network/timeout error after {max_retries} attempts: {str(e)}")
                    raise e
                
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                print(f"Network/timeout error. Retrying in {delay:.2f} seconds... (attempt {attempt + 1}/{max_retries}): {str(e)}")
                time.sleep(delay)
            else:
                # For other exceptions, don't retry
                raise e

def fetch_contributor_commits(repo, contributor, start_date):
    """
    Fetch commits for a single contributor with rate limiting
    """
    try:
        commits = list(handle_rate_limit(repo.get_commits, author=contributor, since=start_date))
        return contributor.login, commits
    except Exception as e:
        print(f"Error fetching commits for {contributor.login}: {str(e)}")
        return contributor.login, []

def save_state(state_data, filename="reports/scan_state.pkl"):
    """
    Save the current state to a pickle file
    """
    try:
        os.makedirs("reports", exist_ok=True)
        with open(filename, 'wb') as f:
            pickle.dump(state_data, f)
        print(f"State saved to {filename}")
    except Exception as e:
        print(f"Error saving state: {str(e)}")

def load_state(filename="reports/scan_state.pkl"):
    """
    Load state from a pickle file
    """
    try:
        if os.path.exists(filename):
            with open(filename, 'rb') as f:
                state_data = pickle.load(f)
            print(f"State loaded from {filename}")
            return state_data
        return None
    except Exception as e:
        print(f"Error loading state: {str(e)}")
        return None

def save_progress_data(total_contributions, user_profiles, daily_contributions, repo_contributions, 
                      organization, start_date, processed_repos):
    """
    Save current progress data to JSON files
    """
    try:
        os.makedirs("reports", exist_ok=True)
        
        # Save comprehensive data as JSON
        comprehensive_data = {
            "organization": organization,
            "start_date": start_date.isoformat(),
            "end_date": datetime.now(timezone.utc).isoformat(),
            "processed_repositories": processed_repos,
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
        
        # Save JSON data
        with open("reports/contributions_data.json", "w") as file:
            json.dump(comprehensive_data, file, indent=2, default=str)
        
        # Save CSV data
        sorted_contributions = sorted(total_contributions.items(), key=lambda x: x[1]["total_contributions"], reverse=True)
        with open("output.csv", "w") as file:
            file.write("Username,Name,Commits,PRs Created,PRs Merged,PR Reviews,Total Contributions\n")
            for username, data in sorted_contributions:
                file.write(f"{username},{data['name']},{data['commits']},{data['prs_created']},{data['prs_merged']},{data['prs_reviewed']},{data['total_contributions']}\n")
        
        print("Progress data saved to output.csv and reports/contributions_data.json")
        
    except Exception as e:
        print(f"Error saving progress data: {str(e)}")

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

# Check for existing state and offer to resume
existing_state = load_state()
resume_from_state = False
processed_repo_names = set()

if existing_state:
    print(f"\nFound existing scan state from previous run:")
    print(f"  Organization: {existing_state.get('organization', 'N/A')}")
    print(f"  Start date: {existing_state.get('start_date', 'N/A')}")
    print(f"  Processed repositories: {len(existing_state.get('processed_repos', []))}")
    
    try:
        resume_choice = input("Resume from previous state? (y/n): ").lower().strip()
        if resume_choice == 'y':
            resume_from_state = True
            processed_repo_names = set(existing_state.get('processed_repos', []))
            # Restore data structures
            total_contributions.update(existing_state.get('total_contributions', {}))
            user_profiles.update(existing_state.get('user_profiles', {}))
            daily_contributions.update(existing_state.get('daily_contributions', {}))
            repo_contributions.update(existing_state.get('repo_contributions', {}))
            print(f"Resuming scan, skipping {len(processed_repo_names)} already processed repositories...")
    except (EOFError, KeyboardInterrupt):
        print("Continuing with fresh scan...")

# Get the list of repositories with explicit pagination handling
print("Fetching repository list...")
repos = handle_rate_limit(org.get_repos, type='all', sort='updated', direction='desc')
repos_list = list(repos)  # This forces PyGithub to fetch all pages
total_repos = len(repos_list)

# Filter out already processed repositories if resuming
if resume_from_state:
    original_count = len(repos_list)
    repos_list = [repo for repo in repos_list if repo.full_name not in processed_repo_names]
    skipped_count = original_count - len(repos_list)
    print(f"Skipped {skipped_count} already processed repositories")
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

# Track timing for progress estimation
scan_start_time = time.time()
processed_repos = list(processed_repo_names) if resume_from_state else []

# Set up signal handler for graceful shutdown
def signal_handler(signum, frame):
    print(f"\n\nReceived interrupt signal. Saving current state...")
    
    # Save current state
    current_state = {
        "organization": ORG_NAME,
        "start_date": start_date.isoformat(),
        "processed_repos": processed_repos,
        "total_contributions": dict(total_contributions),
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
    save_state(current_state)
    
    # Save progress data
    save_progress_data(total_contributions, user_profiles, daily_contributions, 
                      repo_contributions, ORG_NAME, start_date, processed_repos)
    
    print("State and progress saved. You can resume by running the script again.")
    exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Loop through all repositories in the organization
try:
    for idx, repo in enumerate(repos_list, start=1):
        repo_name = repo.full_name
        progress_percent = (idx / total_repos) * 100
        print(f"\n[{progress_percent:.1f}%] Scanning repository {idx}/{total_repos}: {repo_name}")

        try:
            # Get all contributors for the repository with rate limiting
            contributors = handle_rate_limit(repo.get_contributors)
            contributors_list = list(contributors)
            total_contributors = len(contributors_list)
            
            # Create username to contributor mapping for quick lookup
            contributor_map = {c.login: c for c in contributors_list}
            
            print(f"   Found {total_contributors} contributors")

            # Get all pull requests for the repository since start date with rate limiting
            all_prs = handle_rate_limit(repo.get_pulls, state='all', sort='created', direction='desc')
            
            # Filter PRs by date and collect all PR data in one pass
            recent_prs = []
            pr_reviews_cache = {}  # Cache reviews to avoid repeated API calls
            
            print(f"   Fetching PRs and reviews since {start_date.strftime('%Y-%m-%d')}...")
            
            for pr_idx, pr in enumerate(all_prs):
                if pr.created_at >= start_date:
                    recent_prs.append(pr)
                    
                    # Fetch reviews once per PR and cache them
                    try:
                        reviews = list(handle_rate_limit(pr.get_reviews))
                        pr_reviews_cache[pr.number] = reviews
                    except Exception as e:
                        pr_reviews_cache[pr.number] = []
                        
                    # Show progress for PR processing
                    if (pr_idx + 1) % 100 == 0:
                        print(f"     Processed {pr_idx + 1} PRs...")
                else:
                    break  # PRs are sorted by creation date, so we can break early
            
            print(f"   Found {len(recent_prs)} PRs with reviews cached")
            
            # Fetch commits for all contributors concurrently
            print(f"   Fetching commits for {total_contributors} contributors concurrently...")
            commits_data = {}
            
            # Use ThreadPoolExecutor for concurrent commit fetching
            max_workers = min(10, total_contributors)  # Limit concurrent requests to avoid overwhelming API
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all commit fetching tasks
                future_to_contributor = {
                    executor.submit(fetch_contributor_commits, repo, contributor, start_date): contributor
                    for contributor in contributors_list
                }
                
                # Collect results as they complete
                completed = 0
                for future in as_completed(future_to_contributor):
                    username, commits = future.result()
                    commits_data[username] = commits
                    completed += 1
                    
                    # Show progress
                    progress = (completed / total_contributors) * 100
                    print(f"     [{progress:.0f}%] Fetched commits for {completed}/{total_contributors} contributors")
            
            # Now process each contributor efficiently using cached data
            print(f"   Processing contributions for {total_contributors} contributors...")
            
            for contrib_idx, contributor in enumerate(contributors_list, start=1):
                username = contributor.login
                name = contributor.name or "N/A"
                
                # Store user profile info
                if username not in user_profiles:
                    # Try to get email from contributor object
                    email = getattr(contributor, 'email', None)
                    user_profiles[username] = {
                        "name": name,
                        "login": username,
                        "avatar_url": contributor.avatar_url,
                        "html_url": contributor.html_url,
                        "email": email
                    }
                
                # Get commits from cached data
                commits = commits_data.get(username, [])
                commit_count = len(commits)
                
                # Count PRs created and merged by this user (single pass through cached data)
                prs_created = 0
                prs_merged = 0
                prs_reviewed = 0
                
                for pr in recent_prs:
                    # Count PRs created by this user
                    if pr.user.login == username:
                        prs_created += 1
                        if pr.merged:
                            prs_merged += 1
                    
                    # Count PR reviews by this user (using cached reviews)
                    reviews = pr_reviews_cache.get(pr.number, [])
                    prs_reviewed += sum(1 for review in reviews if review.user.login == username)
                
                total_contribs = commit_count + prs_created + prs_merged + prs_reviewed
                
                contrib_progress = (contrib_idx / total_contributors) * 100
                print(f"   [{contrib_progress:.0f}%] {contrib_idx}/{total_contributors} - {name}: {commit_count} commits, {prs_created} PRs created, {prs_merged} PRs merged, {prs_reviewed} PR reviews")
                
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
                    
                    # Track daily contributions for PRs (using cached data)
                    for pr in recent_prs:
                        pr_date = pr.created_at.strftime("%Y-%m-%d")
                        if pr.user.login == username:
                            daily_contributions[username][pr_date]["prs_created"] += 1
                            if pr.merged:
                                merge_date = pr.merged_at.strftime("%Y-%m-%d") if pr.merged_at else pr_date
                                daily_contributions[username][merge_date]["prs_merged"] += 1

            active_contributors = len([u for u in total_contributions if total_contributions[u]['total_contributions'] > 0])
            print(f"   ✓ Repository completed. Active contributors found: {active_contributors}")
            
            # Add this repository to processed list
            processed_repos.append(repo_name)
            
            # Save state after each repository (progressive saving)
            current_state = {
                "organization": ORG_NAME,
                "start_date": start_date.isoformat(),
                "processed_repos": processed_repos,
                "total_contributions": dict(total_contributions),
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
            save_state(current_state)
            
            # Save progress data after each repository
            save_progress_data(total_contributions, user_profiles, daily_contributions, 
                              repo_contributions, ORG_NAME, start_date, processed_repos)
            
            # Calculate estimated time remaining
            elapsed_time = time.time() - scan_start_time
            if idx > 1:  # Only show ETA after processing at least 2 repos
                avg_time_per_repo = elapsed_time / idx
                remaining_repos = total_repos - idx
                eta_seconds = avg_time_per_repo * remaining_repos
                eta_minutes = eta_seconds / 60
                
                if eta_minutes < 1:
                    eta_str = f"{eta_seconds:.0f}s"
                elif eta_minutes < 60:
                    eta_str = f"{eta_minutes:.1f}m"
                else:
                    eta_hours = eta_minutes / 60
                    eta_str = f"{eta_hours:.1f}h"
                
                print(f"   Overall progress: {idx}/{total_repos} repositories ({progress_percent:.1f}%) - ETA: {eta_str}")
            else:
                print(f"   Overall progress: {idx}/{total_repos} repositories ({progress_percent:.1f}%)")
        except Exception as e:
            if hasattr(e, 'status') and e.status == 409 and "Git Repository is empty." in str(e.data):
                print("Skipping empty repository.")
            else:
                print(f"Error processing repository: {str(e)}")

except KeyboardInterrupt:
    print(f"\n\nGracefully stopping... Processed {len(processed_repos)} repositories.")
    print("Final state and data already saved during processing.")

# Final save of all data
print(f"\nScan completed! Processed {len(processed_repos)} repositories.")

# Save final progress data
save_progress_data(total_contributions, user_profiles, daily_contributions, 
                  repo_contributions, ORG_NAME, start_date, processed_repos)

# Clean up state file since scan is complete
try:
    if os.path.exists("reports/scan_state.pkl"):
        os.remove("reports/scan_state.pkl")
        print("Cleaned up temporary state file.")
except:
    pass

print("\nScan completed successfully!")
print("Output saved to output.csv")
print("Comprehensive data saved to reports/contributions_data.json")
