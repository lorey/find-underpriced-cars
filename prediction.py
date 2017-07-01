import json
import re

import logging

import sklearn
from graphviz import Source
from sklearn.tree import DecisionTreeRegressor


def main():
    with open('cars.json') as file:
        json_string = file.read()
    data = json.loads(json_string)

    X = []
    y = []
    for car in data:
        try:
            mileage_wo_dot = car['mobile']['technical']['mileage'].replace('.', '')
            mileage = int(re.findall(r'\d+', mileage_wo_dot)[0])

            price = int(re.findall(r'\d+', car['mobile']['price'])[0])

            row = [mileage]
            X.append(row)
            y.append(price)
        except:
            logging.exception('Something went wrong')

    regr = DecisionTreeRegressor(min_samples_leaf=20)
    regr.fit(X, y)

    with open("iris.dot", 'w') as f:
        sklearn.tree.export_graphviz(regr, out_file=f)

    with open("iris.dot", 'r') as f:
        src = Source(f.read())
        src.render('test-output/holy-grenade.gv', view=True)

if __name__ == '__main__':
    main()