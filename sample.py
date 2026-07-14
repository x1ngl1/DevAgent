def add(a, b):
    return a + b

def divide(a, b):
    if b == 0:
        raise ValueError("除数不能为0")
    return a / b

def process_list(data):
    if not data:
        return []
    return [x * 2 for x in data if x > 0]
