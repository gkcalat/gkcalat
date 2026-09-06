import os
import math
import requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
USERNAME = os.environ.get("GH_USERNAME", "gkcalat")

GRAPHQL_URL = "https://api.github.com/graphql"

# GraphQL query requesting all contributions (including private via viewer context)
QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      restrictedContributionsCount
    }
    repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) {
      totalCount
    }
    pullRequests(states: [MERGED, OPEN]) {
      totalCount
    }
    repositories(first: 100, ownerAffiliations: OWNER) {
      nodes {
        stargazerCount
      }
    }
  }
}
"""

def fetch_data():
    headers = {
        "Authorization": f"bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.post(GRAPHQL_URL, json={"query": QUERY, "variables": {"login": USERNAME}}, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Query failed: {response.status_code}, {response.text}")
    return response.json()["data"]["user"]

def compute_percentile(data):
    cc = data["contributionsCollection"]
    
    # Sum both public and private/restricted contributions
    commits = cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
    prs = cc["totalPullRequestContributions"]
    reviews = cc["totalPullRequestReviewContributions"]
    issues = cc["totalIssueContributions"]
    stars = sum(repo["stargazerCount"] for repo in data["repositories"]["nodes"])

    # Composite weighted activity score
    score = (commits * 2.0) + (prs * 3.5) + (reviews * 4.0) + (issues * 1.5) + (stars * 0.5)

    # Scale factor for GitHub developer population distribution
    scale = 1250.0
    percentile = (1.0 - math.exp(-score / scale)) * 100.0
    top_percentage = max(0.01, 100.0 - percentile)

    # Japanese academic tier grading (similar to github-readme-stats)
    if top_percentage <= 1.0:
        tier = "S+"
    elif top_percentage <= 5.0:
        tier = "S"
    elif top_percentage <= 15.0:
        tier = "A+"
    elif top_percentage <= 30.0:
        tier = "A"
    elif top_percentage <= 50.0:
        tier = "B"
    else:
        tier = "C"

    return {
        "commits": commits,
        "prs": prs,
        "reviews": reviews,
        "issues": issues,
        "stars": stars,
        "score": round(score),
        "percentile": round(percentile, 2),
        "top_percentage": round(top_percentage, 2),
        "tier": tier
    }

def generate_svg(metrics):
    svg = f"""<svg width="495" height="195" viewBox="0 0 495 195" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .header {{ font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif; fill: #fe428e; }}
    .stat-label {{ font: 400 14px 'Segoe UI', Ubuntu, Sans-Serif; fill: #a9fef7; }}
    .stat-val {{ font: 700 14px 'Segoe UI', Ubuntu, Sans-Serif; fill: #ffffff; }}
    .rank-text {{ font: 700 32px 'Segoe UI', Ubuntu, Sans-Serif; fill: #f8d847; }}
    .rank-sub {{ font: 500 12px 'Segoe UI', Ubuntu, Sans-Serif; fill: #a9fef7; }}
  </style>
  <rect width="495" height="195" rx="10" fill="#141321" stroke="#fe428e" stroke-width="1"/>
  
  <text x="25" y="35" class="header">GitHub Contribution Ranking (All Repos)</text>
  
  <text x="25" y="70" class="stat-label">Total Commits (incl. Private):</text>
  <text x="260" y="70" class="stat-val">{metrics['commits']:,}</text>
  
  <text x="25" y="95" class="stat-label">Pull Requests Submitted:</text>
  <text x="260" y="95" class="stat-val">{metrics['prs']:,}</text>
  
  <text x="25" y="120" class="stat-label">Code Reviews Given:</text>
  <text x="260" y="120" class="stat-val">{metrics['reviews']:,}</text>
  
  <text x="25" y="145" class="stat-label">Issues Opened:</text>
  <text x="260" y="145" class="stat-val">{metrics['issues']:,}</text>

  <text x="25" y="170" class="stat-label">Global Percentile Standing:</text>
  <text x="260" y="170" class="stat-val">{metrics['percentile']}%</text>

  <!-- Circular Tier Badge -->
  <circle cx="410" cy="95" r="45" stroke="#fe428e" stroke-width="4" fill="#1a1829"/>
  <text x="410" y="105" text-anchor="middle" class="rank-text">{metrics['tier']}</text>
  <text x="410" y="160" text-anchor="middle" class="rank-sub">Top {metrics['top_percentage']}%</text>
</svg>"""
    with open("percentile-card.svg", "w", encoding="utf-8") as f:
        f.write(svg)

if __name__ == "__main__":
    data = fetch_data()
    metrics = compute_percentile(data)
    generate_svg(metrics)
    print(f"Generated percentile card: Top {metrics['top_percentage']}% (Rank {metrics['tier']})")
