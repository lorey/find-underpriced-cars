import numpy
import pandas
from sklearn.model_selection import cross_val_score
from sklearn.tree import DecisionTreeRegressor

import prediction


class Predictor(object):
    regressor = None
    selected_columns = None

    def predict(self, cars):
        df = prediction.preprocess(cars)
        df = self.prepare(df)

        # use trained columns and adapt it to current data frame
        df_adapted = pandas.DataFrame()
        for column in self.columns:
            if column in df:
                df_adapted[column] = df[column]
            else:
                df_adapted[column] = pandas.Series([0] * len(df))

            if df_adapted[column].isnull().any():
                print(column + ' with NaN')
                df_adapted[column] = df_adapted[column].fillna(0)

        predictions = []
        for index, row in df_adapted.iterrows():
            car_row = numpy.asarray(row[self.columns])

            price_actual = df.ix[index].price
            price_inferred = int(self.regressor.predict(numpy.asarray([car_row])))

            difference = price_actual - price_inferred
            is_cheap = difference < 0

            price_prediction = {
                'price': {
                    'actual': price_actual,
                    'inferred': price_inferred,
                    'difference': difference,
                    'is_cheap': is_cheap,
                },
                'car_id': index,
            }
            predictions.append(price_prediction)
        return predictions

    def train(self, cars):
        df = prediction.preprocess(cars)
        df_clean = self.prepare(df)

        self.columns = list(df_clean.columns[1:])
        # print('included: %s' % columns_training)
        excluded = [column for column in list(df_clean.columns) if column not in self.columns]
        # print('excluded: %s' % excluded)

        X = df_clean[self.columns]
        y = df_clean['price']

        print('training')
        self.regressor = DecisionTreeRegressor(criterion='mae', min_samples_leaf=0.01, min_impurity_split=1000)
        self.regressor.fit(X, y)

        print("R² on training set:", self.regressor.score(X, y))
        scores = cross_val_score(self.regressor, X, y)
        print("Cross-validated Accuracy: %0.4f (+/- %0.4f)" % (scores.mean(), scores.std() * 2))

        # generate_tree_visualization(regr, X.columns)

    def prepare(self, df):
        df_clean = pandas.DataFrame()
        for column in list(df.columns.values):
            print(column)
            if df[column].dtype not in [numpy.float64, numpy.int]:
                # create dummies and concat
                dummies = pandas.get_dummies(df[column], prefix=column, dummy_na=True)
                df_clean = pandas.concat([df_clean, dummies], axis=1)
                print('  getting dummies (%d columns)' % len(list(dummies.columns)))
            else:
                print('  appending')
                # copy column
                if df[column].isnull().any():
                    # nan_replacement = nan_replacements[column]
                    df_clean[column] = df[column].fillna(df[column].mean())  # replace with mean
                else:
                    df_clean[column] = df[column]

            # remove processed column to save memory
            del df[column]
        return df_clean
