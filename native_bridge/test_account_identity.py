"""A bridge restart keeps its own identity without taking over HA's SID."""

import unittest

from account_identity import native_static_fields


class NativeIdentityTests(unittest.TestCase):
    def test_stable_distinct_installation_id(self) -> None:
        fields = {"deviceId": "owner-app-id", "clientId": "app-client"}
        first = native_static_fields(fields)
        self.assertEqual(first, native_static_fields(fields))
        self.assertNotEqual(first["deviceId"], fields["deviceId"])
        self.assertEqual(first["clientId"], fields["clientId"])
        self.assertEqual(fields["deviceId"], "owner-app-id")

    def test_requires_source_installation_id(self) -> None:
        with self.assertRaises(ValueError):
            native_static_fields({"clientId": "app-client"})


if __name__ == "__main__":
    unittest.main()
