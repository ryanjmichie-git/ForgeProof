from __future__ import annotations

import unittest

from demo_math import safe_add


class DemoMathTests(unittest.TestCase):
    def test_safe_add_positive_numbers(self) -> None:
        self.assertEqual(safe_add(2, 3), 5)

    def test_safe_add_commutative(self) -> None:
        self.assertEqual(safe_add(9, 4), safe_add(4, 9))


if __name__ == "__main__":
    unittest.main()

