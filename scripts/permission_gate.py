# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/permission_gate.py
"""Claude Code PreToolUse hook: answer every tool call with *allow* or *deny* (CLAUDE.md §13.2).

Golden rule: anything outside this project's realm is denied; everything inside is
allowed, so Quan is never asked. The realm is:

* files under the project root, sibling ``vibechem*`` worktrees, Claude Code's own
  folders (``~/.claude``, the ``claude`` temp/scratchpad folder) and the gstack/Bun
  folders gstack needs (``~/.gstack``, ``~/.bun``);
* GitHub through ``gh``, web search/fetch, Context7 and Claude Docs;
* package tools working on the project (``uv``, ``pnpm``, ``npx``).

Inside the realm a few irreversible actions are still denied, matching CLAUDE.md §4:
pushes to ``main``/``phase-*`` (except creating a new phase branch), force pushes,
history rewrites, ``gh pr merge`` (use ``scripts/merge_step.py``), repository
settings and secrets, ``.env`` files, gstack shipping commands, and edits to this
gate or the Claude settings (Quan's action).

Input: the hook JSON on stdin. Output: one ``hookSpecificOutput`` JSON object.
Any internal error is a deny ("fail closed"). Standard library only.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

ALLOWED_MCP_PREFIXES = ("mcp__context7__", "mcp__claude_ai_Claude_Docs__")
ALLOWED_MCP_SERVERS = ("context7",)
FORBIDDEN_SKILLS = frozenset(
    {
        "ship",
        "land-and-deploy",
        "modernize",
        "pair-agent",
        "ubicloud",
        "setup-gbrain",
        "setup-browser-cookies",
        "canary",
        "crew",
        "setup-deploy",
    }
)
ALLOWED_DOWNLOAD_HOSTS = (
    "bun.sh",
    "github.com",
    "raw.githubusercontent.com",
    "objects.githubusercontent.com",
    "pypi.org",
    "files.pythonhosted.org",
    "registry.npmjs.org",
    "astral.sh",
)
PROTECTED_FILES = ("settings.json", "settings.local.json", "permission_gate.py")
SYSTEM_TOOLS = frozenset(
    {
        "sudo",
        "runas",
        "setx",
        "reg",
        "schtasks",
        "shutdown",
        "winget",
        "choco",
        "scoop",
        "format",
        "diskpart",
        "ngrok",
        "headroom",
        "gstack-team-init",
    }
)
SAFE_DEVICES = ("/dev/null", "/dev/stdin", "/dev/stdout", "/dev/stderr")
UNIX_SYSTEM_DIRS = ("/etc", "/usr", "/home", "/var", "/opt", "/root", "/users", "/mnt", "/proc")
SEGMENT_SPLIT = re.compile(r"&&|\|\||[;|\n&]")
URL = re.compile(r"https?://([^/\s'\"]+)", re.IGNORECASE)
PROTECTED_BRANCH = re.compile(r"^(refs/heads/)?(main|master|phase-\d+)$")
REDIRECT = re.compile(r">>?\s*['\"]?([^\s'\";|&]+)")
WINDOWS_PATH = re.compile(r"\b[A-Za-z]:\\[^\s'\"]*")
WRITERS = frozenset({"tee", "mv", "cp", "rm", "truncate", "dd", "install", "ln"})

Decision = tuple[str, str]  # ("allow" | "deny", reason)
ALLOW: Decision = ("allow", "inside the VibeChem realm")


# --- paths -----------------------------------------------------------------


def norm(path: str, home: str) -> str:
    """Lower-case Windows-style absolute form of ``path`` (Git Bash ``/c/x`` -> ``c:/x``)."""
    p = path.strip().strip("'\"").replace("\\", "/")
    if p.startswith("~"):
        p = home.replace("\\", "/") + p[1:]
    p = re.sub(r"^\$(HOME|\{HOME\})", home.replace("\\", "/"), p)
    m = re.match(r"^/([a-zA-Z])(/|$)", p)
    if m:
        p = f"{m.group(1)}:/{p[3:]}"
    if re.match(r"^[a-zA-Z]:", p):
        parts = PureWindowsPath(p).parts
        resolved: list[str] = []
        for part in parts[1:]:
            if part == "..":
                if resolved:
                    resolved.pop()
            elif part != ".":
                resolved.append(part)
        p = "/".join([parts[0].rstrip("\\/").replace("\\", "/"), *resolved])
    else:
        p = str(PurePosixPath(p))
    return p.lower().rstrip("/")


def roots(project: str, home: str, temp: str) -> list[str]:
    """Allowed root folders, normalised."""
    project_n = norm(project, home)
    found = [
        project_n,
        norm(f"{home}/.claude", home),
        norm(f"{home}/.gstack", home),
        norm(f"{home}/.bun", home),
        norm(f"{temp}/claude", home),
    ]
    parent, _, name = project_n.rpartition("/")
    found.append(f"{parent}/{name}-")  # sibling worktrees: c:/dev/vibechem-t0-06
    return found


def inside(path: str, allowed: Sequence[str], home: str, cwd: str) -> bool:
    """True if ``path`` (absolute or relative to ``cwd``) lies in an allowed root."""
    raw = path.strip().strip("'\"")
    if raw.replace("\\", "/") in SAFE_DEVICES:
        return True
    if not is_absolute(raw):
        raw = f"{cwd}/{raw}"
    p = norm(raw, home)
    for root in allowed:
        if root.endswith("-"):
            if p.startswith(root):
                return True
        elif p == root or p.startswith(root + "/"):
            return True
    return False


def is_absolute(token: str) -> bool:
    t = token.replace("\\", "/")
    return bool(re.match(r"^([a-zA-Z]:/|/|~|\$HOME|\$\{HOME\})", t))


def looks_like_path(token: str) -> bool:
    """Absolute paths and ``..`` escapes worth checking; ignores flags, URLs and regexes."""
    t = token  # split_tokens already turned C:\x into C:/x; '\n' must not read as /n
    if "://" in t or t.startswith("-"):
        return False
    if re.match(r"^([a-zA-Z]:/|~|\$HOME|\$\{HOME\})", t):
        return True
    if re.match(r"^/[a-zA-Z](/|$)", t) or t.startswith("/tmp"):
        return True
    if t.lower().startswith(UNIX_SYSTEM_DIRS):
        return True
    return t == ".." or t.startswith("../") or "/../" in t


# --- Bash ------------------------------------------------------------------


def split_tokens(segment: str) -> list[str]:
    # Keep Windows paths (C:\x) through shlex; other backslashes ('\n', '\|') stay as they are.
    segment = WINDOWS_PATH.sub(lambda m: m.group(0).replace("\\", "/"), segment)
    try:
        tokens = shlex.split(segment, posix=True)
    except ValueError:
        tokens = segment.split()
    while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
        tokens = tokens[1:]  # leading VAR=value assignments
    return tokens


def program(tokens: list[str]) -> str:
    return PurePosixPath(tokens[0].replace("\\", "/")).name.lower().removesuffix(".exe")


def writes_protected(command: str) -> bool:
    """True if the command writes to a protected file (redirect, writer tool, in-place edit)."""
    if any(p in t for t in REDIRECT.findall(command) for p in PROTECTED_FILES):
        return True
    for segment in SEGMENT_SPLIT.split(command):
        tokens = split_tokens(segment)
        if not tokens or not any(p in t for t in tokens[1:] for p in PROTECTED_FILES):
            continue
        prog = program(tokens)
        in_place = prog in {"sed", "perl"} and any(
            t.startswith("-i") or t == "--in-place" for t in tokens[1:]
        )
        if (
            prog in WRITERS
            or in_place
            or (prog in {"python", "python3", "node"} and "-c" in tokens)
        ):
            return True
    return False


def check_bash(command: str, ctx: Mapping[str, Any]) -> Decision:
    cmd_lower = command.lower()
    if writes_protected(command):
        return ("deny", "changing the Claude settings or the permission gate is Quan's action")
    if re.search(r"(^|[\s/'\"])\.env(\.[\w.-]+)?($|[\s'\"])", command) and ".env.example" not in (
        command
    ):
        return ("deny", ".env files are never read (CLAUDE.md §4)")
    for host in URL.findall(command):
        if re.search(r"\b(curl|wget|irm|iwr|invoke-webrequest|invoke-restmethod)\b", cmd_lower):
            bare = host.lower().split(":")[0]
            if not any(bare == h or bare.endswith("." + h) for h in ALLOWED_DOWNLOAD_HOSTS):
                return ("deny", f"downloads only from known installer hosts, not {bare}")
    for segment in SEGMENT_SPLIT.split(command):
        tokens = split_tokens(segment)
        if not tokens:
            continue
        decision = check_segment(tokens, ctx)
        if decision[0] == "deny":
            return decision
    return ALLOW


def check_segment(tokens: list[str], ctx: Mapping[str, Any]) -> Decision:
    for token in tokens:
        for part in token.split("=", 1)[-1:] if token.startswith("-") else [token]:
            if looks_like_path(part) and not inside(part, ctx["roots"], ctx["home"], ctx["cwd"]):
                return ("deny", f"path outside the project: {part}")
    prog = PurePosixPath(tokens[0].replace("\\", "/")).name.lower().removesuffix(".exe")
    args = tokens[1:]
    if prog in SYSTEM_TOOLS:
        return ("deny", f"{prog} changes the machine, not the project")
    if prog in {"npm", "pnpm", "yarn", "bun"} and ({"-g", "--global"} & set(args)):
        return ("deny", "global installs change the machine, not the project")
    if prog == "uv" and args[:2] == ["tool", "install"]:
        return ("deny", "global installs change the machine, not the project")
    if prog in {"pip", "pip3"} and "--user" in args:
        return ("deny", "global installs change the machine, not the project")
    if prog in {"npx", "pnpm"} and "impeccable" in args:
        sub = args[args.index("impeccable") + 1 :]
        if sub[:1] in (["live"], ["install"]) or sub[:2] == ["telemetry", "on"]:
            return ("deny", "Impeccable live/install/telemetry are not used (TOOLS.md §2)")
    if prog == "rm":
        return check_rm(args, ctx)
    if prog == "git":
        return check_git(args, ctx)
    if prog == "gh":
        return check_gh(args)
    return ALLOW


def check_rm(args: list[str], ctx: Mapping[str, Any]) -> Decision:
    targets = [a for a in args if not a.startswith("-")]
    project = ctx["roots"][0]
    for t in targets:
        if t in {"/", "*", ".", "~", "./", "/*"}:
            return ("deny", f"rm {t} would delete the whole tree")
        p = norm(t if is_absolute(t) else f"{ctx['cwd']}/{t}", ctx["home"])
        if p in {project, f"{project}/.git"} or p.endswith("/.git"):
            return ("deny", "rm of the project root or .git")
    return ALLOW


def git_subcommand(args: list[str]) -> tuple[str, list[str]]:
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in {"-C", "-c"} else 1
    if i >= len(args):
        return "", []
    return args[i], args[i + 1 :]


def check_git(args: list[str], ctx: Mapping[str, Any]) -> Decision:
    sub, rest = git_subcommand(args)
    flags = [a for a in rest if a.startswith("-")]
    if sub == "push":
        return check_push(rest, ctx)
    if sub == "reset" and {"--hard", "--merge", "--keep"} & set(flags):
        return ("deny", "git reset --hard discards work (CLAUDE.md §4)")
    if sub == "clean" and any(f == "--force" or re.match(r"^-[a-z]*f", f) for f in flags):
        return ("deny", "git clean -f deletes untracked work")
    if sub in {"rebase", "filter-branch", "filter-repo", "replace"}:
        return ("deny", "history rewrites are not allowed (CLAUDE.md §4)")
    if sub == "stash" and rest[:1] in (["drop"], ["clear"]):
        return ("deny", "dropping a stash discards work")
    if sub == "branch" and ("-D" in flags or ("--delete" in flags and "--force" in flags)):
        return ("deny", "force-deleting a branch; use -d on your own merged branch")
    if sub == "config" and {"--global", "--system"} & set(flags):
        return ("deny", "global git config is outside the project")
    return ALLOW


def check_push(rest: list[str], ctx: Mapping[str, Any]) -> Decision:
    for flag in rest:
        if flag in {"-f", "--force", "--mirror", "--delete", "-d", "--prune"} or flag.startswith(
            "--force-with-lease"
        ):
            return ("deny", f"git push {flag} is not allowed (CLAUDE.md §4)")
    positional = [a for a in rest if not a.startswith("-")]
    refspecs = positional[1:]
    if not refspecs or refspecs == ["HEAD"]:
        refspecs = [ctx["branch"]()]
    for spec in refspecs:
        if spec.startswith("+"):
            return ("deny", "forced refspec push is not allowed")
        dest = spec.split(":")[-1]
        if dest == "HEAD":
            dest = ctx["branch"]()
        if PROTECTED_BRANCH.match(dest):
            if re.match(r"^(refs/heads/)?phase-\d+$", dest) and not ctx["remote_has"](dest):
                continue  # creating a new phase branch (CLAUDE.md §14.1 step 2)
            return ("deny", f"pushing to {dest} is Quan's action or merge_step.py's (§4, §14.2)")
    return ALLOW


def check_gh(args: list[str]) -> Decision:
    group, sub = [*args, "", ""][:2]
    if group == "pr" and sub == "merge":
        return ("deny", "merge only through scripts/merge_step.py (CLAUDE.md §14.2)")
    if group == "repo" and sub in {"delete", "edit", "rename", "archive", "unarchive"}:
        return ("deny", "repository settings are not changed by Claude (CLAUDE.md §4)")
    if group in {"secret", "variable"} and sub not in {"list", ""}:
        return ("deny", "secrets and variables are not changed by Claude")
    if group == "secret":
        return ("deny", "secrets are not touched by Claude")
    if group == "label" and sub in {"delete", "edit"}:
        return ("deny", "label meanings are not changed (CLAUDE.md §4)")
    if group == "auth" and sub in {"token", "logout", "refresh", "login"}:
        return ("deny", "gh credentials are Quan's")
    if group == "release" and sub in {"delete", "delete-asset"}:
        return ("deny", "deleting releases is Quan's action")
    if group == "api":
        return check_gh_api(args[1:])
    return ALLOW


def check_gh_api(args: list[str]) -> Decision:
    method = "GET"
    for i, a in enumerate(args):
        if a in {"-X", "--method"} and i + 1 < len(args):
            method = args[i + 1].upper()
        elif a.startswith("--method="):
            method = a.split("=", 1)[1].upper()
        elif a in {"-f", "-F", "--field", "--raw-field", "--input"} and method == "GET":
            method = "POST"
    endpoint = next((a for a in args if not a.startswith("-")), "")
    if endpoint == "graphql":
        return ("deny", "graphql mutation") if "mutation" in " ".join(args) else ALLOW
    if method != "GET":
        return ("deny", f"gh api {method} changes GitHub state; use gh pr/issue commands")
    return ALLOW


# --- other tools -----------------------------------------------------------


def path_args(tool_input: Mapping[str, Any]) -> Iterable[str]:
    for key in ("file_path", "path", "notebook_path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            yield value
    pattern = tool_input.get("pattern")
    if isinstance(pattern, str) and is_absolute(pattern):
        yield pattern.split("*")[0] or pattern


def decide(event: Mapping[str, Any], ctx: Mapping[str, Any]) -> Decision:
    tool = str(event.get("tool_name", ""))
    tool_input: Mapping[str, Any] = event.get("tool_input") or {}
    if tool.startswith("mcp__"):
        if tool.startswith(ALLOWED_MCP_PREFIXES):
            return ALLOW
        return ("deny", f"{tool.split('__')[1]} is outside the VibeChem realm")
    if tool in {"ListMcpResourcesTool", "ReadMcpResourceTool", "ReadMcpResourceDirTool"}:
        server = str(tool_input.get("server", ""))
        return ALLOW if server in ALLOWED_MCP_SERVERS else ("deny", "MCP server outside realm")
    if tool == "Skill":
        name = str(tool_input.get("skill", "")).split(":")[-1].lower()
        if name in FORBIDDEN_SKILLS:
            return ("deny", f"gstack /{name} ships or deploys; not used (TOOLS.md §2)")
        return ALLOW
    if tool in {"Bash", "PowerShell"}:
        return check_bash(str(tool_input.get("command", "")), ctx)
    for p in path_args(tool_input):
        if not inside(p, ctx["roots"], ctx["home"], ctx["cwd"]):
            return ("deny", f"path outside the project: {p}")
        name = PurePosixPath(p.replace("\\", "/")).name
        if tool in {"Edit", "Write", "NotebookEdit"} and (
            name in PROTECTED_FILES and (".claude" in p or "scripts" in p)
        ):
            return ("deny", "changing the Claude settings or the permission gate is Quan's action")
        if re.fullmatch(r"\.env(\.[\w.-]+)?", name) and name != ".env.example":
            return ("deny", ".env files are never read (CLAUDE.md §4)")
    return ALLOW


def git_output(cwd: str, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", cwd, *args], capture_output=True, text=True, timeout=15, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def make_context(event: Mapping[str, Any], env: Mapping[str, str]) -> dict[str, Any]:
    home = env.get("USERPROFILE") or env.get("HOME") or str(Path.home())
    temp = env.get("TEMP") or env.get("TMP") or f"{home}/AppData/Local/Temp"
    project = env.get("CLAUDE_PROJECT_DIR") or str(PureWindowsPath(__file__).parents[1])
    cwd = str(event.get("cwd") or project)

    def branch() -> str:
        return git_output(cwd, "rev-parse", "--abbrev-ref", "HEAD") or "main"

    def remote_has(name: str) -> bool:
        short = name.removeprefix("refs/heads/")
        return bool(git_output(cwd, "ls-remote", "--heads", "origin", short)) or not (
            git_output(cwd, "remote")
        )

    return {
        "home": home,
        "cwd": cwd,
        "roots": roots(project, home, temp),
        "branch": branch,
        "remote_has": remote_has,
    }


def respond(decision: Decision) -> str:
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision[0],
                "permissionDecisionReason": f"VibeChem gate: {decision[1]}",
            }
        }
    )


def main() -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
        decision = decide(event, make_context(event, os.environ))
    except Exception as exc:  # noqa: BLE001 - fail closed on anything
        decision = ("deny", f"gate error ({type(exc).__name__}: {exc})")
    print(respond(decision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
