import json
import logging
from datetime import datetime

from bs4 import BeautifulSoup


class AdExtractor(object):
    html = None

    def __init__(self, html):
        self.html = html

    def get_data(self):
        car = self.scrape_data_from_ad_page()

        # dart data
        car['mobile']['dart'] = self.extract_dart_data()

        if car['mobile']['dart'] is None:
            logging.warning('no dart data')
            return None

        if 'price' not in car['mobile']['dart']['ad']:
            logging.warning('price is not set')
            return None

        return car

    def extract_dart_data(self):
        html = self.html

        # ad data start and end strings
        search_start = 'mobile.dart.setAdData('
        search_end = ');\n'

        # find start and end
        search_start_index = html.find(search_start)
        if search_start_index == -1:
            logging.warning('ad data start not found')
            return None  # empty dict as default value

        start_index = search_start_index + len(search_start)
        end_index = html.find(search_end, start_index)

        # try to extract json
        json_string = html[start_index:end_index]
        try:
            json_data = json.loads(json_string)
        except ValueError as ve:
            # most likely the json contains the end indicator
            raise RuntimeError('malformed json: %s' % json_string) from ve
        return json_data

    def scrape_data_from_ad_page(self):
        soup = BeautifulSoup(self.html, 'html.parser')

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
            description_box = soup.find('div', {'class': 'cBox-body--vehicledescription'}).find('div', {
                'class': 'description'})
            description_html = str(description_box)
            description_text = description_box.get_text(separator='\n')
            description = {
                'html': description_html,
                'text': description_text,
            }

        car = {
            'crawler': {
                'created_at': str(datetime.now()),
                'updated_at': str(datetime.now()),
                'last_seen_at': str(datetime.now()),
            },
            'mobile': {
                'ad_id': ad_id,
                'web': {
                    'title': title,
                    'price': price,
                    'technical': technical_data,
                    'features': features,
                    'description': description,
                    'seller': seller,
                }
            },
        }
        return car
