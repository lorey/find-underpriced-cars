import json
import os
import re
from datetime import datetime

import logging
import sklearn
from graphviz import Source
from sklearn.feature_extraction import DictVectorizer
from sklearn.tree import DecisionTreeRegressor


def main():
    cars = []
    directory = os.getcwd() + '/cars'
    file_list = os.listdir(directory)
    for filename in file_list:
        with open(directory + '/' + filename) as file:
            json_string = file.read()
        car = json.loads(json_string)
        cars.append(car)

    X = []
    y = []
    for car in cars:
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

        # power
        power_in_ps = -1
        if 'power' in car['mobile']['technical']:
            power_raw = car['mobile']['technical']['power']
            power_in_ps = int(re.findall(r'\d+', power_raw)[1])
        else:
            logging.warning('no power found')
        row['power_ps'] = power_in_ps

        # previous owners
        if 'numberOfPreviousOwners' in car['mobile']['technical']:
            row['owners'] = int(car['mobile']['technical']['numberOfPreviousOwners'])

        # cubic
        if 'cubicCapacity' in car['mobile']['technical']:
            cubic_capacity_raw = car['mobile']['technical']['cubicCapacity'].replace('.', '')
            cubic_capacity = int(re.findall(r'\d+', cubic_capacity_raw)[0])
            row['cubic_capacity'] = cubic_capacity
        else:
            logging.warning('no cubic capacity found')

        # inlining features
        if car['mobile']['features'] is not None:
            for feature in car['mobile']['features']:
                row['features_' + feature] = True
        else:
            row['feature_none'] = True

        # tech details as strings
        excluded_keys = ['mileage', 'firstRegistration', 'hu', 'power', 'cubicCapacity', 'numberOfPreviousOwners']
        row.update({k: v for k, v in car['mobile']['technical'].items() if k not in excluded_keys})

        X.append(row)

        # price
        price_raw = car['mobile']['price'].replace('.', '')
        price = int(re.findall(r'\d+', price_raw)[0])
        y.append(price)

    vec = DictVectorizer()
    X = vec.fit_transform(X)

    regr = DecisionTreeRegressor(min_samples_leaf=50)
    regr.fit(X, y)

    generate_tree_visualization(regr, vec)

    for i in range(len(cars)):
        price_actual = y[i]
        price_inferred = int(regr.predict(X[i]))

        differece = price_actual - price_inferred
        is_cheap = differece < 0
        print(price_actual, price_inferred, differece, is_cheap)


def generate_tree_visualization(regr, vec):
    with open("iris.dot", 'w') as f:
        sklearn.tree.export_graphviz(regr, out_file=f, feature_names=vec.get_feature_names())
    with open("iris.dot", 'r') as f:
        src = Source(f.read())
        src.render('iris.gv', view=True)


if __name__ == '__main__':
    main()