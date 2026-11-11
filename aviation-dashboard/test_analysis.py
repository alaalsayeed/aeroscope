import unittest
from analyze import fit, predict, metrics


class AnalysisAlgorithmTests(unittest.TestCase):
    def test_tree_boundary_and_probability_smoothing(self):
        rows = [{"x": i, "y": int(i >= 3)} for i in range(6)]
        tree = fit(rows, "y", ["x"])
        self.assertEqual(tree["threshold"], 2.5)
        self.assertEqual(predict(tree, {"x": 2.5})[0], 0.2)
        self.assertEqual(predict(tree, {"x": 2.5001})[0], 0.8)

    def test_regression_leaf_uses_training_mean(self):
        rows = [{"x": 0, "target": 1.0}, {"x": 1, "target": 3.0}]
        tree = fit(rows, "target", ["x"], classification=False)
        self.assertEqual(predict(tree, {"x": 5})[0], 2.0)

    def test_classification_metrics(self):
        result = metrics([0, 1], [0.2, 0.8], classification=True)
        self.assertEqual(result["accuracy"], 1.0)
        self.assertEqual(result["TP"], 1)
        self.assertEqual(result["TN"], 1)
        self.assertEqual(result["FP"], 0)
        self.assertEqual(result["FN"], 0)


if __name__ == "__main__":
    unittest.main()
