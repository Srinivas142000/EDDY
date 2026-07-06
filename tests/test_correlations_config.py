import os
import unittest
from unittest.mock import patch

import correlations


class CorrelationsConfigTests(unittest.TestCase):
    def test_default_budget_limit(self):
        with patch.dict(os.environ, {}, clear=False):
            self.assertEqual(correlations.get_run_budget_limit(), correlations.DEFAULT_MAX_NEW_PER_RUN)

    def test_environment_override_budget_limit(self):
        with patch.dict(os.environ, {"EDDY_MAX_NEW_PER_RUN": "7"}, clear=False):
            self.assertEqual(correlations.get_run_budget_limit(), 7)


if __name__ == "__main__":
    unittest.main()
