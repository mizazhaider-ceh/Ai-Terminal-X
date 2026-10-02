# Shared test setup: stub out the Google AI libraries so the pure helper
# functions can be tested without installing (or calling) the real SDK.
import sys
import types

google_mod = types.ModuleType("google")
genai_mod = types.ModuleType("google.generativeai")
genai_mod.GenerativeModel = object
google_mod.generativeai = genai_mod
sys.modules.setdefault("google", google_mod)
sys.modules.setdefault("google.generativeai", genai_mod)

dotenv_mod = types.ModuleType("dotenv")
dotenv_mod.load_dotenv = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv_mod)
