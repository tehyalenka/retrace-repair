import unittest
from search import search_documents

class Smoke(unittest.TestCase):
    def test_exact(self):
        self.assertEqual(search_documents('Cat', [{'id': 1, 'text': 'Cat'}]), [1])
