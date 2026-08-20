import importlib
import importlib.util
import json
import os
import sys
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import Mock


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)


class InstrumentDirectoryStateTests(unittest.TestCase):
    def test_empty_state_is_a_versioned_empty_directory(self):
        module = (
            importlib.import_module("instrument_directory")
            if importlib.util.find_spec("instrument_directory")
            else None
        )

        self.assertIsNotNone(module, "共享标的目录模块尚未实现")
        self.assertEqual(
            module.empty_directory_state(),
            {"version": 1, "custom_instruments": [], "hidden_symbols": []},
        )

    def test_custom_observation_preserves_resolved_name_and_not_a_strategy_instrument(self):
        from instrument_directory import add_custom_instrument

        state = add_custom_instrument(
            {"version": 1, "custom_instruments": [], "hidden_symbols": []},
            "600887",
            "伊利股份",
        )

        self.assertEqual(
            state["custom_instruments"],
            [{"symbol": "600887", "name": "伊利股份", "market": "CN", "category": "自定义"}],
        )
        self.assertEqual(add_custom_instrument(state, "600887", "别的名字"), state)

    def test_hiding_and_restoring_are_reversible(self):
        from instrument_directory import hide_instrument, restore_instrument

        state = {"version": 1, "custom_instruments": [], "hidden_symbols": []}
        hidden = hide_instrument(state, "563360")

        self.assertEqual(hidden["hidden_symbols"], ["563360"])
        self.assertEqual(restore_instrument(hidden, "563360"), state)

    def test_directory_merges_custom_entries_and_hides_builtin_without_changing_strategy_rules(self):
        from instrument_directory import apply_directory_state
        from instruments import get_instrument, list_instruments

        state = {
            "version": 1,
            "custom_instruments": [{"symbol": "600887", "name": "600887 · 自定义观察", "market": "CN", "category": "自定义"}],
            "hidden_symbols": ["510300"],
        }

        specs = apply_directory_state(list_instruments(), state)
        self.assertEqual([spec.symbol for spec in specs][-1], "600887")
        self.assertNotIn("510300", [spec.symbol for spec in specs])
        custom = specs[-1]
        self.assertFalse(custom.is_core)
        self.assertFalse(custom.supports_campaign)
        self.assertFalse(custom.supports_backtest)
        self.assertTrue(get_instrument("510300").is_core)

    def test_invalid_state_and_invalid_custom_code_are_rejected(self):
        from instrument_directory import DirectoryStateError, add_custom_instrument, normalize_directory_state

        with self.assertRaisesRegex(DirectoryStateError, "版本"):
            normalize_directory_state({"version": 2, "custom_instruments": [], "hidden_symbols": []})
        with self.assertRaisesRegex(DirectoryStateError, "六位"):
            add_custom_instrument({"version": 1, "custom_instruments": [], "hidden_symbols": []}, "HSI")


class GitHubDirectoryStoreTests(unittest.TestCase):
    def test_read_decodes_github_contents_response_and_keeps_sha(self):
        from instrument_directory import GitHubDirectoryStore

        payload = {"version": 1, "custom_instruments": [], "hidden_symbols": []}
        response = Mock()
        response.read.return_value = json.dumps(
            {"sha": "abc123", "content": "eyJ2ZXJzaW9uIjoxLCJjdXN0b21faW5zdHJ1bWVudHMiOltd\nLCJoaWRkZW5fc3ltYm9scyI6W119"}
        ).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock(return_value=response)

        snapshot = GitHubDirectoryStore(token="secret", opener=opener).read()

        self.assertEqual(snapshot.state, payload)
        self.assertEqual(snapshot.sha, "abc123")
        request = opener.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")

    def test_write_uses_sha_and_only_configured_directory_path(self):
        from instrument_directory import DirectorySnapshot, GitHubDirectoryStore

        response = Mock()
        response.read.return_value = b'{"commit": {"sha": "newsha"}}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock(return_value=response)
        store = GitHubDirectoryStore(token="secret", opener=opener)
        snapshot = DirectorySnapshot({"version": 1, "custom_instruments": [], "hidden_symbols": []}, "oldsha")

        commit_sha = store.write(snapshot, snapshot.state, "directory: reset")

        self.assertEqual(commit_sha, "newsha")
        request = opener.call_args.args[0]
        self.assertEqual(request.get_method(), "PUT")
        self.assertTrue(request.full_url.endswith("/repos/milaotou001/etf-quant/contents/mobile/instrument_directory.json"))
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["sha"], "oldsha")
        self.assertEqual(body["message"], "directory: reset")

    def test_write_requires_token_and_translates_conflict_and_network_errors(self):
        from instrument_directory import DirectoryRemoteError, DirectorySnapshot, GitHubDirectoryStore

        snapshot = DirectorySnapshot({"version": 1, "custom_instruments": [], "hidden_symbols": []}, "oldsha")
        with self.assertRaisesRegex(DirectoryRemoteError, "DIRECTORY_GITHUB_TOKEN"):
            GitHubDirectoryStore(token=None).write(snapshot, snapshot.state, "directory: reset")

        conflict = HTTPError("https://api.github.com", 409, "conflict", None, None)
        with self.assertRaisesRegex(DirectoryRemoteError, "已被其他设备修改"):
            GitHubDirectoryStore(token="secret", opener=Mock(side_effect=conflict)).write(
                snapshot, snapshot.state, "directory: reset"
            )

        with self.assertRaisesRegex(DirectoryRemoteError, "网络"):
            GitHubDirectoryStore(token="secret", opener=Mock(side_effect=URLError("offline"))).read()


class DirectoryAccessTests(unittest.TestCase):
    def test_management_pin_must_be_configured_and_match(self):
        from instrument_directory import directory_admin_pin_matches

        self.assertFalse(directory_admin_pin_matches("1234", {}))
        self.assertFalse(directory_admin_pin_matches("wrong", {"DIRECTORY_ADMIN_PIN": "1234"}))
        self.assertTrue(directory_admin_pin_matches("1234", {"DIRECTORY_ADMIN_PIN": "1234"}))


if __name__ == "__main__":
    unittest.main()
