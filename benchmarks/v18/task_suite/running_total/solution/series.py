def running_total(values):
    total=0
    out=[]
    for value in values:
        total+=value
        out.append(total)
    return out
