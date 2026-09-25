import unittest

from dupan_signing import _rc4, extract_sofire_material, native_rand_pair, native_rchannel, sofire_z


class NativeRandTests(unittest.TestCase):
    def test_rc4_known_vector(self):
        self.assertEqual(_rc4(b"Plaintext", b"Key").hex(), "bbf316e8d940af0ad3")

    def test_synthetic_android_pair(self):
        rand, rand2 = native_rand_pair(
            "synthetic-bduss", "123456789", "R7A0VSkyHLCChONU5mM2QnOAu6R7m3s+RL/Pz3mKABc=",
            "1780000000", "synthetic-device-identifier", "13.32.1")
        self.assertEqual(rand, "c336b76ac4ddb3849e80cf9f5994e34ced514e13")
        self.assertEqual(rand2, "c9826fc612c6ec72d93ed1cf3cd3a7547e1eb2b3")

    def test_synthetic_rchannel(self):
        self.assertEqual(native_rchannel("123456789", "1780000000", "synthetic-channel"),
                         "db74c5ee8bdcb16071afb61f8ea41b9a")

    def test_rejects_unusable_inputs(self):
        args = ["synthetic-bduss", "123456789", "R7A0VSkyHLCChONU5mM2QnOAu6R7m3s+RL/Pz3mKABc=",
                "1780000000", "synthetic-device-identifier", "13.32.1"]
        for index, value in ((0, ""), (1, "bad-uid"), (2, "bad?"), (3, "yesterday"),
                             (4, "x\n"), (5, "x")):
            with self.subTest(index=index):
                candidate = list(args)
                candidate[index] = value
                with self.assertRaises(ValueError):
                    native_rand_pair(*candidate)

    def test_sofire_z_offline_round_trip(self):
        material = {"seed": "0123456789ABCDEF0123456789ABCDEF", "status": 101,
                    "flag1": 10, "flag2": 207, "flag3": "08"}
        z = sofire_z(**material, timestamp="1780000000", random_hex="A1B2C3")
        self.assertEqual(z, "2D583210BA98FEDC5531765432108EBA983CFEDC7654A1A500B208C36A18")
        self.assertEqual(len(z), 60)
        self.assertEqual(extract_sofire_material(z), material)
        self.assertEqual(z[44:46] + z[50:52] + z[54:56], "A1B2C3")
        self.assertEqual(int(z[56:60] + z[46:50], 16), 1780000000)

    def test_sofire_z_rejects_invalid_material(self):
        material = {"seed": "0123456789ABCDEF0123456789ABCDEF", "status": 101,
                    "flag1": 10, "flag2": 207, "flag3": "08", "timestamp": "1780000000"}
        for key, value in (("seed", "invalid"), ("status", 300), ("flag1", -1),
                           ("flag2", True), ("flag3", "G0"), ("timestamp", "bad")):
            with self.subTest(key=key):
                candidate = {**material, key: value}
                with self.assertRaises(ValueError):
                    sofire_z(**candidate)
        with self.assertRaises(ValueError):
            extract_sofire_material("short")
        good = sofire_z(**material, random_hex="A1B2C3")
        with self.assertRaises(ValueError):
            extract_sofire_material("00" + good[2:])


if __name__ == "__main__":
    unittest.main()
