import subprocess
import sys

result = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "tests/app/repositories/test_recommendation.py",
        "-v",
        "--tb=short",
    ],
    capture_output=True,
    text=True,
    cwd=".",
)
print("exit:", result.returncode, flush=True)
print("---STDOUT---", flush=True)
print(result.stdout, flush=True)
print("---STDERR---", flush=True)
print(result.stderr, flush=True)
