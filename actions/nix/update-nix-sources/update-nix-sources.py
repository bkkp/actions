#!/usr/bin/env python
import typer
import requests
import subprocess
import json
import re
from typing import NamedTuple, Any, Optional
import os
import sys



# --- Git functions
class GitRemoteInfo(NamedTuple):
  owner: str
  name: str

def git_remote_info() -> GitRemoteInfo:
  response = subprocess.run(["git", "remote", "get-url", "origin"], check=True, capture_output=True)
  stdout = response.stdout.decode().lstrip()
  return GitRemoteInfo(*re.match(r"https://github.com/(\w+)/(\w+).git", stdout).groups())

def git_checkout_branch(branch:str) -> None:
  try:
    subprocess.run(["git", "checkout", branch], check=True)
  except subprocess.CalledProcessError:
    try:
      subprocess.run(["git", "checkout", "-b", branch], check=True)
    except subprocess.CalledProcessError as e:
      raise Exception(f"Failed to checkout or create branch {branch}")

def git_add() -> None:
  subprocess.run(["git", "add", "."], check=True)

def git_commit(username:str , email: str, msg: str) -> None:
  try:
    response = subprocess.run(["git", "diff", "--staged", "--quiet"], check=True)
    # exit code 1 => somthing to commit
    # exit code 0 => nothing to commit
  except subprocess.CalledProcessError as e:
    if e.returncode == 1: # => there is files to be commited
      subprocess.run(
        ["git", "-c", f"user.name={username}", "-c", f"user.email={email}", "commit", "-m", msg],
        check=True
      )
    else:
      raise e

def git_force_push(branch) -> None:
  subprocess.run(["git", "push", "--set-upstream", "origin", f"{branch}", "--force"], check=True)



# --- Interact with GitHub
class GhRepoInfo(NamedTuple):
  id: str
  default_branch: str

class GhRequestError(Exception):
  def __init__(self, errors, raw):
    self.errors = errors
    self.raw = raw

  def __str__(self):
    l = []
    for e in self.errors:
      l.append(e["message"])
    return str(l)

def gh_api_request(query: str) -> dict[str, Any]:
  r = requests.post(
    url="https://api.github.com/graphql",
    headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}"},
    json={"query": query}
  )
  r.raise_for_status()
  response =  r.json()
  if "errors" in response:
    raise GhRequestError(response["errors"], response)
  else:
    return response

def gh_repo_info() -> GhRepoInfo:
  owner, gh_repo_name = git_remote_info()

  repo_query = f"""
    query {{
      repository(name: "{gh_repo_name}", owner: "{owner}") {{
        id
        defaultBranchRef {{
          name
        }}
      }}
    }}
    """

  try:
    response = gh_api_request(repo_query)
  except GhRequestError as e:
    raise e
  else:
    parsed = GhRepoInfo(
      id=response["data"]["repository"]["id"],
      default_branch=response["data"]["repository"]["defaultBranchRef"]["name"]
    )
    return parsed

def make_pull_request(
  title:str,
  body:str,
  head_branch:str,
  base_branch:Optional[str] = None
) -> None:
  repo = gh_repo_info()

  if base_branch is None:
    base_branch = repo.default_branch

  create_pr_query = f"""
    mutation MakePR {{
      createPullRequest (input:{{
        headRefName:"{head_branch}",
        baseRefName:"{base_branch}",
        title:"{title}",
        body:"{body}",
        repositoryId: "{repo.id}"}}
      )
      {{
        pullRequest {{ title, number }}
      }}
    }}"""

  try:
    response = gh_api_request(create_pr_query)
  except GhRequestError as e:
    if len(e.errors) == 1:
      msg = e.errors[0]["message"]
      if msg.startswith("A pull request already exists for"):
        typer.echo(msg)
      else:
        raise e
    else:
      raise e
  else:
    typer.echo(response["data"])



def niv(cmd:str) -> None:
  subprocess.run(["niv", cmd], check=True)



def main(
  branch:str = "bot/update-nix-sources7",
  pr_title:str = "[bot] Update nix sources",
  pr_body:str = "This is a automatic generatet PR, with updates to nix sources.",
  commiter_username:str = "GitHub",
  commiter_email:str = "noreply@github.com",
  github_token: Optional[str] = typer.Argument(None, envvar="GITHUB_TOKEN")
):
  if github_token is None:
      typer.secho("# >>> GITHUB TOKEN MISSING: Add token to cli arg github_token or set env variable GITHUB_TOKEN", fg=typer.colors.RED)
      sys.exit(1)
  else:
    os.environ["GITHUB_TOKEN"] = github_token

  typer.secho("\n# >>> Checkout or create PR brnach", fg=typer.colors.BLUE)
  git_checkout_branch(branch)

  typer.secho("\n# >>> Update sources.nix", fg=typer.colors.BLUE)
  niv("init")
  git_add()
  git_commit(commiter_username, commiter_email, "Update sources.nix")

  typer.secho("\n# >>> Update nix sources", fg=typer.colors.BLUE)
  niv("update")
  git_add()
  git_commit(commiter_username, commiter_email, "Update nix sources")

  typer.secho("\n# >>> Force push", fg=typer.colors.BLUE)
  git_force_push(branch)

  typer.secho("\n# >>> Make PR", fg=typer.colors.BLUE)
  make_pull_request(
    title=pr_title,
    body=pr_body,
    head_branch=branch,
  )


if __name__ == "__main__":
  typer.run(main)
