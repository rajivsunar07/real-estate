from flask import Flask, render_template, jsonify, request
from sqlalchemy import create_engine
import pandas as pd
from dotenv import load_dotenv, find_dotenv
import os
import json

# load_dotenv(find_dotenv())
app = Flask(__name__)

# engine = create_engine(
#             'postgresql://{username}:{password}@{host}:{port}/{database}?sslmode=require'.format(
#                 username = os.getenv('USERNAME'),
#                 password = os.getenv('PASSWORD'),
#                 host = os.getenv('HOST'),
#                 port = os.getenv('PORT'),
#                 database = os.getenv('DATABASE'),
#             )
#         )

# Engine for the database connection
engine = create_engine(
            '{databaseuri}?sslmode=require'.format(
                databaseuri = os.getenv('DATABASE_URI'),
            )
        )

data_df = pd.read_sql_table(os.getenv('TABLE'), engine)
data_df.drop(columns=['index'], inplace=True)

@app.route('/', methods=['GET'])
def index(district=None):
    args = dict(request.args)
   
    districts = list(data_df['district'].unique())
    try:
        districts.remove('Missing')
    except:
        pass

    cities = []

    if 'city' in args or 'district' in args:
        cities = list(data_df[data_df['district'] == args['district']]['city'].unique())
        if 'Missing' in cities:
            cities.remove('Missing')
        get_data_from = list(args.keys())[-1]
        data = data_df[data_df[get_data_from] == args[get_data_from]].copy()

        if 'city' in args:
            grp = data.groupby(['area'])
        elif 'district' in args:
            grp = data.groupby(['city'])
    else:
        grp = data_df.groupby(['district'])
    
    grp_sum = grp['price'].mean()

    try: 
        grp_sum.drop(index='Missing', inplace=True)
    except:
        pass

    data = grp_sum.to_dict()
    labels = list(data.keys())
    data = list(data.values())


    return render_template(
        'base.html',
        districts=districts, 
        cities=cities, 
        labels=labels, 
        data=data, 
        args=args
        )

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000)) 
    app.run(debug=False, host='0.0.0.0', port=port)