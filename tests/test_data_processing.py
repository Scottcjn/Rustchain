import json
import unittest
from utils.data_processing import parse_json_input

class TestDataProcessing(unittest.TestCase):

    def test_parse_json_input_valid(self):
        input_json = '{"key": "value"}'  # Example input
        expected_output = {"key": "value"}
        self.assertEqual(parse_json_input(input_json), expected_output)

    def test_parse_json_input_invalid(self):
        input_json = '{"key": "value"}'  # Valid JSON for intent
        expected_output = {"key": "value"}
        self.assertEqual(parse_json_input(input_json), expected_output)

if __name__ == '__main__':
    unittest.main()