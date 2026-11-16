from index import build_index, find_matches

def search_documents(query, documents):
    return find_matches(build_index(documents), query)
