"""The welcome window's translations: complete, consistent, and covering every key the QML uses."""
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from lynux import i18n  # noqa: E402

QML = ROOT / "runtime/lynux/qml"
# Keys QML builds at runtime: "tool_" + harness id, "stage_" + progress stage from lynux-state.
STAGES = ("allocate", "format", "open", "bind")


class StringTests(unittest.TestCase):
    def test_every_entry_has_all_languages_and_matching_placeholders(self):
        for key, values in i18n.STRINGS.items():
            self.assertEqual(len(values), 4, key)
            self.assertTrue(all(value.strip() for value in values), key)
            placeholders = [sorted(re.findall(r"%\d", value)) for value in values]
            self.assertTrue(all(found == placeholders[0] for found in placeholders), key)

    def test_qml_only_uses_keys_that_exist(self):
        used = set()
        for path in QML.glob("*.qml"):
            used.update(re.findall(r"app\.s\.(\w+)", path.read_text(encoding="utf-8")))
        tools = json.loads((ROOT / "config/harnesses.json").read_text())["harnesses"]
        used.update(f"tool_{tool}" for tool in tools)
        used.update(f"stage_{stage}" for stage in STAGES)
        self.assertEqual(sorted(used - set(i18n.STRINGS)), [])

    def test_hong_kong_uses_local_words(self):
        self.assertIn("網絡", i18n.strings("zh_HK")["home_online"])
        self.assertIn("網路", i18n.strings("zh_TW")["home_online"])

    def test_locale_values_map_to_supported_languages(self):
        cases = {"zh_CN.UTF-8": "zh_CN", "zh_TW": "zh_TW", "zh_HK:zh_TW": "zh_HK", "ja": "ja_JP",
                 "en_GB.UTF-8": "en_US", "C.UTF-8": None, "fr_FR": None}
        for value, expected in cases.items():
            self.assertEqual(i18n.match(value), expected, value)

    def test_plasma_setting_wins_over_environment_and_english_is_the_default(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(i18n.detect(folder, {}), "en_US")
            self.assertEqual(i18n.detect(folder, {"LANG": "ja_JP.UTF-8"}), "ja_JP")
            (Path(folder) / "plasma-localerc").write_text("[Translations]\nLANGUAGE=zh_HK:zh_TW\n")
            self.assertEqual(i18n.detect(folder, {"LANG": "ja_JP.UTF-8"}), "zh_HK")

    def test_every_language_has_a_generated_locale(self):
        generated = (ROOT / "overlay/etc/locale.gen").read_text().split()
        for code in i18n.CODES:
            locale, _ = i18n.settings(code)
            self.assertIn(locale, generated)


if __name__ == "__main__":
    unittest.main()
