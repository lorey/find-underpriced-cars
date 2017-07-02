import json
import logging
import os
import urllib
from datetime import datetime
from time import sleep

import requests
from bs4 import BeautifulSoup


def main():
    cars_data = perform_search()

    with open('cars.json', 'w') as file:
        file.write(json.dumps(cars_data, indent=2, ensure_ascii=False))


def perform_search():
    cars_data = []

    for page in range(1, 250):
        search_url = 'https://suchen.mobile.de/fahrzeuge/search.html'
        parameters = {
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
            'pageNumber': page,
            'maxPrice': 10000,
        }

        url = search_url + '?' + urllib.parse.urlencode(parameters)
        print(url)

        response = requests.get(url)
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

                cache_path = get_cache_path_for_ad_id(ad_id)
                if os.path.isfile(cache_path):
                    # read from file
                    with open(cache_path, 'r') as file:
                        content = file.read()
                    car_data = json.loads(content)
                else:
                    # scrape
                    car_url = 'https://suchen.mobile.de/fahrzeuge/details.html?id=%d' % ad_id

                    sleep(1)
                    print(car_url)

                    car_data = crawl_car(car_url)

                cars_data.append(car_data)
            else:
                logging.warning('no ad-id: %s' % car_result)

    return cars_data


def crawl_car(url):
    # todo save html
    # todo save pictures

    response = requests.get(url)
    html = response.content.decode('utf-8')

    car = extract_data_from_car_page(html)
    car['url'] = url

    filename = get_cache_path_for_ad_id(car['mobile']['ad_id'])
    with open(filename, 'w') as file:
        file.write(json.dumps(car, ensure_ascii=False, indent=4))

    return car


def get_cache_path_for_ad_id(ad_id):
    return 'cars/%d.json' % ad_id


def extract_data_from_car_page(html):
    soup = BeautifulSoup(html, 'html.parser')

    # generic
    title = soup.find('h1', {'id': 'rbt-ad-title'}).get_text()
    price = soup.find('span', {'class': 'rbt-prime-price'}).get_text()

    ad_id = int(soup.find('div', {'class': 'parking-block'})['data-parking'])

    # seller
    seller_address = soup.find('p', {'id': 'rbt-seller-address'}).get_text(separator=' ')

    seller_phone = None
    if soup.find('span', {'id': 'rbt-seller-phone'}):
        seller_phone = soup.find('span', {'id': 'rbt-seller-phone'}).get_text().replace('Tel.: ', '')

    seller = {
        'address': seller_address,
        'phone': seller_phone,
    }

    # technical data
    technical_data = {}
    technical_box_tag = soup.find('div', {'id': 'rbt-td-box'})
    rows = technical_box_tag.find_all('div', {'class': 'g-row'})
    for row in rows:
        # print(row)
        for child in row.children:
            id = child['id']
            key = id.replace('-l', '').replace('-v', '').replace('rbt-', '')
            if '-v' in id:
                technical_data[key] = child.get_text()

    # features
    features = None
    if soup.find('div', {'id': 'rbt-features'}):
        features_box_tag = soup.find('div', {'id': 'rbt-features'}).find('div', {'class': 'g-row'})
        features = [column.get_text() for column in features_box_tag.children]

    # description
    description = None
    if soup.find('div', {'class': 'cBox-body--vehicledescription'}):
        description_box = soup.find('div', {'class': 'cBox-body--vehicledescription'}).find('div', {'class': 'description'})
        description_html = str(description_box)
        description_text = description_box.get_text(separator='\n')
        description = {
            'html': description_html,
            'text': description_text,
        }

    car = {
        'crawler': {
            'seen_at': str(datetime.now()),
        },
        'mobile': {
            'ad_id': ad_id,
            'title': title,
            'price': price,
            'technical': technical_data,
            'features': features,
            'description': description,
            'seller': seller,
        },
    }
    return car


if __name__ == '__main__':
    main()
