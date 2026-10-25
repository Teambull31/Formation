#!/usr/bin/env python3
"""Contrôle des TP ESP-IDF : lit main.cpp, l'analyse, le compile et l'exécute dans le sandbox, lit la trace.

Lancer avec `python3 -I -B esp_check.py <tp_id>` (le répertoire courant est le dossier du TP). La
vérification propre au TP est dans checks/<tp_id>.py : SCENARIO (dict), MAX_MS (int),
verify(trace, source). Seuls ce dossier (contenu de confiance) et la bibliothèque standard sont
chargés, par chemin ; le répertoire de l'apprenant n'est jamais sur sys.path ni monté dans le
sandbox : le texte analysé est copié dans un dossier privé et c'est cette copie qui est compilée.
"""
from __future__ import annotations

import errno
import importlib.util
import json
import os
import re
import signal
import stat
import sys
import tempfile
from pathlib import Path

ESP = Path(__file__).resolve().parent
CHECKS = ESP / "checks"
SOURCE = "main.cpp"
MAX_BYTES = 200_000
MAX_OUT = 1_000_000  # trace bytes kept; a 60 s TP logging every 10 ms stays well under
MAX_BAD_LINES = 3
WALL_S = 40  # compile + run, under the TP timeout (60 s)
GXX_FLAGS = ["-std=c++17", "-O1", "-pthread", "-w", "-fmax-errors=5", "-fno-diagnostics-show-caret",
             "-fdiagnostics-color=never"]
TP_ID = re.compile(r"[A-Za-z0-9_-]+")

MSG_NO_SOURCE = "main.cpp est introuvable dans le dossier du TP"
MSG_SYMLINK = "main.cpp est un lien symbolique : enregistrez votre code dans un vrai fichier main.cpp"
MSG_NOT_REGULAR = "main.cpp n'est pas un fichier ordinaire"
MSG_UNREADABLE = "main.cpp est illisible ({})"
MSG_TOO_BIG = f"main.cpp est trop gros (plus de {MAX_BYTES} octets)"
MSG_NOT_UTF8 = "main.cpp n'est pas encodé en UTF-8 (octet invalide en position {pos}) : enregistrez-le en UTF-8"
MSG_TIME = ("interdit ligne {line} : {what}. Dans un programme ESP-IDF, on attend avec vTaskDelay(pdMS_TO_TICKS(ms)) "
            "et on fait plusieurs choses à la fois avec des tâches FreeRTOS (xTaskCreate)")
MSG_OUTPUT = ("interdit ligne {line} : {what}. Seuls ESP_LOGI, ESP_LOGW et ESP_LOGE apparaissent dans la trace du "
              "simulateur : journalisez avec eux, sans fichier ni sortie directe")
MSG_PROCESS = ("interdit ligne {line} : {what}. Un programme ESP-IDF n'a ni processus ni shell : "
               "utilisez des tâches FreeRTOS (xTaskCreate)")
MSG_LOWLEVEL = "interdit ligne {line} : {what} (construction de bas niveau inutile pour ce TP)"
MSG_INCLUDE = ("#include interdit ligne {line} : {what}. Incluez seulement des en-têtes ESP-IDF "
               "(\"freertos/FreeRTOS.h\", \"driver/gpio.h\", ...) ou standard (<cstdio>, ...), sans chemin absolu ni ..")
MSG_DEFINES_MAIN = ("ne définissez pas main() : sous ESP-IDF, le point d'entrée est "
                    "extern \"C\" void app_main(void), appelé par le système")
MSG_NO_APP_MAIN = "app_main introuvable : définissez extern \"C\" void app_main(void), le point d'entrée ESP-IDF"
MSG_NO_EXTERN_C = ("app_main doit être déclarée en extern \"C\" : extern \"C\" void app_main(void) "
                   "(sinon le C++ change son nom et le système ne la trouve pas)")
MSG_COMPILE = "main.cpp ne compile pas :\n{summary}\n(relisez la section du cours qui présente ces fonctions)"
MSG_COMPILE_TIMEOUT = "la compilation de main.cpp a pris trop de temps"
MSG_NO_SANDBOX = "le sandbox d'exécution (bwrap) est indisponible : le code n'est pas exécuté sans lui"
MSG_FLOOD = (f"la trace dépasse {MAX_OUT} octets et a été tronquée : votre programme journalise trop "
             "(un ESP_LOGI dans une boucle sans vTaskDelay ?)")
MSG_BAD_TRACE = "la trace du simulateur est illisible ({n} lignes inattendues)"
MSG_BUSY_LOOP = ("votre tâche « {task} » ne rend jamais la main : ajoutez un vTaskDelay(pdMS_TO_TICKS(...)) "
                 "dans sa boucle pour laisser tourner les autres tâches")
MSG_TOO_MANY_TASKS = "trop de tâches : le simulateur en autorise 4 en plus de app_main"
MSG_SEGV = "le programme a planté (SIGSEGV, accès mémoire invalide : pointeur nul ou tableau dépassé ?)"
MSG_CRASH = "le programme a planté (signal {sig})"
MSG_ESP_ERROR_CHECK = "ESP_ERROR_CHECK a arrêté le programme : {msg}"
MSG_ABORT = "le programme s'est arrêté (abort) : {msg}"
MSG_TIMEOUT = "le programme a dépassé le temps d'exécution autorisé"
MSG_SCENARIO = "erreur interne du TP (scénario refusé par le simulateur) : {err}"
MSG_NO_END = "le programme s'est arrêté avant la fin de la simulation (code {rc})"
MSG_STDERR = "\nSortie d'erreur du programme (extrait) :\n{err}"
OK = "OK : le programme se comporte comme attendu dans le simulateur."


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # before exec: dataclasses and `import esp_trace` look it up there
    spec.loader.exec_module(mod)
    return mod


sandbox = _load("esp_sandbox", ESP / "sandbox.py")
build = _load("esp_sim_build", ESP / "sim" / "build.py")
esp_trace = _load("esp_trace", ESP / "trace.py")
CheckError, Trace, need = esp_trace.CheckError, esp_trace.Trace, esp_trace.need


# ---- (1) lecture ----

def read_source() -> str:
    try:
        fd = os.open(SOURCE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except FileNotFoundError:
        raise CheckError(MSG_NO_SOURCE) from None
    except OSError as e:
        raise CheckError(MSG_SYMLINK if e.errno == errno.ELOOP else MSG_UNREADABLE.format(e.strerror)) from None
    try:
        st = os.fstat(fd)
        need(stat.S_ISREG(st.st_mode), MSG_NOT_REGULAR)
        need(st.st_size <= MAX_BYTES, MSG_TOO_BIG)
        data = b""
        while len(data) <= MAX_BYTES and (chunk := os.read(fd, MAX_BYTES + 1 - len(data))):
            data += chunk
    finally:
        os.close(fd)
    need(len(data) <= MAX_BYTES, MSG_TOO_BIG)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise CheckError(MSG_NOT_UTF8.format(pos=e.start)) from None


# ---- (2) analyse statique ----

RAW_STRING = re.compile(r'(?:u8|[uUL])?R"([^()\\\s"]{0,16})\(')


def _digit_separator(text: str, i: int) -> bool:
    # 1'000 or 0xFF'FF: a ' between two hex digits of a number, not a character literal (u8'x' is one).
    return i > 0 and text[i - 1] in "0123456789abcdefABCDEF" and text[i + 1:i + 2].isalnum() \
        and not text[:i].endswith("u8")


def blank(text: str) -> tuple[str, str]:
    """(code, no_comments): comments blanked in both, literal contents also blanked in code. Newlines kept."""
    code: list[str] = []
    nc: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        prev = text[i - 1] if i else " "
        if text.startswith(("//", "/*"), i):
            if text[i + 1] == "/":
                j = text.find("\n", i)
            else:
                j = text.find("*/", i + 2)
                j = j + 2 if j >= 0 else j
            j = n if j < 0 else j
            seg = re.sub(r"[^\n]", " ", text[i:j])
            code.append(seg)
            nc.append(seg)
            i = j
            continue
        m = RAW_STRING.match(text, i) if c in "uULR" and not (prev.isalnum() or prev == "_") else None
        if m:
            j = text.find(")" + m.group(1) + '"', m.end())
            j = n if j < 0 else j + len(m.group(1)) + 2
        elif c == '"' or (c == "'" and not _digit_separator(text, i)):
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
        else:
            code.append(c)
            nc.append(c)
            i += 1
            continue
        seg = text[i:j]
        nc.append(seg)
        code.append('""' + re.sub(r"[^\n]", " ", seg[2:]))
        i = j
    return "".join(code), "".join(nc)


_IO_WORDS = ("write|pwrite|writev|pwritev2?|sendmsg|sendto|sendfile|splice|vmsplice|tee|copy_file_range|mmap|"
             "memfd_create|socket|ioctl|fcntl|lseek|openat|open64|creat|readv|preadv2?|pread|recvmsg|"
             "dup[23]?|getenv|secure_getenv|environ")
# (pattern, message, searched in): "code" has literals blanked, "nc" keeps them (comments blanked in both).
# The scan targets accidents and casual trace forgery; the sandbox is what contains hostile code.
RULES = [
    (r"\b(?:jthread|this_thread|thread)\b", MSG_TIME, "code"),
    (r"\bsleep_(?:for|until)\b|\b(?:usleep|nanosleep|clock_nanosleep)\b|\bsleep\s*\(", MSG_TIME, "code"),
    (r"\basync\b|\bpthread_\w+|\b(?:wait_|try_lock_)(?:for|until)\b", MSG_TIME, "code"),
    (r"\b(?:time|clock)\s*\(|\b(?:clock_gettime|gettimeofday|timespec_get|ftime)\b", MSG_TIME, "code"),
    (r"\b(?:system|steady|high_resolution|utc|tai|gps|file)_clock\b", MSG_TIME, "code"),
    (r"\b(?:v?f?w?printf|v?dprintf|f?putw?s|f?putw?c|putw?char|fwrite|perror|psig\w+)(?:_unlocked)?\b",
     MSG_OUTPUT, "code"),
    (r"\b(?:w?cout|w?cerr|w?clog)\b", MSG_OUTPUT, "code"),
    (r"\b(?:f|fre)open(?:64)?\b|\b(?:fdopen|tmpfile(?:64)?|filesystem)\b|\w*(?:fstream|filebuf)\b", MSG_OUTPUT, "code"),
    (rf"\b(?:{_IO_WORDS})(?:64)?\b", MSG_OUTPUT, "code"),
    # Common words (a door can be "open"): only calls or references are refused.
    (r"\b(?:read|open|close|send|recv)\s*\(|(?:&|::)\s*(?:read|open|close|send|recv)\b", MSG_OUTPUT, "code"),
    (r"/(?:proc|dev|sys)\b", MSG_OUTPUT, "literals"),
    (r"\b(?:system|fork|vfork|kill)\s*\(|(?:&|::)\s*(?:system|fork|vfork|kill)\b", MSG_PROCESS, "code"),
    (r"\b(?:popen|posix_spawnp?|syscall|clone3?|ptrace|prctl|unshare|setns|fexecve|exec[lv][pe]{0,2}|dl(?:open|v?sym))\b",
     MSG_PROCESS, "code"),
    # Reserved identifiers (__builtin_*, __attribute__, __asm__, _Pragma, mangled names like _ZN3sim8trace_fdE).
    (r"\b(?!__(?:FILE__|LINE__|func__|FUNCTION__|PRETTY_FUNCTION__|VA_ARGS__|cplusplus)\b)_(?:_|[A-Z])\w*",
     MSG_LOWLEVEL, "code"),
    (r"\b(?:asm|gnu|weakref|sim)\b", MSG_LOWLEVEL, "code"),
    (r"#\s*(?:embed|include_next)\b|##", MSG_LOWLEVEL, "code"),
    # Outside literals, a backslash can only be a universal character name (printf).
    (r"\\", MSG_LOWLEVEL, "code"),
]
INCLUDE = re.compile(r"^[ \t]*#[ \t]*include\b[ \t]*(.*)$", re.M)


def scan(source: str) -> None:
    # Splice continued lines and map the %: digraph to #, as the preprocessor does, before matching.
    # Line numbers count the spliced text (off only after a backslash-continued line).
    text = source.replace("\\\r\n", "").replace("\\\n", "").replace("%:", "#")
    code, nc = blank(text)
    # Adjacent literals are one string to the compiler: "/pro" "c" is "/proc".
    texts = {"code": code, "nc": nc, "literals": re.sub(r'"\s*(?:u8|[uUL])?"', "", nc)}

    def line(pos: int) -> int:
        return text.count("\n", 0, pos) + 1

    for m in INCLUDE.finditer(nc):
        target = re.match(r'(<[^>\n]*>|"[^"\n]*")', m.group(1))
        name = target.group(1)[1:-1].strip() if target else ""
        need(target and not name.startswith("/") and ".." not in name and "\\" not in name,
             MSG_INCLUDE.format(line=line(m.start()), what=m.group(0).strip()))
    for pattern, message, where in RULES:
        m = re.search(pattern, texts[where])
        need(m is None, m and message.format(line=line(m.start()), what=m.group(0).strip()))
    # (3) point d'entrée ESP-IDF
    need(not re.search(r"\bmain\s*\(", code), MSG_DEFINES_MAIN)
    need(re.search(r"\bapp_main\b", code), MSG_NO_APP_MAIN)
    need(re.search(r'\bextern\s*"C"', nc), MSG_NO_EXTERN_C)


# ---- (4) compilation, (5) exécution, (6) fin de trace ----

def _summary(err: str) -> str:
    # Keep file names, drop directories: the learner sees main.cpp, not the sandbox or cache paths.
    lines = [re.sub(r"(?:/[^\s:'\"`/]+)+/", "", l)[:300] for l in err.splitlines() if l.strip()]
    return "\n".join(lines[:5])


def _excerpt(err: str) -> str:
    err = err.strip()
    if not err:
        return ""
    return MSG_STDERR.format(err="\n".join(err[-800:].splitlines()[-10:]))


def run_program(source: str, check) -> tuple[Trace, str]:
    sim = build.build_sim()
    with tempfile.TemporaryDirectory(prefix="espcheck-") as d:
        work = Path(d)
        (work / SOURCE).write_bytes(source.encode("utf-8"))
        (work / "scenario.json").write_text(json.dumps(check.SCENARIO), encoding="utf-8")
        try:
            r = sandbox.compile_and_run(["g++", *GXX_FLAGS, "-I", f"{sim}/include", SOURCE, f"{sim}/libespsim.a"],
                                        ["--max-ms", str(check.MAX_MS), "--scenario", "scenario.json"],
                                        cwd=work, ro=[sim], wall_s=WALL_S, max_out=MAX_OUT)
        except (sandbox.SandboxUnavailable, sandbox.UnsafePath) as e:
            raise CheckError(f"{MSG_NO_SANDBOX} ({e})") from None
    if r.phase == "compile":
        need(not r.timed_out, MSG_COMPILE_TIMEOUT)
        need("undefined reference to `app_main'" not in r.err, MSG_NO_APP_MAIN)
        need("multiple definition of `main'" not in r.err, MSG_DEFINES_MAIN)
        raise CheckError(MSG_COMPILE.format(summary=_summary(r.err)))
    return interpret(r), r.err


def interpret(r) -> Trace:
    """Trace from the private trace fd (stdout only); stderr is learner/diagnostic text shown on failure."""
    def fail(message: str):
        raise CheckError(message + _excerpt(r.err))

    if r.out.endswith(sandbox.TRUNCATED):
        fail(MSG_FLOOD)
    trace = Trace(r.out)
    if trace.bad_lines > MAX_BAD_LINES:
        fail(MSG_BAD_TRACE.format(n=trace.bad_lines))
    end = trace.last_end()
    reason, sig = end.get("reason"), end.get("signal")
    # std::thread creation over the process cap (RUN_MAX_PROCS) throws, then aborts.
    if "Resource temporarily unavailable" in r.err and (r.signal == "SIGABRT" or sig == signal.SIGABRT):
        fail(MSG_TOO_MANY_TASKS)
    if reason == "deadline":
        return trace
    if reason == "busy_loop":
        fail(MSG_BUSY_LOOP.format(task=end.get("task", "?")))
    if reason == "crash" or (not end and r.signal and not r.timed_out):
        try:
            name = signal.Signals(sig).name if reason == "crash" else r.signal
        except (ValueError, TypeError):
            name = str(sig)
        fail(MSG_SEGV if name == "SIGSEGV" else MSG_CRASH.format(sig=name))
    if reason == "abort":
        errors = trace.logs(level="E")
        msg = errors[-1].get("msg", "") if errors else ""
        fail((MSG_ESP_ERROR_CHECK if errors and errors[-1].get("tag") == "esp_err" else MSG_ABORT).format(msg=msg))
    if r.timed_out:
        fail(MSG_TIMEOUT)
    if r.rc == 2 and "scénario" in r.err:
        raise CheckError(MSG_SCENARIO.format(err=r.err.strip()[:300]))
    fail(MSG_NO_END.format(rc=r.rc))


# ---- (7) vérification du TP ----

def main(argv: list[str]) -> int:
    if len(argv) != 2 or not TP_ID.fullmatch(argv[1]) or not (CHECKS / f"{argv[1]}.py").is_file():
        print(f"Usage: {Path(argv[0]).name} <tp_id> (un module checks/<tp_id>.py doit exister)", file=sys.stderr)
        return 2
    check = _load(f"esp_check_{argv[1]}", CHECKS / f"{argv[1]}.py")
    try:
        source = read_source()
        scan(source)
        trace, err = run_program(source, check)
        try:
            check.verify(trace, source)
        except CheckError as e:
            raise CheckError(str(e) + _excerpt(err)) from None
    except CheckError as e:
        print(f"ECHEC : {e}")
        return 1
    print(OK)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
