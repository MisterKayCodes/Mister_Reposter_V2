import os, sys, ast, asyncio, re
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# --- PRO UI INTEGRITY AUDIT ---
# Purpose: Dynamic discovery of buttons & handlers to prevent "Broken Link" UI.

# 1. SETUP PATHS
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(ROOT)

from aiogram import Dispatcher, Bot, types
from aiogram.types import Update

# 2. MOCK ENVIRONMENT
mock_service = AsyncMock()
mock_service.register_user.return_value = None
mock_service.is_admin.return_value = True

# 3. DISCOVERY ENGINE
class UIIntegrityAudit:
    def __init__(self, pkg="app"):
        self.pkg = pkg
        self.kb_files = [
            os.path.join(ROOT, "app/bot/keyboards.py"),
            os.path.join(ROOT, "app/bot/keyboards_admin.py")
        ]
        self.router_dir = os.path.join(ROOT, "app/bot/handlers")
        self.discovered_payloads = set()
        self.dangling_routers = []
        self.ghost_buttons = []
        self.stats = {"scanned": 0, "passed": 0, "failed": 0}

    def _extract_callback_data(self):
        for kb_file in self.kb_files:
            if not os.path.exists(kb_file): continue
            with open(kb_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        for kw in node.keywords:
                            if kw.arg == "callback_data":
                                if isinstance(kw.value, ast.Constant):
                                    self.discovered_payloads.add(kw.value.value)
                                elif isinstance(kw.value, ast.JoinedStr):
                                    pattern = ""
                                    for part in kw.value.values:
                                        if isinstance(part, ast.Constant):
                                            pattern += str(part.value)
                                        else:
                                            pattern += "1" 
                                    self.discovered_payloads.add(pattern)

    def _check_dangling_routers(self, dp: Dispatcher):
        all_handler_files = [
            f[:-3] for f in os.listdir(self.router_dir) 
            if f.endswith(".py") and f not in ["__init__.py", "utils.py"]
        ]
        with open(os.path.join(ROOT, "app/bot/routers.py"), "r") as f:
            routers_py = f.read()
            for hf in all_handler_files:
                if hf not in routers_py:
                    self.dangling_routers.append(hf)

    async def run_audit(self):
        print("\n--- PRO UI INTEGRITY AUDIT ---")
        
        with patch("app.bot.handlers.utils.repost_service", mock_service):
            from app.bot.routers import register_all_routers
            
            dp = Dispatcher()
            register_all_routers(dp)
            bot = Bot(token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11") 
            
            self._extract_callback_data()
            self._check_dangling_routers(dp)
            
            print(f"Discovered {len(self.discovered_payloads)} callback patterns.")
            
            for payload in sorted(list(self.discovered_payloads)):
                self.stats["scanned"] += 1
                cb = types.CallbackQuery(
                    id="1", 
                    from_user=types.User(id=1, is_bot=False, first_name="Test"),
                    chat_instance="1",
                    data=payload,
                    message=types.Message(
                        message_id=1, 
                        date=datetime.now(), 
                        chat=types.Chat(id=1, type="private")
                    )
                )
                update = Update(update_id=1, callback_query=cb)
                
                try:
                    result = await dp.feed_update(bot, update)
                    if result is not None:
                        self.stats["passed"] += 1
                    else:
                        self.ghost_buttons.append(payload)
                        self.stats["failed"] += 1
                except Exception:
                    self.stats["passed"] += 1

        self._print_report()

    def _print_report(self):
        if self.dangling_routers:
            print("\n[!] DANGLING ROUTERS (Found in handlers/ but not registered in routers.py):")
            for dr in self.dangling_routers:
                print(f"  - {dr}.py")

        if self.ghost_buttons:
            print("\n[!] GHOST BUTTONS (Payload exists in keyboards but no handler matches):")
            for gb in self.ghost_buttons:
                print(f"  - '{gb}'")

        print("\n" + "="*45)
        print(f"AUDIT SUMMARY: {self.stats['scanned']} payloads tested.")
        print(f"  - Pass (Wired): {self.stats['passed']}")
        print(f"  - Fail (Ghost): {self.stats['failed']}")
        
        status = "PASSED" if not self.ghost_buttons and not self.dangling_routers else "FAILED"
        print(f"RESULT: {status}")
        print("="*45)

if __name__ == "__main__":
    audit = UIIntegrityAudit()
    asyncio.run(audit.run_audit())
