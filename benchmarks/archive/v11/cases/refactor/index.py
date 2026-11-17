def build_index(documents):
    return [(document['id'], document['text']) for document in documents]

def find_matches(index, query):
    return [doc_id for doc_id, text in index if query in text]
