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
    headers = {
        "Authorization": f"bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.post(GRAPHQL_URL, json={"query": QUERY}, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Query failed: {response.status_code}, {response.text}")
    res_json = response.json()
    if "errors" in res_json:
        raise Exception(f"GraphQL Errors: {res_json['errors']}")
    return res_json["data"]["viewer"]


def standard_normal_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

  
def compute_metrics(data):
    cc = data["contributionsCollection"]
    
    public_commits = cc["totalCommitContributions"]
    prs = cc["totalPullRequestContributions"]
    reviews = cc["totalPullRequestReviewContributions"]
    issues = cc["totalIssueContributions"]
    public_total = public_commits + prs + reviews + issues

    private_total = cc.get("restrictedContributionsCount", 0)
    all_commits = public_commits + private_total

    # Proportional split
    grand_total = max(1, public_total + private_total)
    public_pct = round((public_total / grand_total) * 100, 1)
    private_pct = round((private_total / grand_total) * 100, 1)

    total_bar_w = 445
    public_bar_w = round((public_total / grand_total) * total_bar_w)
    private_bar_w = total_bar_w - public_bar_w

    repos_contributed = data["repositoriesContributedTo"]["totalCount"]
    stars = sum(repo["stargazerCount"] for repo in data["repositories"]["nodes"])

    # --- AI-Era Recalibrated Scoring ---
    # 1. Commits: Square-root damping. 500 commits = 335 pts; 2000 commits = 670 pts.
    #    Prevents automated agent churn from dominating the index.
    commit_score = 15.0 * math.sqrt(max(0, all_commits))

    # 2. Merged/Open PRs: Units of cohesive shipped work.
    pr_score = prs * 4.0

    # 3. Reviews: The human-in-the-loop verification bottleneck.
    review_score = reviews * 7.0

    # 4. Problem Definition & Triage.
    issue_score = issues * 2.0

    # 5. External Utility (Stars).
    star_score = min(500.0, stars * 1.0)

    base_score = commit_score + pr_score + review_score + issue_score + star_score

    # Cross-repo collaboration factor (damped logarithmic scale)
    breadth_factor = 1.0 + min(0.30, math.log10(max(1, repos_contributed)) * 0.12)
    composite_score = base_score * breadth_factor

    # --- Calibrated Power-Law / Log-Normal Hybrid CDF ---
    # Centered at median active engineer (composite_score ~ 450)
    # sigma = 1.15 produces a wider, more realistic elite spread
    mu = 6.1
    sigma = 1.15

    z = (math.log(max(1.0, composite_score)) - mu) / sigma
    percentile = standard_normal_cdf(z) * 100.0
    top_percentage = max(0.05, round(100.0 - percentile, 2))

    # Stricter realistic tier thresholds
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
        "public_total": public_total,
        "private_total": private_total,
        "public_pct": public_pct,
        "private_pct": private_pct,
        "public_bar_w": public_bar_w,
        "private_bar_w": private_bar_w,
    }


def generate_svg(m):
    svg = f"""<svg width="495" height="235" viewBox="0 0 495 235" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .header {{ font: 600 17px 'Segoe UI', Ubuntu, Sans-Serif; fill: #fe428e; }}
    .subtitle {{ font: 400 11px 'Segoe UI', Ubuntu, Sans-Serif; fill: #7970a9; }}
    .stat-label {{ font: 400 13px 'Segoe UI', Ubuntu, Sans-Serif; fill: #a9fef7; }}
    .stat-val {{ font: 700 13px 'Segoe UI', Ubuntu, Sans-Serif; fill: #ffffff; }}
    .rank-text {{ font: 700 32px 'Segoe UI', Ubuntu, Sans-Serif; fill: #f8d847; }}
    .rank-sub {{ font: 600 12px 'Segoe UI', Ubuntu, Sans-Serif; fill: #fe428e; }}
    .split-title {{ font: 600 12px 'Segoe UI', Ubuntu, Sans-Serif; fill: #ffffff; }}
    .split-meta {{ font: 400 11px 'Segoe UI', Ubuntu, Sans-Serif; fill: #7970a9; }}
    .legend-public {{ font: 600 11px 'Segoe UI', Ubuntu, Sans-Serif; fill: #a9fef7; }}
    .legend-private {{ font: 600 11px 'Segoe UI', Ubuntu, Sans-Serif; fill: #fe428e; }}
  </style>

  <rect width="495" height="235" rx="10" fill="#141321" stroke="#fe428e" stroke-width="1"/>
  
  <text x="25" y="32" class="header">GitHub Standing (Active Developer Index)</text>
  <text x="25" y="48" class="subtitle">AI-era weighted: human review, PR shipping, and org collaboration</text>
  
  <text x="25" y="78" class="stat-label">Total Commits (All Repos):</text>
  <text x="245" y="78" class="stat-val">{m['commits']:,}</text>
  
  <text x="25" y="100" class="stat-label">Pull Requests Merged/Open:</text>
  <text x="245" y="100" class="stat-val">{m['prs']:,}</text>
  
  <text x="25" y="122" class="stat-label">Code Reviews Given:</text>
  <text x="245" y="122" class="stat-val">{m['reviews']:,}</text>
  
  <text x="25" y="144" class="stat-label">Issues Triaged &amp; Opened:</text>
  <text x="245" y="144" class="stat-val">{m['issues']:,}</text>

  <text x="25" y="166" class="stat-label">Global Percentile Standing:</text>
  <text x="245" y="166" class="stat-val">{m['percentile']}%</text>

  <!-- Circular Tier Badge -->
  <circle cx="410" cy="95" r="42" stroke="#fe428e" stroke-width="3" fill="#1a1829"/>
  <text x="410" y="105" text-anchor="middle" class="rank-text">{m['tier']}</text>
  <text x="410" y="155" text-anchor="middle" class="rank-sub">Top {m['top_percentage']}%</text>

  <!-- Split Ratio Header -->
  <text x="25" y="195" class="split-title">Contribution Distribution</text>
  <text x="240" y="195" class="legend-public">● Public: {m['public_pct']}%</text>
  <text x="355" y="195" class="legend-private">● Private &amp; Org: {m['private_pct']}%</text>

  <!-- Segmented Progress Bar -->
  <clipPath id="bar-clip">
    <rect x="25" y="206" width="445" height="10" rx="5"/>
  </clipPath>
  
  <g clip-path="url(#bar-clip)">
    <rect x="25" y="206" width="445" height="10" fill="#242238"/>
    <rect x="25" y="206" width="{m['public_bar_w']}" height="10" fill="#a9fef7"/>
    <rect x="{25 + m['public_bar_w']}" y="206" width="{m['private_bar_w']}" height="10" fill="#fe428e"/>
  </g>
</svg>"""
    with open("percentile-card.svg", "w", encoding="utf-8") as f:
        f.write(svg)

if __name__ == "__main__":
    data = fetch_data()
    metrics = compute_metrics(data)
    generate_svg(metrics)
    print(f"Generated card: {metrics['public_pct']}% Public / {metrics['private_pct']}% Private & Org")
