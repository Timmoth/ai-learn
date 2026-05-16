import subprocess
from pathlib import Path


def _build_cmd(backend: dict, prompt: str, verbose: bool) -> tuple[list[str], str | None]:
    prompt_via = backend.get("prompt_via", "arg")
    args = list(backend.get("args", []))
    if verbose:
        args += list(backend.get("verbose_args", []))

    cmd = [backend["command"]]
    for arg in args:
        if "{prompt}" in arg:
            if prompt_via == "arg":
                cmd.append(arg.replace("{prompt}", prompt))
        else:
            cmd.append(arg)

    stdin_input = prompt if prompt_via == "stdin" else None
    return cmd, stdin_input


def run_streaming(config: dict, prompt: str, cwd: Path) -> int:
    """Invoke the backend with verbose args so progress streams to the user."""
    active = config["active_backend"]
    backend = config["backends"][active]
    cmd, stdin_input = _build_cmd(backend, prompt, verbose=True)

    print(f"Running backend: {active} ({backend['command']})")
    print("-" * 60)
    try:
        result = subprocess.run(cmd, cwd=cwd, input=stdin_input, text=True)
    except FileNotFoundError:
        print(f"Error: command '{backend['command']}' not found on PATH.")
        return 127
    print("-" * 60)
    return result.returncode


def run_capture(config: dict, prompt: str, cwd: Path) -> tuple[int, str]:
    """Invoke the backend without verbose args and capture stdout as text."""
    active = config["active_backend"]
    backend = config["backends"][active]
    cmd, stdin_input = _build_cmd(backend, prompt, verbose=False)

    try:
        result = subprocess.run(
            cmd, cwd=cwd, input=stdin_input, text=True, capture_output=True
        )
    except FileNotFoundError:
        return 127, f"Error: command '{backend['command']}' not found on PATH."
    return result.returncode, result.stdout
