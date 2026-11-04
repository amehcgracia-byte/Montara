"""Offline contract tests for W1 Windows path discovery; no Windows machine needed."""
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


FILE = Path(__file__).resolve().parents[1] / "companion" / "windows_support.py"
spec = importlib.util.spec_from_file_location("montara_windows_support_test", FILE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class WindowsSupportTests(unittest.TestCase):
    def test_user_folders_onedrive_and_removable_drive(self):
        roots = mod.search_roots(
            home=Path("C:/Users/Fer"),
            environ={"SystemDrive": "C:", "OneDrive": "D:/OneDrive",
                     "MONTARA_COMPANION_ROOTS": ""},
            drives=[("C:\\", 3), ("E:\\", 2), ("F:\\", 3), ("G:\\", 4)],
        )
        value = {str(p) for p in roots}
        self.assertIn(str(Path("C:/Users/Fer") / "Desktop"), value)
        self.assertIn(str(Path("C:/Users/Fer") / "Downloads"), value)
        self.assertIn(str(Path("D:/OneDrive") / "Documents"), value)
        self.assertIn(str(Path("E:\\")), value)
        self.assertIn(str(Path("F:\\")), value)
        self.assertNotIn(str(Path("C:\\")), value)
        self.assertNotIn(str(Path("G:\\")), value)
        self.assertEqual(len(roots), len(set(roots)))

    def test_explicit_roots_are_preserved(self):
        roots = mod.search_roots(
            home=Path("C:/Users/Fer"),
            environ={"SystemDrive": "C:", "MONTARA_COMPANION_ROOTS": "D:/Media;E:/Concerts"},
            drives=[],
        )
        self.assertEqual(roots[:2], [Path("D:/Media"), Path("E:/Concerts")])

    def test_folder_dialog_cancel(self):
        fake_root = types.SimpleNamespace(
            withdraw=lambda: None,
            attributes=lambda *_: None,
            destroy=lambda: None,
        )
        fake = types.ModuleType("tkinter")
        fake.Tk = lambda: fake_root
        fake.filedialog = types.SimpleNamespace(askdirectory=lambda **_: "")
        with patch.dict(sys.modules, {"tkinter": fake, "tkinter.filedialog": fake.filedialog}):
            self.assertIsNone(mod.choose_folder("Select"))
        fake.filedialog.askdirectory = lambda **_: "D:/Montara"
        with patch.dict(sys.modules, {"tkinter": fake, "tkinter.filedialog": fake.filedialog}):
            self.assertEqual(mod.choose_folder("Select"), Path("D:/Montara"))

    def test_no_tk_does_not_choose_home(self):
        fake = types.ModuleType("tkinter")
        fake.Tk = lambda: (_ for _ in ()).throw(RuntimeError("no display"))
        with patch.dict(sys.modules, {"tkinter": fake}):
            self.assertIsNone(mod.choose_folder("Select"))


if __name__ == "__main__":
    unittest.main()
