#!/usr/bin/env python3
"""Contrôle des TP ESP-IDF : lit main.cpp, l'analyse, le compile et l'exécute dans le sandbox, lit la trace.

Lancer avec `python3 -I -B esp_check.py <tp_id>` (le répertoire courant est le dossier du TP). La
vérification propre au TP est dans checks/<tp_id>.py : SCENARIO (dict), MAX_MS (int),
verify(trace, source). Les messages de verify (CheckError / need) doivent finir par leur propre
« (relire : <section>) » ; ceux du pilote reçoivent HINT. Seuls ce dossier (contenu de confiance) et la bibliothèque standard sont
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
MSG_HARD_LINK = "main.cpp a plusieurs liens physiques : enregistrez votre code dans un fichier main.cpp à part"
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
MSG_COMPILE = "main.cpp ne compile pas :\n{summary}"
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
MSG_KILLED = "le programme s'est arrêté brutalement"
MSG_ESP_ERROR_CHECK = "ESP_ERROR_CHECK a arrêté le programme : {msg}"
MSG_ABORT = "le programme s'est arrêté (abort) : {msg}"
MSG_TIMEOUT = "le programme a dépassé le temps d'exécution autorisé"
MSG_SCENARIO = "erreur interne du TP (scénario refusé par le simulateur) : {err}"
MSG_NO_END = "le programme s'est arrêté avant la fin de la simulation (code {rc})"
MSG_STDERR = "\nSortie d'erreur du programme (extrait) :\n{err}"
MSG_INTERNAL = "erreur interne du contrôle ({cause})"
HINT = " (relire : les « Pièges » de la leçon)"
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
        need(st.st_nlink == 1, MSG_HARD_LINK)
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


# The scan targets accidents and casual trace forgery; the sandbox is what contains hostile code.
#
# Library names (NAME_RULES) are refused only where they can mean the library function, so a
# learner's own `struct Writer { void write(int); }`, `w.write(1)`, `Writer::write` or a variable
# named `tee` stay allowed. Never refused: a member access (`.name`, `->name`), a name qualified by
# anything but std (`X::name`), and a member declaration directly in a struct/class body. Otherwise:
#   "word"  : any use (type-like names: cout, fstream, ...);
#   "value" : a call `name(`, a reference `&name` / `::name` / `std::name`, or the bare name passed as
#             a value (`= name;`, `f(name)`, `return name;`): the names that can write to the trace fd
#             or start a process, so a function pointer cannot sneak them in;
#   "call"  : a call or a reference only (common words: `bool open`, `if (open)` are fine).
NAME_RULES = [
    (r"(?:v?f?w?printf|v?dprintf|f?putw?s|f?putw?c|putw?char|fwrite|perror|psig\w+)(?:_unlocked)?", MSG_OUTPUT, "value"),
    (r"w?cout|w?cerr|w?clog|(?:f|fre)open(?:64)?|fdopen|tmpfile(?:64)?|filesystem|\w*fstream|\w*filebuf", MSG_OUTPUT, "word"),
    (r"(?:write|pwrite|writev|pwritev2?|sendmsg|sendto|sendfile|splice|vmsplice|tee|copy_file_range|dup[23]?)(?:64)?",
     MSG_OUTPUT, "value"),
    (r"(?:read|open|openat|creat|close|send|recv|recvmsg|readv|preadv2?|pread|mmap|memfd_create|socket|ioctl|fcntl|"
     r"lseek|getenv|secure_getenv)(?:64)?", MSG_OUTPUT, "call"),
    (r"system|popen|fork|vfork|posix_spawnp?|syscall|fexecve|exec[lv][pe]{0,2}|dl(?:open|v?sym)", MSG_PROCESS, "value"),
    (r"kill|clone3?|ptrace|prctl|unshare|setns", MSG_PROCESS, "call"),
    (r"time|clock|sleep", MSG_TIME, "call"),
]
STD_THREAD = r"this_thread|jthread|thread|async"  # refused as std::name, or bare under `using namespace std`
USING_STD = re.compile(r"\busing\s+(?:namespace\s+)?(?:::\s*)?std\b")
# (pattern, message, searched in): "code" has literals blanked, "literals" keeps them, adjacent ones joined.
RULES = [
    (rf"\bstd\s*::\s*(?:{STD_THREAD})\b", MSG_TIME, "code"),
    (r"\bsleep_(?:for|until)\b|\b(?:usleep|nanosleep|clock_nanosleep)\b", MSG_TIME, "code"),
    (r"\bpthread_\w+|\b(?:wait_|try_lock_)(?:for|until)\b", MSG_TIME, "code"),
    (r"\b(?:clock_gettime|gettimeofday|timespec_get|ftime)\b", MSG_TIME, "code"),
    (r"\b(?:system|steady|high_resolution|utc|tai|gps|file)_clock\b", MSG_TIME, "code"),
    (r"/(?:proc|dev|sys)\b", MSG_OUTPUT, "literals"),
    # Reserved identifiers (__builtin_*, __attribute__, __asm__, _Pragma, mangled names like _ZN3sim8trace_fdE).
    (r"\b(?!__(?:FILE__|LINE__|func__|FUNCTION__|PRETTY_FUNCTION__|VA_ARGS__|cplusplus)\b)_(?:_|[A-Z])\w*",
     MSG_LOWLEVEL, "code"),
    (r"\basm\b|\bgnu\s*::|\busing\s+gnu\b", MSG_LOWLEVEL, "code"),
    # The simulator's internals, and aliases that would hide std:: or sim:: from the rules above.
    (r"\bsim\s*::|\bnamespace\s+sim\b|\busing\s+namespace\s+(?:::\s*)?sim\b|\bnamespace\s+\w+\s*=\s*(?:::\s*)?(?:std|sim)\b",
     MSG_LOWLEVEL, "code"),
    (r"#\s*(?:embed|include_next)\b|##", MSG_LOWLEVEL, "code"),
    # Outside literals, a backslash can only be a universal character name (printf).
    (r"\\", MSG_LOWLEVEL, "code"),
]


def _bodies(code: str, keywords: str) -> list[tuple[int, int]]:
    """(open, close) brace positions of each body introduced by one of `keywords` (struct|class|union, enum)."""
    pairs: dict[int, int] = {}
    stack: list[int] = []
    for i, c in enumerate(code):
        if c == "{":
            stack.append(i)
        elif c == "}" and stack:
            pairs[stack.pop()] = i
    return [(m.end() - 1, pairs[m.end() - 1]) for m in re.finditer(rf"\b(?:{keywords})\b[^;{{}}()]*\{{", code)
            if m.end() - 1 in pairs]


def _directly_in(code: str, pos: int, bodies: list[tuple[int, int]]) -> bool:
    # Inside one of the bodies and not nested deeper (a member function's body, a lambda...).
    return any(o < pos < c and code.count("{", o + 1, pos) == code.count("}", o + 1, pos) for o, c in bodies)


VALUE_KW = ("return", "and", "or", "not", "xor", "bitand", "bitor", "compl", "co_return", "throw", "sizeof", "case")
VALUE_PREV = tuple("+-*&?:=,({<>!|^~/%[)")  # a bare name right after one of these is used as a value


def _typed(before: str) -> bool:
    """The text ends with a type name or identifier (not `*`, an operator or an operator keyword)."""
    w = re.search(r"(\w+)$", before)
    if w:
        return w.group(1) not in VALUE_KW
    return bool(re.search(r"\w\s*<[^;{}()]*>$", before))


def _declared_in(code: str, name: str, o: int, c: int) -> bool:
    """`name` is declared directly in the class body (o, c): `bool open;`, `void write(int);`."""
    for m in re.finditer(rf"\b{name}\b", code[o + 1:c]):
        pos = o + 1 + m.start()
        if _directly_in(code, pos, [(o, c)]) and _typed(code[max(0, pos - 200):pos].rstrip()) \
                and code[pos + len(name):pos + len(name) + 40].lstrip()[:1] in tuple(";=({[,"):
            return True
    return False


def _declared_variable(code: str, name: str) -> bool:
    """A variable of the learner's own: `int tee = 3;`, `bool open;`, `int a, tee;` (never an extern declaration)."""
    kw = "|".join(VALUE_KW)
    for m in re.finditer(rf"(?:\b(?!(?:{kw})\b)[A-Za-z_]\w*\s+|,\s*){name}\s*(?:=(?!=)|;|\[|\{{)", code):
        stmt = code[max(0, m.start() - 200):m.start()]
        if not re.search(r"\bextern\b", re.split(r"[;{}]", stmt)[-1]):
            return True
    return False


# `Porte() : open(false) {}`, `Porte() : a(1), open(false) {}`: the statement so far is a function head and `:`/`,`.
_HEAD = r"^\s*(?!case\b|default\b)(?:[\w:<>~]+\s+)*[\w:~<>]+\s*\([^;{}]*\)\s*(?:noexcept\s*)?:"
CTOR_INIT = re.compile(_HEAD + r"(?:\s*[\w:<>]+\s*(?:\([^()]*\)|\{[^{}]*\})\s*,)*\s*$")


def _library_use(code: str, names: str, form: str, classes: list[tuple[int, int]], enums: list[tuple[int, int]]):
    word = re.compile(rf"\b(?:{names})\b")
    if form == "value":  # a macro can hide the name from every rule below: refused whole on any #define line
        for d in re.finditer(r"^[ \t]*#[ \t]*define\b[^\n]*", code, re.M):
            m = word.search(code, d.start(), d.end())
            if m:
                return m
    for m in word.finditer(code):
        raw = code[max(0, m.start() - 200):m.start()]
        before = raw.rstrip()
        if before.endswith((".", "->")) or _directly_in(code, m.start(), enums):
            continue  # member access, or an enumerator: enum class Mode { read, write };
        qualifier = re.search(r"(\w+|>)::\s*$", raw)
        if qualifier and qualifier.group(1) != "std":
            continue  # X::name: the learner's own member or namespace
        name = m.group(0)
        after = code[m.end():m.end() + 40].lstrip()
        call = after.startswith("(")
        reference = before.endswith(("&", "::"))
        # Member declaration directly in a class body, after a type: struct Writer { void write(int); };
        if call and _typed(before) and _directly_in(code, m.start(), classes):
            continue
        if form != "word" and not reference:
            # Sibling member call inside a member function of a class that declares it: open();
            if call and any(o < m.start() < c and _declared_in(code, name, o, c) for o, c in classes):
                continue
            # Constructor initialiser of a member the learner declared: Porte() : open(false) {}
            if after[:1] in ("(", "{") and before[-1:] in (":", ",") \
                    and CTOR_INIT.match(re.split(r"[;{}]", before)[-1]) \
                    and any(_declared_in(code, name, o, c) for o, c in classes):
                continue
        value = (before.endswith(VALUE_PREV) or re.search(rf"\b(?:{'|'.join(VALUE_KW)})$", before)) \
            and not _declared_variable(code, name)
        if form == "word" or call or reference or (form == "value" and value):
            return m
    return None


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
    classes, enums = _bodies(code, "struct|class|union"), _bodies(code, "enum")
    rules = NAME_RULES + ([(STD_THREAD, MSG_TIME, "word")] if USING_STD.search(code) else [])
    for names, message, form in rules:
        m = _library_use(code, names, form, classes, enums)
        need(m is None, m and message.format(line=line(m.start()), what=m.group(0)))
    # (3) point d'entrée ESP-IDF
    need(not re.search(r"\bmain\s*\(", code), MSG_DEFINES_MAIN)
    need(re.search(r"\bapp_main\b", code), MSG_NO_APP_MAIN)
    need(re.search(r'\bextern\s*"C"', nc), MSG_NO_EXTERN_C)


# ---- (4) compilation, (5) exécution, (6) fin de trace ----

def _strip_paths(text: str) -> str:
    # Keep file names, drop directories: the learner sees main.cpp, not the sandbox or cache paths.
    return re.sub(r"(?:/[^\s:'\"`/]+)+/", "", text)


def _summary(err: str) -> str:
    lines = [_strip_paths(l)[:300] for l in err.splitlines() if l.strip()]
    return "\n".join(lines[:5])


def _excerpt(err: str) -> str:
    err = err.strip()
    if not err:
        return ""
    return MSG_STDERR.format(err="\n".join(err[-800:].splitlines()[-10:]))


def _not_learner(message: str) -> CheckError:
    e = CheckError(message)
    e.hint = ""  # not the learner's code: no lesson to re-read
    return e


def _with_detail(e: CheckError, err: str) -> CheckError:
    e.detail = _excerpt(err)  # printed after the hint
    return e


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
            raise _not_learner(f"{MSG_NO_SANDBOX} ({e})") from None
    if r.phase == "compile":
        need(not r.timed_out, MSG_COMPILE_TIMEOUT)
        need("undefined reference to `app_main'" not in r.err, MSG_NO_APP_MAIN)
        need("multiple definition of `main'" not in r.err, MSG_DEFINES_MAIN)
        raise CheckError(MSG_COMPILE.format(summary=_summary(r.err)))
    return interpret(r), r.err


def interpret(r) -> Trace:
    """Trace from the private trace fd (stdout only); stderr is learner/diagnostic text shown on failure."""
    def fail(message: str):
        raise _with_detail(CheckError(message), r.err)

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
        name = r.signal
        if reason == "crash":
            try:
                name = signal.Signals(sig).name
            except (ValueError, TypeError):
                name = r.signal  # crash line without a usable signal: fall back to the exit status
        fail(MSG_SEGV if name == "SIGSEGV" else MSG_CRASH.format(sig=name) if name else MSG_KILLED)
    if reason == "abort":
        errors = trace.logs(level="E")
        msg = errors[-1].get("msg", "") if errors else ""
        fail((MSG_ESP_ERROR_CHECK if errors and errors[-1].get("tag") == "esp_err" else MSG_ABORT).format(msg=msg))
    if r.timed_out:
        fail(MSG_TIMEOUT)
    if r.rc == 2 and "scénario" in r.err:
        raise _not_learner(MSG_SCENARIO.format(err=r.err.strip()[:300]))
    fail(MSG_NO_END.format(rc=r.rc))


# ---- (7) vérification du TP ----

def main(argv: list[str]) -> int:
    if len(argv) != 2 or not TP_ID.fullmatch(argv[1]) or not (CHECKS / f"{argv[1]}.py").is_file():
        print(f"Usage: {Path(argv[0]).name} <tp_id> (un module checks/<tp_id>.py doit exister)", file=sys.stderr)
        return 2
    try:
        check = _load(f"esp_check_{argv[1]}", CHECKS / f"{argv[1]}.py")
        source = read_source()
        scan(source)
        trace, err = run_program(source, check)
        try:
            check.verify(trace, source)
        except CheckError as e:
            e.hint = ""  # verify messages carry their own (relire : ...)
            raise _with_detail(e, err) from None
    except CheckError as e:
        print(f"ECHEC : {e}{getattr(e, 'hint', HINT)}{getattr(e, 'detail', '')}")
        return 1
    except Exception as e:  # never a traceback, never OK: a bug in the sim build, a check module or the sandbox
        cause = _strip_paths((str(e).strip().splitlines() or [""])[0])[:200]
        print(f"ECHEC : {MSG_INTERNAL.format(cause=f'{type(e).__name__}: {cause}' if cause else type(e).__name__)}")
        return 1
    print(OK)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
