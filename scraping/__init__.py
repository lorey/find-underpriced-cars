import json
import logging
import os
import urllib
from datetime import datetime
from time import sleep

import requests
from bs4 import BeautifulSoup

import storage
from scraping import extraction

RETRIES_ON_FAILURE = 3

USED_CARS = {
    'ambitCountry': 'DE',
    'damageUnrepaired': 'NO_DAMAGE_UNREPAIRED',
    'isSearchRequest': 'true',
    'scopeId': 'C',
     'usage': 'USED',
    'sortOption.sortBy': 'creationTime',
    'sortOption.sortOrder': 'DESCENDING',
    'maxMileage': 200000,
    'maxPrice': 25000,
}

USED_PRIVATE_PREMIUM_CARS = {
    'adLimitation': 'ONLY_FSBO_ADS',  # private
    'climatisation': 'MANUAL_OR_AUTOMATIC_CLIMATISATION',
    'ambitCountry': 'DE',
    'damageUnrepaired': 'NO_DAMAGE_UNREPAIRED',
    'isSearchRequest': 'true',
    'makeModelVariant1.makeId': 3500,  # bmw
    'makeModelVariant2.makeId': 1900,  # audi?
    'makeModelVariant3.makeId': 17200,  # mercedes?
    'scopeId': 'C',
    'usage': 'USED',
    'sortOption.sortBy': 'creationTime',
    'sortOption.sortOrder': 'DESCENDING',
    'maxMileage': 200000,
    'maxPrice': 25000,
}

PARAMETERS_BMW_ONE_SERIES = {
    'ambitCountry': 'DE',
    'damageUnrepaired': 'NO_DAMAGE_UNREPAIRED',
    'isSearchRequest': 'true',
    'makeModelVariant1.makeId': 3500,  # bmw
    'makeModelVariant1.modelGroupId': 20,  # 1 series
    'makeModelVariant1.modelId': '73%2C2%2C3%2C4%2C59%2C61%2C5%2C58%2C87',  # combination of models?
    'scopeId': 'C',
    'usage': 'USED',
    'sortOption.sortBy': 'creationTime',
    'sortOption.sortOrder': 'DESCENDING',
    'maxPrice': 10000,
}


def run():
    while True:
        scrape_search(parameters=USED_CARS)

        # fuck sleep
        # print('going to sleep')
        # sleep(60 * 5)


def scrape_search(parameters, pages=50):
    if pages > 50:
        logging.warning('pages bigger than 50 do not yield new results')

    cars_data = []

    for page in range(1, 1 + pages):
        search_url = 'https://suchen.mobile.de/fahrzeuge/search.html'
        parameters['pageNumber'] = page
        url = search_url + '?' + urllib.parse.urlencode(parameters)
        print(url)

        session = requests.session()
        response = session.get(url)
        html = response.content.decode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')

        car_results = soup.find_all('div', {'class': 'cBox-body--resultitem'})

        # return if finished early
        if len(car_results) == 0:
            return cars_data

        sleep(3)
        for car_result in car_results:
            car_link = car_result.a
            if car_link.has_attr('data-ad-id'):
                ad_id = int(car_result.a['data-ad-id'])
                car_data = scrape_ad(ad_id, session)

                if car_data is not None:
                    cars_data.append(car_data)
            else:
                logging.warning('no ad-id: %s' % car_result)

    return cars_data


def scrape_ad(ad_id, session=None):
    if session is None:
        session = requests.session()

    # todo save pictures

    url = 'https://suchen.mobile.de/fahrzeuge/details.html?id=%d' % ad_id
    print(url)

    response = session.get(url)
    if response.status_code != 200:
        logging.warning('status code is %d for %s' % (response.status_code, url))
        return None

    html = response.content.decode('utf-8')
    storage.save_ad(ad_id, html)

    extractor = extraction.AdExtractor(html)
    car = extractor.get_data()

    if car is None:
        return None

    # add url
    car['url'] = url

    return car


if __name__ == '__main__':
    run()
