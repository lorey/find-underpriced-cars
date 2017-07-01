import json
import urllib
from datetime import datetime
from time import sleep

import logging
import requests
from bs4 import BeautifulSoup


def main():
    cars_data = perform_search()

    with open('cars.json', 'w') as file:
        file.write(json.dumps(cars_data, indent=2, ensure_ascii=False))


def perform_search():
    cars_data = []

    page = 1
    while True:
        search_url = 'https://suchen.mobile.de/fahrzeuge/search.html'
        parameters = {
            'ambitCountry': 'DE',
            'damageUnrepaired': 'NO_DAMAGE_UNREPAIRED',
            'isSearchRequest': 'true',
            'makeModelVariant1.makeId': 3500,  # bmw
            'makeModelVariant1.modelId': 59,  # 123?
            'scopeId': 'C',
            'usage': 'USED',
            'sortOption.sortBy': 'creationTime',
            'sortOption.sortOrder': 'DESCENDING',
            'pageNumber': page,
        }

        url = search_url + '?' + urllib.parse.urlencode(parameters)
        print(url)

        response = requests.get(url)
        html = response.content.decode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')

        car_results = soup.find_all('div', {'class': 'cBox-body--resultitem'})

        # return if finished
        if len(car_results) == 0:
            return cars_data

        for car_result in car_results:
            car_link = car_result.a
            if car_link.has_attr('data-ad-id'):
                ad_id = int(car_result.a['data-ad-id'])
                car_url = 'https://suchen.mobile.de/fahrzeuge/details.html?id=%d' % ad_id

                sleep(1)
                print(car_url)
                car_data = crawl_car(car_url)
                cars_data.append(car_data)
            else:
                logging.warning('no ad-id: %s' % car_result)

        page += 1


def crawl_car(url):
    # todo save html
    # todo save pictures

    response = requests.get(url)
    html = response.content.decode('utf-8')

    car = extract_data_from_car_page(html)
    return car


def extract_data_from_car_page(html):
    soup = BeautifulSoup(html, 'html.parser')

    # generic
    title = soup.find('h1', {'id': 'rbt-ad-title'}).get_text()
    price = soup.find('span', {'class': 'rbt-prime-price'}).get_text()

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
