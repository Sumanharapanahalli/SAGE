"""Run ETL tests with psycopg2 stubbed out (no live DB required)."""
import sys
import unittest.mock

sys.modules['psycopg2'] = unittest.mock.MagicMock()
sys.modules['psycopg2.extras'] = unittest.mock.MagicMock()
sys.path.insert(0, 'data_pipeline')

import pytest
sys.exit(pytest.main(['-v', '--tb=short', 'data_pipeline/test_etl_pipeline.py']))
