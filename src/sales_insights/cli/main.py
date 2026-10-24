#!/bin/python3

from sales_insights.analytics import legacy as cal
from sales_insights.cli import usage as use
from sales_insights.data.loader import load_orders
from sales_insights.data.schema import SchemaError
import sys
import os

def main():
    args = sys.argv[1:]
    if len(args) == 0:
        print("Wrong number of input")
        exit(84)
    if args[0] == "-h" and len(args) == 1:
        use.usage()
        exit(0)
    if len(args) < 2:
        print("Wrong number of argument")
        use.usage()
        exit(84)
    if os.path.isfile(args[len(args)-1]):
        try:
            sales = load_orders(args[len(args)-1])
        except SchemaError as error:
            print(error)
            exit(84)
    else:
        print("Wrong Filepath")
        use.usage()
        exit(84)
    i = 0
    while i < len(args)-1:
        if args[i] == "-T":
            print("Total Revenue: ", cal.sum_of_two_arr(sales["Quantity"], sales["UnitPrice"]))
            i += 1
        elif args[i] == "-c":
            print("Number of clients that bought: ", args[i+1], "=", cal.n_number_clients(sales["Product"], args[i+1], sales["CustomerID"]))
            i += 2
        elif args[i] == "-u":
            print("Items sold:", end=' ')
            items = cal.n_items(sales["Product"])
            print(items)
            i += 1
        elif args[i] == "-p":
            print("Number of", args[i+1], "sold: ", cal.num_products(args[i+1], sales["Quantity"], sales["Product"]))
            i += 2
        elif args[i] == "-t":
            print("Top ", args[i+1], ": ", cal.top_n_product(int(args[i+1]), sales["Quantity"], sales["Product"]))
            i += 2
        else:
            print("Wrong argument\n")
            use.usage()
            exit(84)

            
if __name__ == "__main__":
    main()
