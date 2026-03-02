def multiply(a, b):
    print(a * b)

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 2:
        a = int(sys.argv[1])
        b = int(sys.argv[2])
        multiply(a, b)