import sys, os, importlib.util
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "portal"))
spec = importlib.util.spec_from_file_location("portal_app", os.path.join(BASE_DIR, "portal", "app.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.app.run(host="127.0.0.1", port=5000, debug=False)
