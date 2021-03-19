#!/usr/bin/env python
import typer
import requests
import subprocess
import json
import re
from typing import NamedTuple, Any, Optional, Dict, List, Union
import os
import sys



# --- Git functions
class GitRemoteInfo(NamedTuple):
  owner: str
  name: str

def git_remote_info() -> GitRemoteInfo:
  response = subprocess.run(["git", "remote", "get-url", "origin"], check=True, capture_output=True)
  stdout = response.stdout.decode().lstrip()

  p = re.match(r"https://github.com/(\w+)/(\w+).git", stdout)
  if p is None:
    p = re.match(r"https://github.com/(\w+)/(\w+)", stdout)

  return GitRemoteInfo(*p.groups())

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

def gh_api_request(query: str, variables: dict = None) -> Dict[str, Any]:
  r = requests.post(
    url="https://api.github.com/graphql",
    headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}"},
    json={"query": query, "variables": variables}
  )
  r.raise_for_status()
  response =  r.json()
  if "errors" in response:
    raise GhRequestError(response["errors"], response)
  else:
    return response


def gh_repo_tags(name, owner, search_limit: str = 10) -> dict:
  """ Return mapping from oid to name for latest tags in a repository """
  tags_query = """
    query RefTags($owner: String!, $name: String!, $limit: Int!) {
      repository(owner: $owner, name: $name) {
        refs(
          refPrefix: "refs/tags/", 
          first: $limit, 
          orderBy: {field: TAG_COMMIT_DATE, direction: DESC}
        ) {
          nodes {
            name
            target { oid }
          }
        }
      }
    }
  """
  variables = {'name': name, 'owner': owner, 'limit': search_limit}
  response = gh_api_request(tags_query, variables)
  try:  # repository, refs and nodes may be None
    nodes = response['data']['repository']['refs']['nodes']
  except KeyError:
    return {}

  if not isinstance(nodes, list):
    return {}

  d = {}
  for node in nodes:
    d[node['target']['oid']] = node['name']
  
  return d



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
) -> Union[str, None]:
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
        pullRequest {{ title, number, id }}
      }}
    }}"""

  try:
    response = gh_api_request(create_pr_query)
  except GhRequestError as e:
    if len(e.errors) == 1:
      msg = e.errors[0]["message"]
      if msg.startswith("A pull request already exists for"):
        typer.echo(msg)
        return None
      else:
        raise e
    else:
      raise e
  else:
    typer.echo(response["data"])
    return response["data"]["createPullRequest"]["pullRequest"]["id"]

def gh_userid(user: str) -> str:
  user_query = f"""
    query {{ 
      user(login: "{user}") {{
        name
        id
      }}
    }}"""

  response = gh_api_request(user_query)
  typer.echo(response["data"])
  return response["data"]["user"]["id"]

def gh_add_pr_reviwers(pr_id: str, users: List[str]) -> None:
  _userids = []
  for user in users:
    userid = gh_userid(user)
    _userids.append(userid)
  
  userids = ", ".join(map(lambda x: '\"' + x + '\"', _userids)) 

  add_review_query = f"""
    mutation {{ 
      requestReviews(input:{{pullRequestId: "{pr_id}", union: true, userIds: [{userids}]}}) {{ 
        pullRequest {{
          title
          number
        }}
      }}
    }}"""
  response = gh_api_request(add_review_query)
  typer.echo(response["data"])


# --- Nix functions

def niv(*cmd: str) -> None:
    cmds = ["niv"] + list(cmd)
    subprocess.run(cmds, check=True)


class NivSourceInfo(NamedTuple):
  repo: str
  owner: str
  branch: str
  rev: str

def get_source_info(name: str, niv_path: str = 'nix/sources.json'):
  """ Get information about a nix source """
  with open(niv_path, 'r') as f:
    d = json.load(f)
  info = NivSourceInfo(
    repo=d[name]['repo'],
    owner=d[name]['owner'],
    branch=d[name]['branch'],
    rev=d[name]['rev'],
  )
  return info

def source_version(name: str, source_tags: dict):
  """ Determine version of source from its tags 
  
  Fall back to rev if tag is not found. Argument `source_tags` is a mapping from
  refs(rev's) to tag names.
  """
  source_info = get_source_info(name)
  version = source_tags.get(source_info.rev)
  if version is None:
    return source_info.rev
  else:
    return version


# --- Main function

def main(
  branch: str = "bot/update-nix-sources",
  pr_title: str = "[bot] Update nix sources",
  pr_body: str = "This is an automatic generated PR, with updates to nix sources.",
  commiter_username: str = "GitHub",
  commiter_email: str = "noreply@github.com",
  github_token: Optional[str] = typer.Argument(None, envvar="GITHUB_TOKEN"),
  reviewer: Optional[List[str]] = typer.Option(None),
  source: Optional[str] = typer.Option(None, help='Specific source to update, if omitted updates all'),
):
  if github_token is None:
      typer.secho("# >>> GITHUB TOKEN MISSING: Add token to cli arg github_token or set env variable GITHUB_TOKEN", fg=typer.colors.RED)
      sys.exit(1)
  else:
    os.environ["GITHUB_TOKEN"] = github_token

  typer.secho("\n# >>> Checkout or create PR branch", fg=typer.colors.BLUE)
  git_checkout_branch(branch)

  typer.secho("\n# >>> Update sources.nix", fg=typer.colors.BLUE)
  niv("init")
  git_add()
  git_commit(commiter_username, commiter_email, "Update sources.nix")

  typer.secho("\n# >>> Update nix sources", fg=typer.colors.BLUE)
  if source is None:
      niv("update") # Update all sources
      commit_msg = 'Update all nix sources'
  else:
      source_info = get_source_info(source)
      source_tags = gh_repo_tags(source_info.repo, source_info.owner)
      old_version = source_version(source, source_tags)
      niv("update", source)
      new_version = source_version(source, source_tags)
      commit_msg = f'{source}: {old_version} -> {new_version}'

  git_add()
  git_commit(commiter_username, commiter_email, commit_msg)

  typer.secho("\n# >>> Force push", fg=typer.colors.BLUE)
  git_force_push(branch)

  typer.secho("\n# >>> Make PR", fg=typer.colors.BLUE)
  pr_id = make_pull_request(
    title=pr_title,
    body=pr_body,
    head_branch=branch,
  )

  if (pr_id is not None) & (reviewer is not None):
    typer.secho("\n# >>> Add reviewer to PR", fg=typer.colors.BLUE)
    gh_add_pr_reviwers(pr_id, users=reviewer)


if __name__ == "__main__":
  typer.run(main)
