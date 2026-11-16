def frequencies(items):
    result={}
    for item in items:
        result[item]=result.get(item,0)+1
    return result
