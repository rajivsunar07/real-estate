import requests
import pandas as pd
import numpy as np
import json
import os
from dotenv import load_dotenv, find_dotenv
from sqlalchemy import create_engine 
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text

class RealEstateETL:

    file_name = 'data/extracted-data.json'
    cleaned_file_name = 'data/transformed-data.csv'

    def extract(self):
        page = 1
        file_name = self.file_name
    
        if not os.path.isfile(file_name):
            with open(file_name, mode='w') as fw:
                fw.write(json.dumps({'last_page': 0, 'data': []}))

        with open(file_name, "r") as fr:
            file_data = json.load(fr)
            page = file_data['last_page'] + 1
            data = file_data['data']

        print('Scraping pages..')
        while True: 
            try:
                response = requests.get('https://www.nepalhomes.com/api/property/public/data?&sort=1&page={}&agency_id=&is_project=&find_district_id=&find_area_id=&find_property_category=5d660cb27682d03f547a6c4a'.format(str(page)))
                receieved_data = response.json()['data']

                if(len(receieved_data) == 0):
                    break

                data += receieved_data
                with open(file_name, 'w') as fw:
                    fw.write(json.dumps({'last_page': page, 'data': data}))

                page += 1

            except requests.exceptions.RequestException as e:
                print('Network error occured', e)
                break
            except KeyError as e:
                print('No more data', e)
                break
        print("Extraction completed")

    def transform(self):
        with open(self.file_name, 'r') as fr:
            data = json.load(fr)
            data = data['data']

        data = self.remove_unwanted_data(data)
    
        data = pd.json_normalize(data)
        
        data = self.clean_missing_data(data)
        data = self.clean_data(data)

        data.to_csv(self.cleaned_file_name, index=False)

        print('Transformation completed')
    
    def clean_data(self, data):
        data['total_area'] = data.apply(lambda x: self.change_area_value(x['total_area'], x['total_area_unit']), axis=1)
        data['total_area'] = data['total_area'].astype(np.float32)
        data.drop(columns=['total_area_unit'], inplace=True) # not  needed after conversion, all are converted to same unit

        data = self.clean_road_access_value(data)

        return data

    def remove_unwanted_data(self, data):
        # --- remove unnecessary data ---
        delete_keys = ['_id', 'slug_url', 'agency_id', 'media', 'prefix', 'is_featured','is_project', 'is_premium',
            'is_negotiable', 'project_property_type', 'basic', 'added_by', 'added_at']

        for d in data:

            # delete unwanted data
            for k in delete_keys:
                d.pop(k, None)
            
            ''' Clean individual data '''

            # price
            d['price'].pop('is_price_on_call', None)
            d['price'].pop('label', None)
            d['price'] = d['price']['value']

            # building
            for k in d['building']:
                d[k] = d['building'][k]
            d.pop('building', None)

            # address
            for k in d['address']:
                try: 
                    value = str(d['address'][k]['name'])
                except Exception as e:
                    value = ''
                d[str(k).split('_', 1)[0]] = value
            d.pop('address', None) 

            # location_property
            for k in d['location_property']:
                try:
                    d[k] = d['location_property'][k]['title']
                except:
                    d[k] = d['location_property'][k]
            d.pop('location_property', None)
            
            # bedroom and bathroom
            bedroom = d['no_of']['bedroom']
            bathroom = d['no_of']['bathroom']
            d.pop('no_of')
            d['bedroom'] = bedroom
            d['bathroom'] = bathroom
        
        return data

    def clean_missing_data(self, df):

        # drop missing values
        df.dropna(axis='index', how='all', inplace=True)
        df.dropna(axis = 'index', how='all', subset=['price'], inplace=True)

        df['built_year'].replace(np.nan, 0, inplace=True)
        df['built_year'] = df['built_year'].astype(np.int16)
        df['built_month'] = df['built_month'].apply(lambda x: 12 if x > 12 else x).astype(np.int16)

        df['total_floor'].replace([np.nan, 0.0], 1.0, inplace=True)

        df['state'].replace(np.nan, 'Missing', inplace=True)
        df['district'].replace(np.nan, 'Missing', inplace=True)
        df['city'].replace(np.nan, 'Missing', inplace=True)
        df['area'].replace(np.nan, 'Missing', inplace=True)

        df['total_area'].replace(np.nan, '0', inplace=True)
        df['total_area'].replace('', '0', inplace=True)
        df['property_face'].replace([np.nan, '-'], 'Missing', inplace=True)

        df['bedroom'].replace(np.nan, 2, inplace=True)
        df['bedroom'] = df['bedroom'].astype(np.int16)

        df['bathroom'].replace(np.nan, 2, inplace=True)
        df['bathroom'] = df['bathroom'].astype(np.int16)

        df['road_access_value'].replace(np.nan, '0', inplace=True)
        df['road_access_value'].replace('', '0', inplace=True)

        return df

    def change_area_value(self, value, unit):
        ''' 
            The area value of a property is written in several different units.
            All are converted into the same unit: Square feet.
            The rates for conversion are received from: https://www.nepalhomes.com/unit-converter 
        '''
        if '' in value:
            return 0

        if 'str' not in str(type(value)):
            return value

        if unit == 'Sq. Feet':
            if '-' in value:
                count = value.count('-')
                values = value.split('-', count)
                total = 0.0
                for i in values:
                    total += float(i) 
                return total
            return value

        if unit == 'Sq. Meter':
            if '-' in value:
                count = value.count('-')
                values = value.split('-', count)
                total = 0.0
                for i in values:
                    total += float(i) * 10.764
                return total
            return float(value) * 10.764

        value_list = value.split('-', 3)
        value_list = np.array(value_list, dtype=float)

        conversion_rates = [0, 0, 0, 0]

        if unit == 'Ropani-Aana-Paisa-Daam':
            conversion_rates = [ 5476, 342.25, 85.56, 21.39 ]
        elif unit == 'Bigha-Kattha-Dhur-Haat':
            value_list[3] = value_list[3] ** 2
            conversion_rates = [ 72900, 3645, 182.25 , 2.25 ]

        total = 0.0 
        for i in range(0, len(value_list)):
            total += value_list[i] * conversion_rates[i]

        return total

    def change_road_access_value(self, x):
        if ('-' in x or '/' in x )and '--' not in x:
            if '-' in x:
                x = (int(x.split('-')[0]) + int(x.split('-')[1]))/2
            else:
                x = (int(x.split('/')[0]) + int(x.split('/')[1]))/2

            return str(x)
        elif '+' in x and len(x) == 3:
            return x[0:2]
        elif '--' in x and len(x) == 6:
            return str((int(x[0:2]) + int(x[4:]))/2)
        elif '&' in x and len(x) == 7:
            return str((int(x[0:2]) + int(x[5:]))/2)

        return x

    def clean_road_access_value(self, df):
        df = df[df['road_access_value'].str.contains('|'.join(['to', 'from', 'has'])) == False]

        df['road_access_value'] = df['road_access_value'].apply(self.change_road_access_value)
        df['road_access_value'] = df['road_access_value'].astype(np.float64)  

        # converting feet to meter
        # 1 feet = 0.3048 meter

        df['road_access_value'] = df.apply(lambda x: x['road_access_value'] if x['road_access_length_unit'] == 'Meter' else x['road_access_value'] * 0.3048, axis=1)
        df['road_access_road_type'].replace(np.nan, 'Missing', inplace=True)

        # no longer needed
        df.drop(columns=['road_access_length_unit'], inplace=True)

        return df

    def load(self):
        data_df = pd.read_csv(self.cleaned_file_name)
       
        load_dotenv(find_dotenv())
        engine = create_engine(
                'postgresql://{username}:{password}@{host}:{port}/{database}'.format(
                    username = os.getenv('USERNAME'),
                    password = os.getenv('PASSWORD'),
                    host = os.getenv('HOST'),
                    port = os.getenv('PORT'),
                    database = os.getenv('DATABASE'),
                )
            )

        data_df.to_sql(os.getenv('TABLE'), engine)


if __name__ == '__main__':
    etl = RealEstateETL()
    # etl.extract()
    # etl.transform()
    etl.load()