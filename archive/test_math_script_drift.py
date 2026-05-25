import sys

def multiply_args(a, b):
    result = float(a) * float(b)
    print(result)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python test_math_script.py <num1> <num2>")
    else:
        multiply_args(sys.argv[1], sys.argv[2])