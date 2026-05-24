# for j from  1 to n -1
# key=arr[j]
# i = j -1 
# while i >= 0 and arr[i] < key:
#     arr[i+1] = arr[i]
#     i = i - 1
# arr[i+1] = key

def insertion_sort_desc(arr):
    for j in range(1, len(arr)):
        key = arr[j]
        i = j - 1
        while i >= 0 and arr[i] < key:
            arr[i+1] = arr[i]
            i = i - 1
        arr[i+1] = key
    return arr

if __name__ == "__main__":
    numbers = [11, 10, 3, 16, 41, 31, 1, 4]
    print("Original:", numbers)
    print("Sorted (decreasing):", insertion_sort_desc(numbers.copy()))