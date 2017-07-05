import json
import os
import re
from datetime import datetime
from time import sleep

import numpy
import pandas
import requests
import sklearn
from graphviz import Source
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_selection import SelectKBest
from sklearn.feature_selection import mutual_info_regression
from sklearn.model_selection import cross_val_score
from sklearn.tree import DecisionTreeRegressor

SECONDS_TO_YEARS_FACTOR = 1 / (60 * 60 * 24 * 365)


def main():
    while True:
        cars = load_cars()
        predictions = train_and_predict(cars, cars)
        # print_best_predictions(predictions, n=100)
        sleep(300)


def print_best_predictions(predictions, n=100, ensure_online=False):
    best_predictions = sorted(predictions, key=lambda p: p['price']['difference'])
    shown = 0
    for prediction in best_predictions:
        sleep(0.5)
        url = 'https://suchen.mobile.de/fahrzeuge/details.html?id=%s' % prediction['car_id']
        if not ensure_online or requests.get(url).status_code == 200:
            shown += 1
            print(url)
            print('listed with:  %d' % prediction['price']['actual'])
            print('worth around: %d' % prediction['price']['inferred'])
            print('difference:   %d' % prediction['price']['difference'])

        if shown >= n:
            return


def train_and_predict(cars_training: list, cars_prediction: list):
    cars = cars_training + cars_prediction
    df = preprocess(cars)
    df_training = df[0:len(cars_training)]
    df_prediction = df[len(cars_training):]

    columns_training = df_training.columns[1:]
    # print('included: %s' % columns_training)
    excluded = [column for column in list(df_training.columns) if column not in columns_training]
    # print('excluded: %s' % excluded)

    X = df_training[columns_training]
    y = df_training['price']

    # scaler = StandardScaler()
    # X = scaler.fit_transform(X.todense())

    # regr = SVR(kernel='linear')  # 0.80
    regr = DecisionTreeRegressor(criterion='mae', min_samples_leaf=25, min_impurity_split=1000)
    regr.fit(X, y)

    scores = cross_val_score(regr, X, y, cv=5)
    print("R² on training set:", regr.score(X, y))
    print("Cross-validated Accuracy: %0.4f (+/- %0.4f)" % (scores.mean(), scores.std() * 2))

    # generate_tree_visualization(regr, X.columns)

    predictions = generate_predictions(df_prediction, regr, columns_training)

    return predictions


def preprocess(cars):
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
    # todo make repeatable
    df['fuel'] = pandas.Series([car['mobile']['dart'].get('adSpecificsFuel', None) for car in cars])
    fuel_dummies = pandas.get_dummies(df['fuel'])
    df = pandas.concat([df, fuel_dummies], axis=1)
    df = df.drop('fuel', axis=1)

    # features
    # todo make repeatable
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
    # todo make repeatable
    included_keys = ['interior', 'emissionClass', 'climatisation', 'countryVersion', 'damageCondition', 'export', 'transmission']
    technical = pandas.DataFrame([car['mobile']['web']['technical'] for car in cars])
    # print('excluded from technical: %s' % technical.columns)
    selected_keys = [column for column in included_keys if column in list(technical.columns.values)]  # avoid columns not seen in sample
    technical = technical[selected_keys]
    # extract interior
    technical['interior_type'] = technical.apply(lambda row: extract_interior_type(row['interior']) if row['interior'] is not numpy.NaN else 'unknown', axis=1)
    technical['interior_color'] = technical.apply(lambda row: extract_interior_color(row['interior']) if row['interior'] is not numpy.NaN else 'unknown', axis=1)
    del technical['interior']
    technical_clean = get_dummies_for_all(technical)
    df = pandas.concat([df, technical_clean], axis=1)

    # add data from dart
    values = []
    keys_from_dart = ['adSpecificsMake', 'adSpecificsMakeModel', 'adSpecificsModel']
    for car in cars:
        values.append([car['mobile']['dart'][key_from_dart] for key_from_dart in keys_from_dart])
    dart = pandas.DataFrame(values)
    df = pandas.concat([df, get_dummies_for_all(dart)], axis=1)

    # money_words = get_money_words(cars, df)
    # df = pandas.concat([df, money_words], axis=1)

    # key by id
    df = df.set_index('id')

    return df


def get_dummies_for_all(dataframe):
    return pandas.concat([pandas.get_dummies(dataframe[col]) for col in dataframe], axis=1, keys=dataframe.columns)


def get_money_words(cars, df, top=10):
    texts = []
    for car in cars:
        if car['mobile']['web']['description'] is not None:
            texts.append(car['mobile']['web']['description'].get('text', ''))
        else:
            texts.append('')

    tfidf_vectorizer = TfidfVectorizer(ngram_range=(2, 5), max_features=top*10, max_df=0.75)
    tfidfs = tfidf_vectorizer.fit_transform(texts)

    k_best = SelectKBest(mutual_info_regression, k=top)
    X_new = k_best.fit_transform(tfidfs, df.price)

    k_best_feature_indices = k_best.get_support(True).tolist()
    k_best_column_names = ['contains=' + tfidf_vectorizer.get_feature_names()[i] for i in k_best_feature_indices]
    return pandas.DataFrame(X_new.todense(), columns=k_best_column_names)


def extract_interior_type(desc):
    return desc.split(', ')[0]


def extract_interior_color(desc):
    parts = desc.split(', ')
    if len(parts) > 1:
        return parts[1]
    return numpy.NaN


def load_cars(sample=None):
    cars = []
    directory = os.getcwd() + '/cars'
    file_list = os.listdir(directory)
    for filename in file_list:
        with open(directory + '/' + filename) as file:
            json_string = file.read()
        car = json.loads(json_string)
        cars.append(car)

        if sample is not None and len(cars) >= sample:
            return cars
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
            'car_id': index,
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
    return (datetime.now() - first_registration).total_seconds() * SECONDS_TO_YEARS_FACTOR


def get_time_to_hu(car):
    time_to_hu = -5
    if 'hu' in car['mobile']['web']['technical']:
        hu_raw = car['mobile']['web']['technical']['hu']
        if hu_raw == 'Neu':
            time_to_hu = 2.0
        else:
            hu = datetime.strptime(hu_raw, '%m/%Y')
            time_to_hu = (hu - datetime.now()).total_seconds() * SECONDS_TO_YEARS_FACTOR

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
        sklearn.tree.export_graphviz(regr, out_file=f, feature_names=feature_names, filled=True, impurity=True, rotate=True, max_depth=4)
    with open(dot_filename, 'r') as f:
        src = Source(f.read())
        src.render(gv_filename)


if __name__ == '__main__':
    main()
