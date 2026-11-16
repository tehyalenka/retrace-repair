from formatter import format_record

def render_report(records):
    return '\n'.join(format_record(r) for r in records)
