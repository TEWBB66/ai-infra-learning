from pathlib import Path
import sys


SCAN_ROOTS = [
    Path("README.md"),
    Path("docs"),
    Path("projects"),
    Path("monitoring"),
    Path("k8s"),
    Path("tests"),
    Path("reports"),
    Path(".github"),
    Path("scripts"),
]

ROOT_FILES = [
    Path(".env.example"),
    Path("Dockerfile"),
    Path("docker-compose.yml"),
    Path("requirements.txt"),
    Path("LICENSE"),
]

TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".yml",
    ".yaml",
    ".json",
    ".txt",
    ".example",
}


BLOCKED_TERMS = [
    "P" + "01",
    "9" + "/10",
    "8" + "/10",
    "up" + "grade",
    "\u5347\u7ea7",
    "\u8bc4\u5206",
    "\u8ba1\u5212",
    "\u6211\u4eec",
    "master" + "y",
    "career" + " plan",
    "Co" + "dex",
    "\u4e0b\u4e00\u6b65",
    "\u7b80\u5386",
    "\u9762\u8bd5",
    "\u5b66\u4e60\u8def\u7ebf",
]


def is_text_file(path: Path) -> bool:
    if path.name.startswith(".") and path.suffix == "":
        return False
    return path.suffix in TEXT_SUFFIXES or path.name in {"Dockerfile"}


def iter_public_files():
    for path in ROOT_FILES:
        if path.exists() and path.is_file() and is_text_file(path):
            yield path

    for root in SCAN_ROOTS:
        if root.is_file():
            yield root
            continue

        if not root.exists():
            continue

        for path in root.rglob("*"):
            if "__pycache__" in path.parts:
                continue
            if path.is_file() and is_text_file(path):
                yield path


def find_violations():
    violations = []

    for path in iter_public_files():
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for term in BLOCKED_TERMS:
                if term in line:
                    violations.append((path, line_number, term))

    return violations


def main():
    violations = find_violations()
    if not violations:
        return 0

    for path, line_number, term in violations:
        print(f"{path}:{line_number}: blocked public-process term: {term}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
