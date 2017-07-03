import json
import os
import re
from datetime import datetime
from time import sleep

import numpy
import pandas
import sklearn
from graphviz import Source
from sklearn.tree import DecisionTreeRegressor
from sklearn.tree.tree import BaseDecisionTree


def main():
    while True:
        predictions = train_and_predict()
        sleep(300)
        # print_best_predictions(predictions)


def print_best_predictions(predictions):
    best_predictions = sorted(predictions, key=lambda p: p['price']['difference'])[0:50]
    for prediction in best_predictions:
        print('https://suchen.mobile.de/fahrzeuge/details.html?id=%s' % prediction['car_id'])
        print('listed with:  %d' % prediction['price']['actual'])
        print('worth around: %d' % prediction['price']['inferred'])
        print('difference:   %d' % prediction['price']['difference'])


def train_and_predict():
    cars = load_cars()

    df = pandas.DataFrame()
    df['id'] = pandas.Series([car['mobile']['ad_id'] for car in cars])
    df['price'] = pandas.Series([float(car['mobile']['dart']['ad']['price']) for car in cars])
    df['first_reg_year'] = pandas.Series([float(car['mobile']['dart']['adFirstRegYear']) for car in cars])
    df['mileage_in_km'] = pandas.Series([float(extract_number_from_string(car['mobile']['web']['technical']['mileage'])) for car in cars])
    df['car_age'] = pandas.Series([get_car_age_in_years(car) for car in cars])
    df['time_to_hu'] = pandas.Series([get_time_to_hu(car) for car in cars])
    df['ps'] = pandas.Series([get_ps(car) for car in cars])
    df['cc'] = pandas.Series([get_cc(car) for car in cars])
    df['prev_owners'] = pandas.Series([get_prev_owners(car) for car in cars])

    # add fuel, make it binary, drop fuel
    df['fuel'] = pandas.Series([car['mobile']['dart'].get('adSpecificsFuel', None) for car in cars])
    fuel_dummies = pandas.get_dummies(df['fuel'])
    df = pandas.concat([df, fuel_dummies], axis=1)
    df = df.drop('fuel', axis=1)

    # features
    features = set()
    for car in cars:
        if car['mobile']['web']['features'] is not None:
            for feature in car['mobile']['web']['features']:
                features.add(feature)

    for feature_name in features:
        values = []
        for car in cars:
            value = car['mobile']['web']['features'] is not None and feature_name in car['mobile']['web']['features']
            values.append(value)

        df[feature_name] = pandas.Series(values)

    # tech details as strings
    included_keys = ['interior', 'emissionClass', 'climatisation', 'countryVersion', 'damageCondition', 'export', 'transmission']
    technical = pandas.DataFrame([car['mobile']['web']['technical'] for car in cars])
    # print('excluded from technical: %s' % technical.columns)
    technical = technical[included_keys]

    # extract interior
    technical['interior_type'] = technical.apply(lambda row: extract_interior_type(row['interior']) if row['interior'] is not numpy.NaN else 'unknown', axis=1)
    technical['interior_color'] = technical.apply(lambda row: extract_interior_color(row['interior']) if row['interior'] is not numpy.NaN else 'unknown', axis=1)
    del technical['interior']

    technical_clean = pandas.concat([pandas.get_dummies(technical[col]) for col in technical], axis=1, keys=technical.columns)
    df = pandas.concat([df, technical_clean], axis=1)
    # print(df)

    # add data from dart
    values = []
    keys_from_dart = ['adSpecificsMake', 'adSpecificsMakeModel', 'adSpecificsModel']
    for key_from_dart in keys_from_dart:
        for car in cars:
            values.append(car['mobile']['dart'][key_from_dart])
    # todo get_dummies and append

    df = df.set_index('id')

    columns_training = df.columns[1:]
    # print('included: %s' % columns_training)
    excluded = [column for column in list(df.columns) if column not in columns_training]
    # print('excluded: %s' % excluded)

    X = pandas.DataFrame(df[columns_training], copy=True)
    y = pandas.DataFrame(df['price'], copy=True)

    # scaler = StandardScaler()
    # X = scaler.fit_transform(X.todense())

    # regr = SVR(kernel='linear')  # 0.80
    regr = DecisionTreeRegressor(criterion='mae', min_samples_leaf=100, min_impurity_split=1000)
    regr.fit(X, y)
    print("Coefficient of determination on training set:", regr.score(X, y))

    if isinstance(regr, BaseDecisionTree):
        generate_tree_visualization(regr, X.columns)

    predictions = generate_predictions(df, regr, columns_training)

    return predictions


def extract_interior_type(desc):
    return desc.split(', ')[0]


def extract_interior_color(desc):
    parts = desc.split(', ')
    if len(parts) > 1:
        return parts[1]
    return numpy.NaN


def load_cars():
    cars = []
    directory = os.getcwd() + '/cars'
    file_list = os.listdir(directory)
    for filename in file_list:
        with open(directory + '/' + filename) as file:
            json_string = file.read()
        car = json.loads(json_string)
        cars.append(car)
    return cars


def generate_predictions(df, regr, features_training):
    predictions = []
    for index, row in df.iterrows():
        car_row = numpy.asarray(row[features_training])

        price_actual = df.ix[index].price
        price_inferred = int(regr.predict(numpy.asarray([car_row])))

        difference = price_actual - price_inferred
        is_cheap = difference < 0

        prediction = {
            'price': {
                'actual': price_actual,
                'inferred': price_inferred,
                'difference': difference,
                'is_cheap': is_cheap,
            },
            'car_id': df.ix[index].name,
        }
        predictions.append(prediction)
    return predictions


def extract_price(car):
    price_raw = car['mobile']['web']['price'].replace('.', '')
    price = int(re.findall(r'\d+', price_raw)[0])
    return price


def extract_number_from_string(string):
    number_without_dots = string.replace('.', '')
    return int(re.findall(r'\d+', number_without_dots)[0])


def get_car_age_in_years(car):
    first_registration_raw = car['mobile']['web']['technical']['firstRegistration']
    first_registration = datetime.strptime(first_registration_raw, '%m/%Y')
    return (datetime.now() - first_registration).total_seconds() / (60 * 60 * 24 * 365)


def get_time_to_hu(car):
    time_to_hu = -5
    if 'hu' in car['mobile']['web']['technical']:
        hu_raw = car['mobile']['web']['technical']['hu']
        if hu_raw == 'Neu':
            time_to_hu = 0.0
        else:
            hu = datetime.strptime(hu_raw, '%m/%Y')
            time_to_hu = (hu - datetime.now()).total_seconds() / (60 * 60 * 24 * 12)

    return time_to_hu


def get_ps(car):
    power_in_ps = -1
    if 'power' in car['mobile']['web']['technical']:
        power_raw = car['mobile']['web']['technical']['power']
        power_in_ps = int(re.findall(r'\d+', power_raw)[1])
    return power_in_ps


def get_prev_owners(car):
    owners = -10
    if 'numberOfPreviousOwners' in car['mobile']['web']['technical']:
        owners = int(car['mobile']['web']['technical']['numberOfPreviousOwners'])
    return owners


def get_cc(car):
    if 'cubicCapacity' in car['mobile']['web']['technical']:
        cubic_capacity_raw = car['mobile']['web']['technical']['cubicCapacity'].replace('.', '')
        cubic_capacity = int(re.findall(r'\d+', cubic_capacity_raw)[0])
        return cubic_capacity
    return -1


def generate_tree_visualization(regr, feature_names):
    dot_filename = "tree.dot"
    gv_filename = 'tree.gv'

    with open(dot_filename, 'w') as f:
        sklearn.tree.export_graphviz(regr, out_file=f, feature_names=feature_names)
    with open(dot_filename, 'r') as f:
        src = Source(f.read())
        src.render(gv_filename)


if __name__ == '__main__':
    main()
