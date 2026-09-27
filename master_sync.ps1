Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass; python -c "
import os, sys, subprocess, importlib, urllib.request, json

print('====================================================')
print('      AUTONOMOUS ASSISTANT MASTER HEALTH & SYNC     ')
print('====================================================')

# 1. Dependency Verification
required_pkgs = ['customtkinter', 'edge_tts', 'pygame', 'ollama', 'psutil', 'PIL', 'openwakeword', 'speech_recognition']
missing = []
for pkg in required_pkgs:
    try:
        if pkg == 'PIL':
            importlib.import_module('PIL')
        else:
            importlib.import_module(pkg)
        print(f'  [OK] Package active: {pkg}')
    except ImportError:
        missing.append(pkg)
        print(f'  [FAIL] Missing package: {pkg}')

if missing:
    print(f'  --> Installing missing dependencies: {missing}')
    subprocess.run([sys.executable, '-m', 'pip', 'install'] + missing, check=True)

# 2. Syntax & Bytecode Compilation Audit
modules = ['db.py', 'tools.py', 'audio.py', 'gui.py', 'engine.py', 'main.py', 'build_app.py']
import py_compile
for mod in modules:
    if os.path.exists(mod):
        py_compile.compile(mod, doraise=True)
        print(f'  [OK] Compiled module: {mod}')
    else:
        print(f'  [WARN] Missing file: {mod}')

# 3. SQLite Database Layer Validation
try:
    from db import TaskDatabase
    db = TaskDatabase()
    tasks = db.get_all_tasks()
    print(f'  [OK] SQLite TaskDatabase verified ({len(tasks)} tasks registered)')
except Exception as e:
    print(f'  [FAIL] TaskDatabase error: {e}')

# 4. Local Ollama Service Probe
try:
    req = urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=2)
    models = [m.get('name') for m in json.loads(req.read().decode()).get('models', [])]
    print(f'  [OK] Ollama service reachable. Models: {models}')
except Exception:
    print('  [WARN] Ollama service not reachable on http://127.0.0.1:11434')

# 5. Build Executable via build_app.py
if os.path.exists('build_app.py'):
    print('  --> Running PyInstaller build pipeline...')
    subprocess.run([sys.executable, 'build_app.py'], check=True)

print('====================================================')
"
powershell -ExecutionPolicy Bypass -File .\setup_shortcut.ps1
