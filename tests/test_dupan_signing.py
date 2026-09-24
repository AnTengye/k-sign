import unittest

from dupan_signing import _rc4, native_rand_pair, native_rchannel


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


if __name__ == "__main__":
    unittest.main()
