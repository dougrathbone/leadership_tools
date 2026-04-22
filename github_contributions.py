from github import Github, Auth
from github import RateLimitExceededException, GithubException
import getpass
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import json
import os
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import signal
import pickle

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

def handle_rate_limit(func, *args, **kwargs):
    """
    Wrapper function to handle GitHub API rate limiting with exponential backoff and timeouts.
    Handles both primary rate limits (RateLimitExceededException) and secondary/abuse
    rate limits (403 GithubException).
    """
    max_retries = 5
    base_delay = 1
    
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
            
        except RateLimitExceededException as e:
            if attempt == max_retries - 1:
                print(f"Rate limit exceeded after {max_retries} attempts.")
                raise e
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            print(f"Rate limit exceeded. Retrying in {delay:.2f} seconds... (attempt {attempt + 1}/{max_retries})")
            time.sleep(delay)

        except GithubException as e:
            if e.status == 403:
                if attempt == max_retries - 1:
                    print(f"403 Forbidden after {max_retries} attempts.")
                    raise e
                delay = min(60, base_delay * (2 ** attempt)) + random.uniform(0, 2)
                print(f"   Secondary rate limit (403). Waiting {delay:.0f}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                raise e
            
        except Exception as e:
            if any(keyword in str(e).lower() for keyword in ['timeout', 'connection', 'network', 'read timed out']):
                if attempt == max_retries - 1:
                    print(f"Network/timeout error after {max_retries} attempts: {str(e)}")
                    raise e
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                print(f"Network/timeout error. Retrying in {delay:.2f} seconds... (attempt {attempt + 1}/{max_retries}): {str(e)}")
                time.sleep(delay)
            else:
                raise e

def fetch_commits_for_author(repo, author, start_date):
    """
    Fetch commits for a repository author. ``author`` may be a PyGithub NamedUser
    or a login string (for people who appear on PRs but not in get_contributors()).
    """
    login = author.login if hasattr(author, "login") else author
    try:
        commits = list(handle_rate_limit(repo.get_commits, author=author, since=start_date))
        return login, commits
    except Exception as e:
        print(f"Error fetching commits for {login}: {str(e)}")
        return login, []

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
                      organization, start_date, processed_repos, organization_repository_count=None,
                      pr_metrics=None):
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
            "organization_repository_count": organization_repository_count,
            "contributors": dict(total_contributions),
            "user_profiles": user_profiles,
            "daily_contributions": {
                user: {date: dict(metrics) for date, metrics in days.items()} 
                for user, days in daily_contributions.items()
            },
            "repo_contributions": {
                user: {repo: dict(metrics) for repo, metrics in repos.items()} 
                for user, repos in repo_contributions.items()
            },
            "pr_metrics": {
                user: dict(m) for user, m in (pr_metrics or {}).items()
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

# Create a PyGitHub instance (retry=False disables PyGithub's internal backoff
# which can sleep 35+ minutes on secondary rate limits; we handle retries ourselves).
g = Github(auth=Auth.Token(access_token), retry=False)

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

# Per-user PR metrics: cycle times, PR sizes, review states
pr_metrics = defaultdict(lambda: {
    "cycle_times_hours": [],
    "pr_sizes": [],
    "reviews_given": {"approved": 0, "changes_requested": 0, "commented": 0},
})

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
            for u, m in existing_state.get('pr_metrics', {}).items():
                pr_metrics[u]["cycle_times_hours"].extend(m.get("cycle_times_hours", []))
                pr_metrics[u]["pr_sizes"].extend(m.get("pr_sizes", []))
                for k, v in m.get("reviews_given", {}).items():
                    pr_metrics[u]["reviews_given"][k] += v
            print(f"Resuming scan, skipping {len(processed_repo_names)} already processed repositories...")
    except (EOFError, KeyboardInterrupt):
        print("Continuing with fresh scan...")

# Get the list of repositories with explicit pagination handling
print("Fetching repository list...")
repos = handle_rate_limit(org.get_repos, type='all', sort='updated', direction='desc')
repos_list = list(repos)  # This forces PyGithub to fetch all pages
organization_repo_total = len(repos_list)
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
        },
        "pr_metrics": {u: dict(m) for u, m in pr_metrics.items()},
    }
    save_state(current_state)
    
    # Save progress data
    save_progress_data(total_contributions, user_profiles, daily_contributions, 
                      repo_contributions, ORG_NAME, start_date, processed_repos,
                      organization_repository_count=organization_repo_total,
                      pr_metrics=pr_metrics)
    
    print("State and progress saved. You can resume by running the script again.")
    exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Loop through all repositories in the organization
try:
    for idx, repo in enumerate(repos_list, start=1):
        repo_name = repo.full_name
        progress_percent = (idx / total_repos) * 100
        print(f"\n[{progress_percent:.1f}%] Scanning repository {idx}/{total_repos}: {repo_name}")

        # Proactive rate-limit check: sleep until reset if budget is low
        try:
            rate = g.get_rate_limit().core
            if rate.remaining < 200:
                sleep_seconds = (rate.reset - datetime.now(timezone.utc)).total_seconds() + 5
                if sleep_seconds > 0:
                    print(f"   ⏳ Rate limit low ({rate.remaining} remaining). Sleeping {sleep_seconds:.0f}s until reset at {rate.reset.strftime('%H:%M:%S UTC')}...")
                    time.sleep(sleep_seconds)
            else:
                print(f"   API budget: {rate.remaining}/{rate.limit}")
        except Exception:
            pass

        try:
            # Get all contributors for the repository with rate limiting
            contributors = handle_rate_limit(repo.get_contributors)
            contributors_list = list(contributors)
            total_contributors = len(contributors_list)
            
            # Create username to contributor mapping for quick lookup
            contributor_map = {c.login: c for c in contributors_list}
            
            print(f"   Found {total_contributors} contributors")

            # PRs created in the reporting window. Using sort='created' bounds the set
            # to PRs actually opened during the period, avoiding the explosion that
            # sort='updated' causes (bot touches, CI, labels bump updated_at on old PRs).
            all_prs = handle_rate_limit(repo.get_pulls, state='all', sort='created', direction='desc')
            
            recent_prs = []
            pr_reviews_cache = {}
            skipped_reviews = 0
            
            print(f"   Fetching PRs created since {start_date.strftime('%Y-%m-%d')}...")
            
            for pr_idx, pr in enumerate(all_prs):
                if pr.created_at < start_date:
                    break
                
                recent_prs.append(pr)
                
                try:
                    reviews = list(pr.get_reviews())
                    pr_reviews_cache[pr.number] = reviews
                except Exception as review_err:
                    status = getattr(review_err, 'status', None)
                    if status == 403:
                        skipped_reviews += 1
                    pr_reviews_cache[pr.number] = []
                    
                if (pr_idx + 1) % 100 == 0:
                    rate = g.get_rate_limit().core
                    print(f"     Processed {pr_idx + 1} PRs... (API budget: {rate.remaining}/{rate.limit})")
            
            if skipped_reviews:
                print(f"   Warning: {skipped_reviews} PR review fetches skipped due to 403")
            print(f"   Found {len(recent_prs)} PRs with reviews cached")
            
            # Everyone with default-branch commits OR any PR role in the window (contributors() alone
            # misses reviewers and many PR authors — see GitHub's contributors API semantics).
            usernames = set(contributor_map.keys())
            for pr in recent_prs:
                if pr.user:
                    usernames.add(pr.user.login)
                for review in pr_reviews_cache.get(pr.number, []):
                    if review.user:
                        usernames.add(review.user.login)
            usernames_sorted = sorted(usernames)
            total_actors = len(usernames_sorted)
            
            # Fetch commits for all actors concurrently
            print(f"   Fetching commits for {total_actors} GitHub users concurrently...")
            commits_data = {}
            
            max_workers = min(3, max(1, total_actors))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_login = {
                    executor.submit(
                        fetch_commits_for_author,
                        repo,
                        contributor_map[u] if u in contributor_map else u,
                        start_date,
                    ): u
                    for u in usernames_sorted
                }
                
                completed = 0
                for future in as_completed(future_to_login):
                    expected_login = future_to_login[future]
                    _, commits = future.result()
                    commits_data[expected_login] = commits
                    completed += 1
                    progress = (completed / total_actors) * 100
                    print(f"     [{progress:.0f}%] Fetched commits for {completed}/{total_actors} users")
            
            print(f"   Processing contributions for {total_actors} users...")
            
            for contrib_idx, username in enumerate(usernames_sorted, start=1):
                contributor = contributor_map.get(username)
                name = (contributor.name or "N/A") if contributor else "N/A"
                
                if username not in user_profiles:
                    if contributor:
                        email = getattr(contributor, "email", None)
                        user_profiles[username] = {
                            "name": name,
                            "login": username,
                            "avatar_url": contributor.avatar_url,
                            "html_url": contributor.html_url,
                            "email": email,
                        }
                    else:
                        user_profiles[username] = {
                            "name": "N/A",
                            "login": username,
                            "avatar_url": "",
                            "html_url": f"https://github.com/{username}",
                            "email": None,
                        }
                
                commits = commits_data.get(username, [])
                commit_count = len(commits)
                
                prs_created = 0
                prs_merged = 0
                prs_reviewed = 0
                user_cycle_times = []
                user_pr_sizes = []
                user_review_states = {"approved": 0, "changes_requested": 0, "commented": 0}
                
                for pr in recent_prs:
                    if pr.user and pr.user.login == username:
                        if pr.created_at >= start_date:
                            prs_created += 1
                            user_pr_sizes.append({
                                "additions": pr.additions,
                                "deletions": pr.deletions,
                            })
                        if pr.merged and pr.merged_at and pr.merged_at >= start_date:
                            prs_merged += 1
                            hours = (pr.merged_at - pr.created_at).total_seconds() / 3600
                            user_cycle_times.append(round(hours, 2))
                    
                    for review in pr_reviews_cache.get(pr.number, []):
                        if not review.user or review.user.login != username:
                            continue
                        sub = getattr(review, "submitted_at", None)
                        if sub is not None and sub >= start_date:
                            prs_reviewed += 1
                            state = (review.state or "").upper()
                            if state == "APPROVED":
                                user_review_states["approved"] += 1
                            elif state == "CHANGES_REQUESTED":
                                user_review_states["changes_requested"] += 1
                            else:
                                user_review_states["commented"] += 1
                
                # Total contributions: commits (includes all commits from merged PRs) + reviews
                # Note: We don't add prs_merged here because those commits are already counted in commit_count
                # PRs are tracked separately for process metrics but not double-counted in total
                total_contribs = commit_count + prs_reviewed
                
                contrib_progress = (contrib_idx / total_actors) * 100
                print(f"   [{contrib_progress:.0f}%] {contrib_idx}/{total_actors} - {name}: {commit_count} commits, {prs_created} PRs created, {prs_merged} PRs merged, {prs_reviewed} PR reviews")
                
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
                        if pr.user and pr.user.login == username:
                            if pr.created_at >= start_date:
                                pr_date = pr.created_at.strftime("%Y-%m-%d")
                                daily_contributions[username][pr_date]["prs_created"] += 1
                            if pr.merged and pr.merged_at and pr.merged_at >= start_date:
                                merge_date = pr.merged_at.strftime("%Y-%m-%d")
                                daily_contributions[username][merge_date]["prs_merged"] += 1
                    
                    for pr in recent_prs:
                        for review in pr_reviews_cache.get(pr.number, []):
                            if review.user and review.user.login == username:
                                sub = getattr(review, "submitted_at", None)
                                if sub is not None and sub >= start_date:
                                    rday = sub.strftime("%Y-%m-%d")
                                    daily_contributions[username][rday]["prs_reviewed"] += 1
                
                if user_cycle_times or user_pr_sizes or any(v > 0 for v in user_review_states.values()):
                    pr_metrics[username]["cycle_times_hours"].extend(user_cycle_times)
                    pr_metrics[username]["pr_sizes"].extend(user_pr_sizes)
                    for k, v in user_review_states.items():
                        pr_metrics[username]["reviews_given"][k] += v

            active_contributors = len([u for u in total_contributions if total_contributions[u]['total_contributions'] > 0])
            try:
                rate = g.get_rate_limit().core
                rate_info = f"API budget: {rate.remaining}/{rate.limit}"
            except Exception:
                rate_info = "API budget: unknown"
            print(f"   ✓ Repository completed. Active contributors: {active_contributors} | {rate_info}")
            
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
                },
                "pr_metrics": {u: dict(m) for u, m in pr_metrics.items()},
            }
            save_state(current_state)
            
            # Save progress data after each repository
            save_progress_data(total_contributions, user_profiles, daily_contributions, 
                              repo_contributions, ORG_NAME, start_date, processed_repos,
                              organization_repository_count=organization_repo_total,
                              pr_metrics=pr_metrics)
            
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
                  repo_contributions, ORG_NAME, start_date, processed_repos,
                  organization_repository_count=organization_repo_total,
                  pr_metrics=pr_metrics)

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
