from github import Github
import getpass
from datetime import datetime, timedelta
from collections import defaultdict

# Ask the user to enter their GitHub personal access token
access_token = getpass.getpass("Enter your GitHub personal access token: ")

# Replace with the name of the organization
ORG_NAME = "htdc"

# Create a PyGitHub instance
g = Github(access_token)

# Get the organization
org = g.get_organization(ORG_NAME)

# Initialize a dictionary to store total contributions
total_contributions = defaultdict(lambda: {"name": "N/A", "contributions": 0})

# Set the default start date to 6 months ago
default_start_date = datetime.now() - timedelta(days=180)
start_date_str = default_start_date.strftime("%Y-%m-%d")

# Prompt the user for an alternate start date
alt_start_date = input(f"Enter an alternate start date (YYYY-MM-DD) or press Enter to use the default ({start_date_str}): ")
if alt_start_date:
    start_date = datetime.strptime(alt_start_date, "%Y-%m-%d")
else:
    start_date = default_start_date

# Get the list of repositories
repos = list(org.get_repos())
total_repos = len(repos)

print(f"Scanning {total_repos} repositories in the {ORG_NAME} organization since {start_date_str}...")

# Loop through all repositories in the organization
for idx, repo in enumerate(repos, start=1):
    repo_name = repo.full_name
    print(f"\nScanning repository {idx}/{total_repos}: {repo_name}")

    try:
        # Get all contributors for the current repository
        contributors = repo.get_contributors()

        # Loop through contributors and update total contributions
        for contributor in contributors:
            username = contributor.login
            name = contributor.name or "N/A"  # Use "N/A" if the name is not available
            
            # Get commits for this contributor since the start date
            commits = repo.get_commits(author=contributor, since=start_date)
            contributions = len(list(commits))
            print(f"\n\s\s\s {name}: {commits} commits")
            if contributions > 0:
                total_contributions[username]["name"] = name
                total_contributions[username]["contributions"] += contributions

        print(f"Repository has {len(total_contributions)} contributors since {start_date}.")
    except Exception as e:
        if hasattr(e, 'status') and e.status == 409 and "Git Repository is empty." in str(e.data):
            print("Skipping empty repository.")
        else:
            print(f"Error processing repository: {str(e)}")

# Sort the contributions in descending order
sorted_contributions = sorted(total_contributions.items(), key=lambda x: x[1]["contributions"], reverse=True)

# Save the output to a file named "output.csv"
with open("output.csv", "w") as file:
    file.write("Username,Name,Contributions\n")
    for username, data in sorted_contributions:
        file.write(f"{username},{data['name']},{data['contributions']}\n")

print("\nOutput saved to output.csv")
