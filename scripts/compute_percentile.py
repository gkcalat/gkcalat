import os
import math
import requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GRAPHQL_URL = "https://api.github.com/graphql"

# 1. Query general stats and the list of active contribution years
QUERY_OVERVIEW = """
query {
  viewer {
    login
    contributionsCollection {
      contributionYears
    }
    repositoriesContributedTo(first: 100, contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) {
      totalCount
    }
    repositories(first: 100, ownerAffiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER]) {
      nodes {
        stargazerCount
      }
    }
  }
}
"""

# 2. Query contribution stats for a specific 1-year window
QUERY_YEAR = """
query($from: DateTime!, $to: DateTime!) {
  viewer {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      restrictedContributionsCount
    }
  }
}
"""

def run_query(query, variables=None):
    headers = {
        "Authorization": f"bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.post(GRAPHQL_URL, json={"query": query, "variables": variables or {}}, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(f"GraphQL request failed [{response.status_code}]: {response.text}")
    payload = response.json()
    if "errors" in payload:
        raise RuntimeError(f"GraphQL errors returned: {payload['errors']}")
    return payload["data"]["viewer"]

def fetch_all_lifetime_data():
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN environment variable is not set.")

    overview = run_query(QUERY_OVERVIEW)
    years = overview["contributionsCollection"]["contributionYears"]

    total_commits = 0
    total_prs = 0
    total_reviews = 0
    total_issues = 0

    # Aggregate across all years to match lowlighter/metrics all-time counts
    for year in years:
        from_date = f"{year}-01-01T00:00:00Z"
        to_date = f"{year}-12-31T23:59:59Z"
        year_data = run_query(QUERY_YEAR, {"from": from_date, "to": to_date})
        cc = year_data["contributionsCollection"]

        public_commits = cc["totalCommitContributions"]
        private_commits = cc.get("restrictedContributionsCount", 0)
        total_commits += (public_commits + private_commits)

        total_prs += cc["totalPullRequestContributions"]
        total_reviews += cc["totalPullRequestReviewContributions"]
        total_issues += cc["totalIssueContributions"]

    repos_contributed = overview["repositoriesContributedTo"]["totalCount"]
    stars = sum(repo["stargazerCount"] for repo in overview["repositories"]["nodes"])

    return {
        "commits": total_commits,
        "prs": total_prs,
        "reviews": total_reviews,
        "issues": total_issues,
        "repos_contributed": repos_contributed,
        "stars": stars
    }

def standard_normal_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def compute_metrics(data):
    commits = data["commits"]
    prs = data["prs"]
    reviews = data["reviews"]
    issues = data["issues"]

    # AI-era scoring model
    commit_score = 15.0 * math.sqrt(max(0, commits))
    pr_score = prs * 4.0
    review_score = reviews * 7.0
    issue_score = issues * 2.0
    star_score = min(500.0, data["stars"] * 1.0)

    base_score = commit_score + pr_score + review_score + issue_score + star_score
    breadth_factor = 1.0 + min(0.30, math.log10(max(1, data["repos_contributed"])) * 0.12)
    composite_score = base_score * breadth_factor

    # Active engineer benchmark calibration (~8M developers)
    mu = 6.1
    sigma = 1.15

    z = (math.log(max(1.0, composite_score)) - mu) / sigma
    percentile = standard_normal_cdf(z) * 100.0
    top_percentage = max(0.05, round(100.0 - percentile, 2))

    if top_percentage <= 1.0:
        tier = "S+"
    elif top_percentage <= 3.5:
        tier = "S"
    elif top_percentage <= 10.0:
        tier = "A+"
    elif top_percentage <= 25.0:
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
        "score": round(composite_score),
        "percentile": round(percentile, 1),
        "top_percentage": top_percentage,
        "tier": tier,
    }

def generate_svg(m):
    svg = f"""<svg width="495" height="195" viewBox="0 0 495 195" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .header {{ font: 600 17px 'Segoe UI', Ubuntu, Sans-Serif; fill: #fe428e; }}
    .subtitle {{ font: 400 11px 'Segoe UI', Ubuntu, Sans-Serif; fill: #7970a9; }}
    .stat-label {{ font: 400 13px 'Segoe UI', Ubuntu, Sans-Serif; fill: #a9fef7; }}
    .stat-val {{ font: 700 13px 'Segoe UI', Ubuntu, Sans-Serif; fill: #ffffff; }}
    .rank-text {{ font: 700 34px 'Segoe UI', Ubuntu, Sans-Serif; fill: #f8d847; }}
    .rank-sub {{ font: 600 12px 'Segoe UI', Ubuntu, Sans-Serif; fill: #fe428e; }}
  </style>

  <rect width="495" height="195" rx="10" fill="#141321" stroke="#fe428e" stroke-width="1"/>
  
  <text x="25" y="30" class="header">GitHub Standing (Active Developer Index)</text>
  <text x="25" y="46" class="subtitle">AI-era calibrated: lifetime human reviews, PR shipping &amp; commits</text>
  
  <text x="25" y="78" class="stat-label">Total Commits (All Repos):</text>
  <text x="235" y="78" class="stat-val">{m['commits']:,}</text>
  
  <text x="25" y="102" class="stat-label">Pull Requests Merged/Open:</text>
  <text x="235" y="102" class="stat-val">{m['prs']:,}</text>
  
  <text x="25" y="126" class="stat-label">Code Reviews Given:</text>
  <text x="235" y="126" class="stat-val">{m['reviews']:,}</text>
  
  <text x="25" y="150" class="stat-label">Issues Triaged &amp; Opened:</text>
  <text x="235" y="150" class="stat-val">{m['issues']:,}</text>

  <text x="25" y="174" class="stat-label">Percentile:</text>
  <text x="235" y="174" class="stat-val">{m['percentile']}%</text>

  <!-- Circular Tier Badge -->
  <circle cx="410" cy="98" r="42" stroke="#fe428e" stroke-width="3" fill="#1a1829"/>
  <text x="410" y="110" text-anchor="middle" class="rank-text">{m['tier']}</text>
  <text x="410" y="162" text-anchor="middle" class="rank-sub">Top {m['top_percentage']}%</text>
</svg>"""

    with open("percentile-card.svg", "w", encoding="utf-8") as f:
        f.write(svg)

if __name__ == "__main__":
    data = fetch_all_lifetime_data()
    metrics = compute_metrics(data)
    generate_svg(metrics)
    print(f"Computed Lifetime Commits: {metrics['commits']}")
    print(f"Generated card: Top {metrics['top_percentage']}% | Tier {metrics['tier']}")
