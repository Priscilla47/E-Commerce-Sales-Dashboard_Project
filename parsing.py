#!/bin/python3

import sys
import csv
import decimal

def file_handling(sys, count, len):
    i = 0
    name = []
    with open('105demography_data.csv', mode ='r')as file:
        csvFile = csv.reader(file, delimiter=';')
        for lines in csvFile:
            while i < len:
                if (sys.argv[count] == lines[i]):
                    name.append(lines[0])
                i += 1
    print("Country: ", name)
    with open('105demography_data.csv', mode ='r')as file:
        csvFile = csv.reader(file, delimiter=';')
        get_info(csvFile, sys, count)
if sys.argv[1] == "-h":
    print("USAGE\n   ./import csv105demography [code]+\n")
    print("DESCRIPTION\n   code country code")
    sys.exit(0)
count = 1
len  = len(sys.argv)
print("count = ", len)
file_handling(sys, count, len)
