#!/bin/python3

import numpy as np

##total revenue made : qty * price
def sum_of_two_arr(arr1, arr2):
    arr1 = np.array(arr1)
    arr2 = np.array(arr2)
    
    if arr1.size != arr2.size:
        raise Value_error("Wrong size of tables")
    return np.sum(arr1 * arr2)

##number of clients who bought a certain product
def n_number_clients(arr1, pdt):
    count = 0
    
    for i in range(len(arr1)):
        if arr1[i] == pdt:
            count += 1
    return count

##comparing an elmt to an array
def compare_it(elmt, items):
    for j in range(len(items)):
        if elmt == items[j]:
            return 1
    return 0

##finding all uniue items sold
def n_items(arr):
    c = 0
    items = []

    items.append(arr[0])
    for i in range(len(arr)):
        if compare_it(arr[i], items) == 0:
            items.append(arr[i])
    return sorted(items)

#num of products sold for a particular pdt
def num_products(item, arr1, pdt):
    n = 0
    
    for i in range(len(pdt)):
        if item == pdt[i]:
            n += arr1[i]
    return n

#associate function for top_n_product
def compare_n_pdt(elmt, items):
    for j in range(len(items)):
        if (elmt == items[j]):
            return j
    return 0

#n most sold product 
def top_n_product(n, arr1, pdts):
    items = n_items(pdts)
    arr1 = np.array(arr1)
    item_qty = [0] * len(items)
    top_n = []

    if n > len(items):
        print("Wrong number of products")
        exit(84)
    for i in range(len(items)):
        item_qty[i] = num_products(items[i], arr1, pdts)
    sorted_item_qty = sorted(item_qty)
    sorted_item_qty.reverse()
    i = 0
    for j in range(len(sorted_item_qty)):
        p = compare_n_pdt(sorted_item_qty[j], item_qty)
        if i == n:
            break
        if p != 0:
            print(i+1, "-", items[p], " sold ", item_qty[p], " times")
            top_n.append(items[p])
            i += 1
    return top_n
