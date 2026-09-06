import os
import math
import requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GRAPHQL_URL = "https://api.github.com/graphql"

QUERY = """
query {
  viewer {
    login
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      restrictedContributionsCount
    }
    repositoriesContributedTo(first: 100, contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) {
      totalCount
    }
    pullRequests(states: [MERGED, OPEN]) {
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

def fetch_data():
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN environment variable is not set.")

    headers = {
        "Authorization": f"bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.post(GRAPHQL_URL, json={"query": QUERY}, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(f"GraphQL request failed [{response.status_code}]: {response.text}")

    payload = response.json()
    if "errors" in payload:
        raise RuntimeError(f"GraphQL errors returned: {payload['errors']}")

    return payload["data"]["viewer"]

def standard_normal_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def compute_metrics(data):
    cc = data["contributionsCollection"]

    public_commits = cc["totalCommitContributions"]
    private_commits = cc.get("restrictedContributionsCount", 0)
    all_commits = public_commits + private_commits

    prs = cc["totalPullRequestContributions"]
    reviews = cc["totalPullRequestReviewContributions"]
    issues = cc["totalIssueContributions"]

    repos_contributed = data["repositoriesContributedTo"]["totalCount"]
    stars = sum(repo["stargazerCount"] for repo in data["repositories"]["nodes"])

    # AI-era recalibrated scoring
    commit_score = 15.0 * math.sqrt(max(0, all_commits))
    pr_score = prs * 4.0
    review_score = reviews * 7.0
    issue_score = issues * 2.0
    star_score = min(500.0, stars * 1.0)

    base_score = commit_score + pr_score + review_score + issue_score + star_score

    breadth_factor = 1.0 + min(0.30, math.log10(max(1, repos_contributed)) * 0.12)
    composite_score = base_score * breadth_factor

    # Log-normal CDF calibrated against ~8M active engineers
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
        "commits": all_commits,
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
  <text x="25" y="46" class="subtitle">AI-era calibrated: human reviews, PR shipping &amp; sublinear commits</text>
  
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
    data = fetch_data()
    metrics = compute_metrics(data)
    generate_svg(metrics)
    print(f"Generated percentile card: Top {metrics['top_percentage']}% | Tier {metrics['tier']} | Percentile {metrics['percentile']}%")
