"""Build the fake ESP-IDF once per content hash and cache it as libespsim.a + include/.

Cache: <tempdir>/formation-espsim-<hash>. The build happens in a private temp dir that is
renamed into place, so concurrent callers all end up with the same complete directory.
"""
import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

SIM = Path(__file__).resolve().parent
CXXFLAGS = ["-std=c++17", "-O1", "-pthread", "-Wall"]


def _sources() -> list[Path]:
    return sorted(p for d in ("include", "src") for p in (SIM / d).rglob("*") if p.is_file())


def _content_hash() -> str:
    h = hashlib.sha256()
    for p in [*_sources(), Path(__file__).resolve()]:
        h.update(str(p.relative_to(SIM)).encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()[:16]


def _check_owned(path: Path) -> None:
    # The cache sits in a shared tempdir: never link against a library another user planted.
    if path.stat().st_uid != os.getuid():
        raise RuntimeError(f"{path} appartient à un autre utilisateur")


def build_sim() -> Path:
    parent = Path(tempfile.gettempdir())
    final = parent / f"formation-espsim-{_content_hash()}"
    if (final / "libespsim.a").is_file():
        _check_owned(final)
        return final
    tmp = Path(tempfile.mkdtemp(prefix=f".{final.name}-", dir=parent))
    try:
        shutil.copytree(SIM / "include", tmp / "include")
        objects = []
        procs = []
        for src in sorted((SIM / "src").glob("*.cpp")):
            obj = tmp / f"{src.stem}.o"
            objects.append(obj)
            procs.append(subprocess.Popen(
                ["g++", *CXXFLAGS, "-I", str(SIM / "include"), "-c", str(src), "-o", str(obj)],
                stderr=subprocess.PIPE, text=True,
            ))
        outputs = [(p, p.communicate()[1]) for p in procs]
        errors = [err for p, err in outputs if p.returncode != 0]
        if errors:
            raise RuntimeError("échec de compilation du simulateur :\n" + "\n".join(errors))
        subprocess.run(["ar", "rcs", str(tmp / "libespsim.a"), *map(str, objects)], check=True)
        for obj in objects:
            obj.unlink()
        try:
            os.rename(tmp, final)
        except OSError:
            if not (final / "libespsim.a").is_file():
                raise
            # another caller won the race with an identical build
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    _check_owned(final)
    return final


if __name__ == "__main__":
    print(build_sim())
