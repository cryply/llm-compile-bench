#!/usr/bin/env python3
"""bench/run.py — гоняет промпты по моделям, компилирует код, пишет results.csv.

  ./run.py                      # все модели, все промпты
  ./run.py -m qwen38 deepseek   # выбранные модели
  ./run.py -p rust_iso8601      # выбранные промпты
  ./run.py --no-switch          # не трогать before/after (модели уже подняты)
"""
import argparse, csv, json, os, re, shutil, subprocess, sys, time, urllib.request
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
WORK = ROOT / "work"

LANG_TAGS = {
    "rust": {"rust", "rs"}, "cpp": {"cpp", "c++", "cc", "cxx"}, "python": {"python", "py"},
    "go": {"go", "golang"}, "typescript": {"typescript", "ts"}, "react": {"tsx", "typescript", "ts", "jsx"},
}

def sh(cmd, cwd=None, timeout=600):
    p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr)[-4000:]

def wait_ready(endpoint, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(endpoint + "/models", timeout=5).read()
            return True
        except Exception:
            time.sleep(3)
    return False

def chat(endpoint, model, prompt, req):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "temperature": req["temperature"], "max_tokens": req["max_tokens"]}
    r = urllib.request.Request(endpoint + "/chat/completions", data=json.dumps(body).encode(),
                               headers={"Content-Type": "application/json", "Authorization": "Bearer x"})
    t0 = time.time()
    with urllib.request.urlopen(r, timeout=req["timeout_s"]) as resp:
        data = json.load(resp)
    wall = time.time() - t0
    msg = data["choices"][0]["message"]
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
    usage = data.get("usage", {})
    timings = data.get("timings", {})
    return content, reasoning, usage, timings, wall

def extract_code(text, lang):
    tags = LANG_TAGS[lang]
    blocks = re.findall(r"```([\w+#-]*)\s*\n(.*?)```", text, re.S)
    cands = [b for t, b in blocks if t.lower() in tags]
    if not cands:
        cands = [b for t, b in blocks if t == ""]
    if not cands and blocks:
        cands = [b for _, b in blocks]
    if cands:
        return max(cands, key=len)
    # Без ограждений: Nemotron отдаёт голый код (27.10). Берём весь ответ —
    # если это проза, она просто не скомпилируется, и это честный провал.
    return text.strip() or None

def check(lang, code, prompt_spec, wd):
    """Возвращает (compile_ok, tests_ok, log)."""
    wd.mkdir(parents=True, exist_ok=True)
    files = prompt_spec.get("files", {})
    if lang == "rust":
        (wd / "Cargo.toml").write_text('[package]\nname="bench"\nversion="0.1.0"\nedition="2021"\n[dependencies]\n' + prompt_spec.get("cargo_deps", ""))
        (wd / "src").mkdir(exist_ok=True); (wd / "tests").mkdir(exist_ok=True)
        (wd / "src/lib.rs").write_text(code)
        (wd / "tests/t.rs").write_text(files["test"])
        rc, log = sh("cargo build --offline 2>&1 || cargo build 2>&1", wd); c_ok = rc == 0
        t_ok = c_ok and sh("cargo test 2>&1", wd)[0] == 0
    elif lang == "cpp":
        (wd / "solution.hpp").write_text(code); (wd / "test.cpp").write_text(files["test"])
        rc, log = sh("g++ -std=c++20 -O1 test.cpp -o t", wd); c_ok = rc == 0
        t_ok = c_ok and sh("./t", wd)[0] == 0
    elif lang == "python":
        (wd / "solution.py").write_text(code); (wd / "test_solution.py").write_text(files["test"])
        rc, log = sh("python3 -m py_compile solution.py", wd); c_ok = rc == 0
        t_ok = c_ok and sh("python3 -m pytest -q test_solution.py", wd)[0] == 0
    elif lang == "go":
        (wd / "go.mod").write_text("module bench\n\ngo 1.22\n")
        (wd / "solution.go").write_text(code); (wd / "solution_test.go").write_text(files["test"])
        rc, log = sh("go vet ./...", wd); c_ok = rc == 0
        t_ok = c_ok and sh("go test ./...", wd)[0] == 0
    elif lang in ("typescript", "react"):
        ts = ROOT / "ts"
        for f in ("package.json", "tsconfig.json"):
            shutil.copy(ts / f, wd / f)
        if (ts / "node_modules").exists() and not (wd / "node_modules").exists():
            os.symlink(ts / "node_modules", wd / "node_modules")
        ext = "tsx" if lang == "react" else "ts"
        (wd / f"solution.{ext}").write_text(code); (wd / f"test.{ext}").write_text(files["test"])
        rc, log = sh("npx tsc --noEmit", wd); c_ok = rc == 0
        if lang == "typescript":
            t_ok = c_ok and sh("npx tsx test.ts", wd)[0] == 0
        else:
            t_ok = c_ok  # react: достаточно типовой проверки
    else:
        return False, False, f"unknown lang {lang}"
    return c_ok, t_ok, log

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--models", nargs="*"); ap.add_argument("-p", "--prompts", nargs="*")
    ap.add_argument("--no-switch", action="store_true")
    a = ap.parse_args()
    # Судьи должны быть на месте ДО того, как грузить модели: 27.10
    # без cargo/go/node весь прогон дал бы нули и выглядел бы как провал
    # моделей, а не харнесса.
    missing = [t for t in ("cargo", "g++", "go", "node", "npx") if shutil.which(t) is None]
    if missing or subprocess.run(["python3", "-m", "pytest", "--version"],
                                 capture_output=True).returncode != 0:
        sys.exit(f"нет судей: {missing or 'pytest'} — установи, иначе результат ложный")
    cfg = yaml.safe_load((ROOT / "models.yaml").read_text())
    models = {k: v for k, v in cfg["models"].items() if not a.models or k in a.models}
    req = cfg["request"]
    prompts = {}
    for f in sorted((ROOT / "prompts").glob("*.yaml")):
        if not a.prompts or f.stem in a.prompts:
            prompts[f.stem] = yaml.safe_load(f.read_text())
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"results_{time.strftime('%Y%m%d_%H%M')}.csv"
    fh = out.open("w"); w = csv.writer(fh); w.writerow(["model", "prompt", "lang", "compile", "tests", "wall_s",
        "completion_tokens", "tok_s", "reasoning_chars", "answer_chars", "error"])
    # Выгрузка ВСЕГО при любом выходе: нормальном, Ctrl+C, SIGTERM.
    # Иначе после падения прогона llama-deepseek остаётся висеть, а таймеры
    # агентов — стоять. Команды идемпотентны: stop неактивного юнита и
    # ollama stop незагруженной модели безвредны.
    run = cfg.get("run", {})
    def cleanup():
        if a.no_switch: return
        for oc in cfg["models"].values():
            for c in oc.get("after", []):
                try: sh(c)
                except Exception as e: print(f"  cleanup: {c}: {e}")
        for c in run.get("after", []):
            try: sh(c)
            except Exception as e: print(f"  cleanup: {c}: {e}")
    import atexit, signal
    atexit.register(cleanup)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    if not a.no_switch:
        for c in run.get("before", []): sh(c)

    for mname, m in models.items():
        print(f"\n=== {mname}", flush=True)
        if not a.no_switch:
            if m.get("exclusive"):
                # по ВСЕМ моделям из конфига, не только выбранным через -m:
                # иначе `-m deepseek` при поднятом qwopus его не погасит
                for o, oc in cfg["models"].items():
                    if o != mname:
                        for c in oc.get("after", []): sh(c)
            for c in m.get("before", []): sh(c)
            if not wait_ready(m["endpoint"]):
                print("  endpoint not ready, skip"); continue
        for pname, p in prompts.items():
            print(f"  {pname} ...", end=" ", flush=True)
            err = ""; c_ok = t_ok = False; wall = tok = toks = 0; reasoning = content = ""
            try:
                content, reasoning, usage, timings, wall = chat(m["endpoint"], m["model"], p["prompt"], req)
                tok = usage.get("completion_tokens", 0)
                toks = timings.get("predicted_per_second") or (tok / wall if wall else 0)
                d = RESULTS / mname; d.mkdir(exist_ok=True)
                (d / f"{pname}.md").write_text(f"# reasoning\n{reasoning}\n\n# answer\n{content}")
                code = extract_code(content, p["lang"])
                if code is None:
                    # 16000 токенов ровно и пустой ответ — reasoning съел бюджет
                    # (deepseek go_worker_pool, 27.10). Это другой провал.
                    err = "max_tokens exhausted" if tok >= req["max_tokens"] else "no code block"
                else:
                    wd = WORK / mname / pname
                    shutil.rmtree(wd, ignore_errors=True)
                    c_ok, t_ok, log = check(p["lang"], code, p, wd)
                    (d / f"{pname}.log").write_text(log)
            except subprocess.TimeoutExpired as e:
                # Повис тест, не сборка: сборка к этому моменту уже прошла.
                # qwopus go_worker_pool 27.10: дедлок в worker pool — это
                # compile=1 tests=0, а не два нуля.
                c_ok = "test" in str(e.cmd) or "./t" in str(e.cmd)
                err = f"tests hang: {str(e.cmd)[:60]}"
            except Exception as e:
                err = repr(e)[:200]
            w.writerow([mname, pname, p["lang"], int(c_ok), int(t_ok), f"{wall:.1f}", tok, f"{toks:.1f}",
                        len(reasoning), len(content), err])
            print(f"compile={int(c_ok)} tests={int(t_ok)} {wall:.0f}s {toks:.1f}tok/s {err}", flush=True)
        if not a.no_switch:
            for c in m.get("after", []): sh(c)
    print(f"\n-> {out}")
    fh.close()   # иначе summary.py читает пустой файл: буфер ещё не сброшен
    sh(f"python3 {ROOT}/summary.py {out}")
    print(open(out).read() if False else "")
    os.system(f"python3 {ROOT}/summary.py {out}")

if __name__ == "__main__":
    main()
