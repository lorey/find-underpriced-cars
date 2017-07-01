import json
import re

import logging
from datetime import datetime

import sklearn
from graphviz import Source
from sklearn.feature_extraction import DictVectorizer
from sklearn.tree import DecisionTreeRegressor


def main():
    with open('cars.json') as file:
        json_string = file.read()
    data = json.loads(json_string)

    X = []
    y = []
    for car in data:
        row = {}

        # mileage
        mileage_wo_dot = car['mobile']['technical']['mileage'].replace('.', '')
        mileage = int(re.findall(r'\d+', mileage_wo_dot)[0])
        row['mileage'] = mileage

        # times
        first_registration_raw = car['mobile']['technical']['firstRegistration']
        first_registration = datetime.strptime(first_registration_raw, '%m/%Y')
        time_since_registration_in_years = (datetime.now() - first_registration).total_seconds() / (60 * 60 * 24 * 365)
        row['car_age_in_years'] = time_since_registration_in_years

        row['time_to_hu_in_months'] = -1000
        if 'hu' in car['mobile']['technical']:
            hu_raw = car['mobile']['technical']['hu']
            if hu_raw == 'Neu':
                time_to_hu = 0.0
            else:
                hu = datetime.strptime(hu_raw, '%m/%Y')
                time_to_hu = (hu - datetime.now()).total_seconds() / (60 * 60 * 24 * 12)

            row['time_to_hu_in_months'] = time_to_hu

        # inlining features
        if car['mobile']['features'] is not None:
            for feature in car['mobile']['features']:
                row['features_' + feature] = True
        else:
            row['feature_none'] = True

        # tech details as strings
        row.update(car['mobile']['technical'])

        X.append(row)

        # price
        price_raw = car['mobile']['price'].replace('.', '')
        price = int(re.findall(r'\d+', price_raw)[0])
        y.append(price)

    vec = DictVectorizer()
    X = vec.fit_transform(X)

    regr = DecisionTreeRegressor(min_samples_leaf=50)
    regr.fit(X, y)

    with open("iris.dot", 'w') as f:
        sklearn.tree.export_graphviz(regr, out_file=f, feature_names=vec.get_feature_names())

    with open("iris.dot", 'r') as f:
        src = Source(f.read())
        src.render('iris.gv', view=True)

    for i in range(len(data)):
        price_actual = y[i]
        price_inferred = int(regr.predict(X[i]))

        differece = price_actual - price_inferred
        is_cheap = differece < 0
        print(price_actual, price_inferred, is_cheap)

if __name__ == '__main__':
    main()