import json
import logging
import os
import re
from datetime import datetime

import sklearn
from graphviz import Source
from sklearn.feature_extraction import DictVectorizer
from sklearn.tree import DecisionTreeRegressor
from sklearn.tree.tree import BaseDecisionTree


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
        row = car_to_row(car)
        X.append(row)

        # price
        price = extract_price(car)
        y.append(price)

    vec = DictVectorizer()
    X = vec.fit_transform(X)

    regr = DecisionTreeRegressor(min_samples_leaf=25, criterion='mae')
    regr.fit(X, y)

    if isinstance(regr, BaseDecisionTree):
        generate_tree_visualization(regr, vec)

    predictions = generate_predictions(cars, regr, vec)
    for prediction in sorted(predictions, key=lambda p: p['price']['difference']):
        print(prediction['car']['url'])
        print('listed with:  %d' % prediction['price']['actual'])
        print('worth around: %d' % prediction['price']['inferred'])
        print('difference:   %d' % prediction['price']['difference'])


def generate_predictions(cars, regr, vec):
    predictions = []
    for i in range(len(cars)):
        car = cars[i]

        price_actual = extract_price(car)

        car_row = car_to_row(car)
        row_transformation = vec.transform(car_row)
        price_inferred = int(regr.predict(row_transformation))

        difference = price_actual - price_inferred
        is_cheap = difference < 0

        prediction = {
            'price': {
                'actual': price_actual,
                'inferred': price_inferred,
                'difference': difference,
                'is_cheap': is_cheap,
            },
            'car': car,
        }
        predictions.append(prediction)
    return predictions


def extract_price(car):
    price_raw = car['mobile']['web']['price'].replace('.', '')
    price = int(re.findall(r'\d+', price_raw)[0])
    return price


def car_to_row(car):
    row = {}

    # mileage
    mileage_wo_dot = car['mobile']['web']['technical']['mileage'].replace('.', '')
    mileage = int(re.findall(r'\d+', mileage_wo_dot)[0])
    row['mileage'] = mileage

    # times
    first_registration_raw = car['mobile']['web']['technical']['firstRegistration']
    first_registration = datetime.strptime(first_registration_raw, '%m/%Y')
    time_since_registration_in_years = (datetime.now() - first_registration).total_seconds() / (60 * 60 * 24 * 365)
    row['car_age_in_years'] = time_since_registration_in_years

    # hu/au
    row['time_to_hu_in_months'] = -1000
    if 'hu' in car['mobile']['web']['technical']:
        hu_raw = car['mobile']['web']['technical']['hu']
        if hu_raw == 'Neu':
            time_to_hu = 0.0
        else:
            hu = datetime.strptime(hu_raw, '%m/%Y')
            time_to_hu = (hu - datetime.now()).total_seconds() / (60 * 60 * 24 * 12)

        row['time_to_hu_in_months'] = time_to_hu

    # power
    power_in_ps = -1
    if 'power' in car['mobile']['web']['technical']:
        power_raw = car['mobile']['web']['technical']['power']
        power_in_ps = int(re.findall(r'\d+', power_raw)[1])
    else:
        logging.warning('no power found')
    row['power_ps'] = power_in_ps

    # previous owners
    if 'numberOfPreviousOwners' in car['mobile']['web']['technical']:
        row['owners'] = int(car['mobile']['web']['technical']['numberOfPreviousOwners'])

    # cubic
    if 'cubicCapacity' in car['mobile']['web']['technical']:
        cubic_capacity_raw = car['mobile']['web']['technical']['cubicCapacity'].replace('.', '')
        cubic_capacity = int(re.findall(r'\d+', cubic_capacity_raw)[0])
        row['cubic_capacity'] = cubic_capacity

    # inlining features
    if car['mobile']['web']['features'] is not None:
        for feature in car['mobile']['web']['features']:
            row['features_' + feature] = True
    else:
        row['feature_none'] = True

    # tech details as strings
    excluded_keys = ['mileage', 'firstRegistration', 'hu', 'power', 'cubicCapacity', 'numberOfPreviousOwners']
    row.update({k: v for k, v in car['mobile']['web']['technical'].items() if k not in excluded_keys})

    # add data from dart
    keys_from_dart = ['adSpecificsMake', 'adSpecificsMakeModel', 'adSpecificsModel']
    row.update({k: v for k, v in car['mobile']['dart'].items() if k in keys_from_dart})

    return row


def generate_tree_visualization(regr, vec):
    dot_filename = "tree.dot"
    gv_filename = 'tree.gv'

    with open(dot_filename, 'w') as f:
        sklearn.tree.export_graphviz(regr, out_file=f, feature_names=vec.get_feature_names())
    with open(dot_filename, 'r') as f:
        src = Source(f.read())
        src.render(gv_filename, view=True)


if __name__ == '__main__':
    main()
