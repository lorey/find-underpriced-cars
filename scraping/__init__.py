import logging
import urllib
from time import sleep

import requests
from bs4 import BeautifulSoup

import storage
from scraping import extraction

LIMIT_MILEAGE = 200000

LIMIT_PRICE = 25000

RETRIES_ON_FAILURE = 3

USED_CARS = {
    'ambitCountry': 'DE',
    'damageUnrepaired': 'NO_DAMAGE_UNREPAIRED',
    'isSearchRequest': 'true',
    'scopeId': 'C',
     'usage': 'USED',
    'sortOption.sortBy': 'creationTime',
    'sortOption.sortOrder': 'DESCENDING',
    'maxMileage': LIMIT_MILEAGE,
    'maxPrice': LIMIT_PRICE,
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
    'maxMileage': LIMIT_MILEAGE,
    'maxPrice': LIMIT_PRICE,
}

PARAMETERS_TO_SCRAPE = [
    USED_CARS,
    USED_PRIVATE_PREMIUM_CARS,
]


def run():
    while True:
        for parameters in PARAMETERS_TO_SCRAPE:
            scrape_search(parameters)
        sleep(60)
        # fuck sleep
        # print('going to sleep')
        # sleep(60 * 5)


def scrape_search(parameters, pages=50):
    if pages > 50:
        logging.warning('pages bigger than 50 do not yield new results')

    cars_data = []
    for page in range(1, 1 + pages):
        cars_in_results = scrape_search_results(page, parameters)
        cars_data.extend(cars_in_results)

    return cars_data


def scrape_search_results(page, parameters):
    search_url = 'https://suchen.mobile.de/fahrzeuge/search.html'
    parameters['pageNumber'] = page
    url = search_url + '?' + urllib.parse.urlencode(parameters)
    print(url)

    sleep(3)
    session = requests.session()
    response = session.get(url)

    html = response.content.decode('utf-8')
    soup = BeautifulSoup(html, 'html.parser')

    car_results = soup.find_all('div', {'class': 'cBox-body--resultitem'})

    cars_data = []
    for car_result in car_results:
        car_link = car_result.a
        if car_link.has_attr('data-ad-id'):
            ad_id = int(car_result.a['data-ad-id'])
            print(get_ad_url(ad_id))

            car_data = None

            # fetch from storage
            if storage.is_stored(ad_id):
                print('  found in storage')
                html = storage.load_ad(ad_id)
                car_data = extract_data_from_ad(html, get_ad_url(ad_id))

            # if storage is corrupt or non-existent
            if car_data is None:
                print('  scraping')
                sleep(3)  # sleep to keep footprint low
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

    url = get_ad_url(ad_id)
    response = session.get(url)
    if response.status_code != 200:
        logging.warning('status code is %d for %s' % (response.status_code, url))
        return None

    html = response.content.decode('utf-8')
    storage.save_ad(ad_id, html)

    return extract_data_from_ad(html, url)


def get_ad_url(ad_id):
    url = 'https://suchen.mobile.de/fahrzeuge/details.html?id=%d' % ad_id
    return url


def extract_data_from_ad(html, url):
    extractor = extraction.AdExtractor(html)
    car = extractor.get_data()
    if car is None:
        return None

    # add url
    car['url'] = url
    return car


if __name__ == '__main__':
    run()
