"""Persist the report and immutable history on the dedicated data branch."""
from pathlib import Path
import shutil
import subprocess
import tempfile


def git(*args, check=True, cwd=None):
    return subprocess.run(["git", *args], check=check, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


root = Path.cwd()
temporary = Path(tempfile.mkdtemp(prefix="mister-mi-data-"))
destination = temporary / "checkout"
existing = git("fetch", "origin", "data", check=False).returncode == 0
try:
    git("worktree", "add", "--detach", str(destination), "FETCH_HEAD" if existing else "HEAD")
    if not existing:
        git("switch", "--orphan", "data", cwd=destination)
    for name in ["consenso_hoje.json", "history.json"]:
        shutil.copyfile(root / "web" / "data" / name, destination / name)
    git("add", "consenso_hoje.json", "history.json", cwd=destination)
    if git("diff", "--cached", "--quiet", check=False, cwd=destination).returncode:
        git("-c", "user.name=Mister Mi", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "commit", "-m", "Mister Mi: análise diária e histórico", cwd=destination)
        git("push", "origin", "HEAD:refs/heads/data", cwd=destination)
    print("Mister Mi: análise e histórico guardados na branch data.")
finally:
    git("worktree", "remove", "--force", str(destination), check=False)
    shutil.rmtree(temporary, ignore_errors=True)
