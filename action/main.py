# https://josh-ops.com/posts/github-composite-action-python/

import os
import yaml
import re
import requests
import base64

GITHUB_API = "https://api.github.com"
OPENSSF_API = "https://api.securityscorecards.dev/projects/github.com"
COMMITS_NUM = 5 # number of commits to analyze

def find_used_actions():
    actions = set()
    for root, _, files in os.walk("../.github/"):
        for f in files:            
            if f.endswith((".yml", ".yaml")):
                try:
                    with open(os.path.join(root, f)) as wf:
                        data = yaml.safe_load(wf)
                        if not data: continue
                        for job in data.get("jobs", {}).values():
                            for step in job.get("steps", []):
                                if "uses" in step.keys():
                                    uses = step["uses"]
                                    m = re.match(r"([\w\-]+\/[\w\-]+)(?:@.+)?", uses)
                                    if m:
                                        actions.add(m.group(1))           
                except yaml.YAMLError as e:
                    print(f"Error parsing YAML file '{filepath}': {e}")
                    raise
    return actions


def get_repo_info(repo):
    out = {"latest_pushed_at": None, "is_archived": None, "is_bot":None, "error": None}
    r = requests.get(f"{GITHUB_API}/repos/{repo}")
    if r.status_code != 200:
        out["error"] = f"Error: {r.status_code}"
        return out

    repo_info = r.json()
    out["latest_pushed_at"] = repo_info.get("pushed_at", None)
    out["is_archived"] = repo_info.get("archived", False)

    # get last N commits to check committer id is [bot] or not
    commits = requests.get(f"{GITHUB_API}/repos/{repo}/commits?per_page={COMMITS_NUM}")
    if commits.status_code == 200 or len(commits.json()) == 0:
        bot_commits = 0
        for i in range(0, len(commits.json())):
            c = commits.json()[i]
            if "[bot]" in c['commit']['author']['name']:
                bot_commits = +1
        out["is_bot"] = False
        # if all last commits originated from bot
        if bot_commits == len(commits.json()):
            out["is_bot"] = True
    else:
        out["error"] = f"No commits found"
        return out
    return out


def get_openssf_score(repo):
    url = f"{OPENSSF_API}/{repo}"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        score = data.get("score", {})
        return {"openssf_score": score}
    return {"openssf_score": None}


def get_repo_readme(repo):
    """
    Fetches the raw content of the README.md file for a given GitHub repository 
    using the GitHub REST API.
    """
    N = 1000 # script analyzes first N symbols to aviod false positives
    deprecation_keywords = [
        "deprecation",
        "deprecated",
        "archive",
        "archived",
        "no longer maintained",
        "unmaintained",
        "read-only",
        "end-of-life",
        "eol",
        "superseded by",
        "replaced by",
        "historical purposes",
    ]
    r = requests.get(f"{GITHUB_API}/repos/{repo}/readme")
    if r.status_code != 200:
        return {"repo_status":None, "error": "Readme not found"}
    
    readme_path = r.json().get("download_url", None)
    if readme_path != None:
        r = requests.get(readme_path)
        if r.status_code != 200:
            return {"repo_status":None, "error": "Readme not found"}
        normalized_readme = r.text[0:N].lower()
    for keyword in deprecation_keywords:
        if keyword in normalized_readme:
            return {"repo_status":"Archived/Deprecated", "error": None}
    return {"repo_status":"Active", "error": None}




list_of_actions = find_used_actions()

for action in list_of_actions:
    out = {"action": action}
    out = out | get_repo_info(action)
    out = out | get_openssf_score(action)
    out = out | get_repo_readme(action)
    print (out)
