#!/bin/python3

import pandas as pd

df = pd.read_csv('data.csv')
x = df["Calories"].mean()
print(x)
#print(df)
