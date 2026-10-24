#!/bin/python3

import numpy as np
import pandas as pd

##total revenue made : qty * price
def sum_of_two_arr(arr1, arr2):
    arr1 = np.array(arr1)
    arr2 = np.array(arr2)
    
    if arr1.size != arr2.size:
        raise ValueError("Wrong size of tables")
    return np.sum(arr1 * arr2)

##number of orders (order lines) of a certain product
def count_orders(arr1, pdt):
    return int((pd.Series(arr1) == pdt).sum())

##number of unique customers who bought a certain product
def n_number_clients(arr1, pdt, customers):
    products = pd.Series(arr1).reset_index(drop=True)
    buyers = pd.Series(customers).reset_index(drop=True)

    if len(products) != len(buyers):
        raise ValueError("Wrong size of tables")
    return int(buyers[products == pdt].nunique())

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

#n most sold product: the biggest total quantity first, ties ordered by product name
def top_n_product(n, arr1, pdts):
    quantities = pd.Series(arr1).reset_index(drop=True)
    products = pd.Series(pdts).reset_index(drop=True)
    totals = quantities.groupby(products).sum().sort_values(ascending=False, kind="stable")

    if n < 0 or n > len(totals):
        print("Wrong number of products")
        exit(84)
    top = totals.head(n)
    for rank, (product, qty) in enumerate(top.items(), start=1):
        print(rank, "-", product, " sold ", qty, " times")
    return list(top.index)
