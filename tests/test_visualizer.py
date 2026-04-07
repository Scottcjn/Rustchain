import unittest
from src.visualizations.visualizer import visualize_hardware_fingerprint

class TestVisualizer(unittest.TestCase):

    def test_visualize_hardware_fingerprint(self):
        data = {"Channel 1": 0.8, "Channel 2": 0.6, "Channel 3": 0.9}
        try:
            visualize_hardware_fingerprint(data)
            result = True  # If no exceptions, we assume success
        except Exception as e:
            result = False  # If there is an exception, we fail the test
        self.assertTrue(result, "Visualization generation failed")

if __name__ == '__main__':
    unittest.main()