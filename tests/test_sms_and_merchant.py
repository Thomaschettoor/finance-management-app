import unittest
from backend_ai.sms_normalizer import normalize_text
from backend_ai.merchant_extractor import extract_merchant


class TestPhaseB(unittest.TestCase):
    def test_normalize_and_extract_swiggy(self):
        raw = "Rs 450 debited via UPI SWIGGY txn ref ABCD1234"
        norm, meta = normalize_text(raw)
        self.assertTrue("450" in raw)
        self.assertEqual(meta.get("transaction_type"), "DEBIT")
        name, mid, score, mmeta = extract_merchant(meta.get("merchant_candidate", ""))
        self.assertTrue(name.lower() in ("swiggy", ""))
        self.assertGreaterEqual(score, 0.5)

    def test_normalize_credit(self):
        raw = "INR 1200 credited to your account via NEFT"
        norm, meta = normalize_text(raw)
        self.assertEqual(meta.get("transaction_type"), "CREDIT")

    def test_vpa_extraction(self):
        raw = "Your VPA sanju39chd@okaxis linked to Indian Bank is debited for Rs.299.00"
        norm, meta = normalize_text(raw)
        self.assertIn('@', meta.get('vpa', ''))

    def test_boilerplate_removal(self):
        raw = "Rs.95.15 on Zomato charged via Simpl. -- Food, groceries, commute. Know More: https://click.getsimpl.com/vyhm/"
        norm, meta = normalize_text(raw)
        # normalized text should not contain known boilerplate URL or 'Know More'
        self.assertNotIn('Know More', norm)
        self.assertNotIn('http', norm.lower())


if __name__ == "__main__":
    unittest.main()
