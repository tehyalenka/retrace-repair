import unittest
from search import search_documents
from index import build_index, find_matches

DOCS = [{'id':1,'text':'Straße'}, {'id':2,'text':'STRASSE'}, {'id':3,'text':'cat'}, {'id':4,'text':'Cat'}]
class SearchVerification(unittest.TestCase):
    def test_default_exact(self):
        self.assertEqual(search_documents('Cat', DOCS), [4])
        self.assertEqual(search_documents('STRASSE', DOCS), [2])
    def test_unicode_casefold(self):
        self.assertEqual(search_documents('strasse', DOCS, case_insensitive=True), [1,2])
        self.assertEqual(search_documents('CAT', DOCS, case_insensitive=True), [3,4])
    def test_empty_query(self):
        self.assertEqual(search_documents('', DOCS, case_insensitive=True), [1,2,3,4])
    def test_no_mutation(self):
        before = [dict(x) for x in DOCS]
        search_documents('cat', DOCS, case_insensitive=True)
        self.assertEqual(DOCS, before)
    def test_existing_index_api(self):
        self.assertEqual(find_matches(build_index(DOCS), 'Cat'), [4])
