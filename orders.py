
from woocommerce import API
# from apps.home import blueprint
from flask import render_template, request, jsonify
import requests
from datetime import datetime, timedelta
from flask_login import login_required
from jinja2 import TemplateNotFound
from dateutil import parser
import os
import json
import concurrent.futures
import re
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
# from tenacity import retry, stop_after_attempt, wait_fixed

from apps.config import API_GENERATOR
wcapi = API(
    url="https://meetandgreetheathrow.com",
    consumer_key="ck_bcc01c92ff106c98d303ba7b0bf4775bfd4911da",
    consumer_secret="cs_1bb7b3da942206be797b0757ca69ecbd10a3cab2",
    version="wc/v3"
)





def index():
    table_headers = [
        '',
        'id',
        'Flight Date & Time',
        'Service',
        'Airport',
        'flight#',
        'Lead Name',
        'No. pax',
        'No. bags',
        'Status',
      
    ]
    today_date = datetime.now().strftime(format='%A %d %B %Y')
    tomorrow_date = (datetime.now() + timedelta(days=1))
    tomorrow_date=tomorrow_date.strftime(format='%A %d %B %Y')
    return render_template('home/index.html', table_headers=table_headers,tomorrow_date=tomorrow_date,today_date=today_date,segment='index', API_GENERATOR=len(API_GENERATOR))

def categorize_orders(orders):
    if not orders:
        return [], [], [], []  # Return empty lists for all categories

    previous_day_orders = []
    today_orders = []
    tomorrow_orders = []
    upcoming_orders = []

    # Get today's date without the time component
    today_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    # Sort orders based on flight_date_time
    orders.sort(key=lambda x: x.get('flight_date_time'))

    for order in orders:
        if 'flight_date_time' in order:
            flight_date_time_str =order.get('flight_date_time')
            flight_datetime = datetime.strptime(str(flight_date_time_str), '%Y-%m-%d %H:%M:%S')
            flight_date = flight_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
            if flight_date < today_date:
                previous_day_orders.append(order)
            elif flight_date == today_date:
                today_orders.append(order)
            elif flight_date == today_date + timedelta(days=1):
                tomorrow_orders.append(order)
            elif flight_date > today_date + timedelta(days=1):
                upcoming_orders.append(order)

    return previous_day_orders, today_orders, tomorrow_orders, upcoming_orders , orders



def fetch_orders_page(wcapi, page, per_page):
    response = wcapi.get("orders", params={"per_page": per_page, "page": page}).json()
    return response

# @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
def get_all_orders(wcapi):
    per_page = 20
    all_orders = []
    max_workers = 5  # Adjust based on your needs and API rate limits

    # Fetch the first page to get the total number of orders
    first_page_response = wcapi.get("orders", params={"per_page": per_page, "page": 1}).json()
    all_orders.extend(first_page_response)
    
    total_orders = wcapi.get("orders", params={"per_page": 1, "page": 1}).headers.get('X-WP-Total')
    total_orders = int(total_orders) if total_orders else len(first_page_response)
    total_pages = (total_orders // per_page) + 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_orders_page, wcapi, page, per_page) for page in range(2, total_pages + 1)]
        for future in concurrent.futures.as_completed(futures):
            all_orders.extend(future.result())
        
    logging.info(f"Finished fetching all orders. Total orders collected: {len(all_orders)}")
    logging.info(f"Finished fetching all orders. Total orders collected: {all_orders}")

    return all_orders



def get_metadata_by_order_id(orders, order_id, meta_key):
    for order in orders:
        if order['id'] == order_id:
            for item in order['line_items']:
                for meta in item['meta_data']:
                    if meta['key'] == meta_key:
                        return meta['value']
    return None
def get_luggage_assistance_by_order_id(orders, order_id, meta_key):
    for order in orders:
        if order['id'] == order_id:
            for item in order['line_items']:
                for meta in item['meta_data']:
                    if meta['key'] == meta_key:
                        luggage_assistance_entries = [entry for entry in item['meta_data'] if entry["display_key"] == "Luggage Assistance"]
                        if len(luggage_assistance_entries) > 1:
                            second_luggage_assistance = luggage_assistance_entries[1]
                            # print("////////////////////////////////// zero")
                            # print(luggage_assistance_entries[0])
                            # print("////////////////////////////////// Order ID" + str(order_id))
                            # print(second_luggage_assistance['value'])
                            return second_luggage_assistance['value']
                        else:
                            #print("////////////////////////////////// Order ID" + str(order_id))
                            # print(luggage_assistance_entries)
                            return ' '
    

def has_multiple_products(order):
    return len(order['line_items']) > 1

def getextrainfo(metadata):
    extradata = ''
    for meta_item in metadata:
        if meta_item.get('key') not in [ 'Flight Date Time', 'Arrival Flight Date &amp; Time' , '_WCPA_order_meta_data' ,'Lead Name', 'Select Airport', 'Flight Number', 'Luggage Assistance', 'Adults' , 'Children']:
                            extradata+='<div class="custom-cell"><strong>'+ str(meta_item.get('key')) +':</strong> ' + str(meta_item.get('value')) + '</div>'
    return extradata

@blueprint.route('/api/orders')
def get_orders():
  
    not_parsed = []
    response= None
    exceptionhappened = False
   
    response=get_all_orders(wcapi)
 
    # response = wcapi.get("orders", params={"per_page": 20}).json()
    if response:
        order_data = []
        tmpOrder={}
        notParsedTmpOrder = {}
        orders = response
        leadname = ''              
        airport = ''
        flightnumber = ''
        adults = ''
        children = ''
        flightdateantime = ''
        second_luggage_assistance =''
        extrainfo= ''
        extradata = ''
        parsed_date= ''
        for order in orders:
            
     

            # Construct the URL to view the order in WordPress
            #https://meetandgreetheathrow.com/wp-admin/post.php?post=1812&action=edit
            wordpress_url = wcapi.url+"/wp-admin/post.php?post="+str(order["id"])+"&action=edit"
            # wordpress_url = wcapi.url("orders/{}".format(order["id"]))
            # print("Order wordpress URL -------------------------------------------------")
            # print(str(wordpress_url))  
            
            line_items = order['line_items']
            if has_multiple_products(order):
              
                # print("Order has multiple products")
                # print("Order Id " + str(order["id"]))
                for bookings in order['line_items']:
                    meta_data = bookings.get('meta_data', [])
                    for meta_item in meta_data:
                        if meta_item.get('key') != '_WCPA_order_meta_data':
                            # print(meta_item.get('value'))
                            if meta_item.get('key') == 'Flight Date Time' or meta_item.get('key') == 'Arrival Flight Date &amp; Time' or meta_item.get('key') == 'Arrival Date &amp; Time' or meta_item.get('key') == 'Flight Arrival Date &amp; Time':
                                # Extract and return the 'value'
                                flight_date_time = meta_item.get('value')
                                # if flight_date_time and flight_date_time not in [ 'June 23, 2024 16.05', 'June 13, 2024 12.35', 'May 1, 2024 15:55 pm','April 30, 2024 20:35 pm','Apr25th10-20am','Apr25th10-20am','April 8, 2024 15:55 pm']:
                                i=0
                                for item in meta_data:
                                    # if meta_data[i].get('key') != '_WCPA_order_meta_data':
                                        if meta_data[i].get('key') == 'Lead Name':
                                            leadname = meta_data[i].get('value')
                                        elif meta_data[i].get('key') == 'Flight Date Time' or meta_data[i].get('key') == 'Arrival Flight Date &amp; Time':
                                            flightdateantime = meta_data[i].get('value')
                                        elif meta_data[i].get('key') == 'Select Airport':
                                            airport = meta_data[i].get('value')
                                        elif meta_data[i].get('key') == 'Flight Number':
                                            flightnumber = meta_data[i].get('value')
                                        elif meta_data[i].get('key') == 'Adults':
                                            adults = meta_data[i].get('value')
                                        elif meta_data[i].get('key') == 'Children':
                                            children = meta_data[i].get('value')
                                        elif meta_data[i].get('key') == 'Luggage Assistance':
                                            luggage_assistance_entries = [entry for entry in meta_data if entry["display_key"] == "Luggage Assistance"]
                                            if len(luggage_assistance_entries) > 1:
                                                second_luggage_assistance = luggage_assistance_entries[1]['value']
                                                
                                        elif meta_data[i].get('key') != '_WCPA_order_meta_data':
                                            extrainfo += '<div class="custom-cell"><strong>'+ str(meta_data[i].get('key')) +':</strong> ' + str(meta_data[i].get('value')) + '</div>'
                                            # print(extrainfo)
                                            # print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                                        # print("Meta ID " + str(i))
                                        # print(meta_data[i].get('key'))
                                        # print(meta_data[i].get('value'))
                                        i+=1
                                
                                
                                
        
            
                            
                               
                                
                                if flight_date_time:
                                    # print("Shahzaib " + str(order["id"]))
                                    adults= str(get_metadata_by_order_id(orders,order["id"], 'Adults'))
                                    children=str(get_metadata_by_order_id(orders,order["id"], 'Children'))
                                    try:

                                        parsed_date = parser.parse(flightdateantime)
                                        # parsed_date, _ = parser.parse(flight_date_time, fuzzy_with_tokens=True)
                                        tmpOrder = {
                                            'id': order["id"],
                                            'status': order["status"],
                                            'flight_date_time': parsed_date.strptime(str(parsed_date), '%Y-%m-%d %H:%M:%S'),
                                            'servicename': bookings.get('name'),
                                            'flight_date_time_raw': flight_date_time,
                                            'leadname' : leadname,
                                            'airport' : airport,   
                                            'flightnumber': flightnumber,
                                            'no_of_pax_with_price': str(get_metadata_by_order_id(orders,order["id"], 'Adults')) + " + "+str(get_metadata_by_order_id(orders,order["id"], 'Children')) ,
                                            'no_of_bags_with_price': get_luggage_assistance_by_order_id(orders,order["id"], 'Luggage Assistance'),
                                            'no_of_pax':re.sub(r'\([^\)]+\)', '', str(adults)).strip() + " + "+ re.sub(r'\([^\)]+\)', '', str(children)).strip(),
                                            'no_of_bags': re.sub(r'\s*\(£?\d+(\.\d{2})?\)', '', str(second_luggage_assistance)).strip() ,
                                            'needspayment': ("Payment Not Needed" if not order["needs_payment"] and order["status"] == "cancelled" 
                 else "Paid" if not order["needs_payment"] 
                 else "Not Paid"),
                                            'extrainfo' : extrainfo,
                                            "order_url": wordpress_url
                                            }
                                        # 'no_of_pax': str(get_metadata_by_order_id(orders,order["id"], 'Select Airport')) +" "+str(get_metadata_by_order_id(orders,order["id"], 'Select Airport')) ,
                                    except ValueError:
                                        exceptionhappened = True
                                        # print("Shahzaib" + str(meta_data[4].get('value')))
                                        notParsedTmpOrder = {
                                            'id': order["id"],
                                            'status': order["status"],
                                            'flight_date_time': flight_date_time,
                                            'servicename': bookings.get('name'),
                                            'flight_date_time_raw': flight_date_time,
                                            'leadname' : leadname,
                                            'airport' : airport,   
                                            'flightnumber': flightnumber,
                                            'no_of_pax_with_price': str(get_metadata_by_order_id(orders,order["id"], 'Adults')) + " + "+str(get_metadata_by_order_id(orders,order["id"], 'Children')) ,
                                            'no_of_bags_with_price': get_luggage_assistance_by_order_id(orders,order["id"], 'Luggage Assistance'),
                                            'no_of_pax':re.sub(r'\([^\)]+\)', '', str(adults)).strip() + " + "+ re.sub(r'\([^\)]+\)', '', str(children)).strip(),
                                            'no_of_bags': re.sub(r'\s*\(£?\d+(\.\d{2})?\)', '', str(second_luggage_assistance)).strip() ,
                                            'needspayment': ("Payment Not Needed" if not order["needs_payment"] and order["status"] == "cancelled" 
                 else "Paid" if not order["needs_payment"] 
                 else "Not Paid"),
                                            'extrainfo' : extrainfo,
                                            "order_url": wordpress_url
                                            }
                    # print("//////////////////////////////")
                    leadname = ''              
                    airport = ''
                    flightnumber = ''
                    adults = ''
                    children = ''
                    flightdateantime = ''
                    second_luggage_assistance = ''
                    extrainfo = ''
                    if tmpOrder and tmpOrder not in order_data:
                        order_data.append(tmpOrder)
                    if notParsedTmpOrder and notParsedTmpOrder not in not_parsed:
                        not_parsed.append(notParsedTmpOrder)

            else:
                for item in line_items:
                    meta_data = item.get('meta_data', [])
                    # print(item.get('name', []))
                    # ID
                    # Date Time
                    # Service
                    # Airport
                    # Flight number
                    # Lead name
                    # No of pax
                    # No of bags
                    # Greeter
                    # Status
                    # Booked On: website Slug/short term.
                   
                    for meta_item in meta_data:
                        #if meta_item.get('key') == 'Arrival Flight Date &amp; Time'  :
                        
                        # if meta_item.get('key') not in [ 'Flight Date Time', 'Arrival Flight Date &amp; Time' , '_WCPA_order_meta_data' ,'Lead Name', 'Select Airport', 'Flight Number', 'Luggage Assistance', 'Adults' , 'Children']:
                        #     extradata+='<li><strong>'+ str(meta_item.get('key')) +':</strong> ' + str(meta_item.get('value')) + '</li>'

                        if meta_item.get('key') == 'Flight Date Time' or meta_item.get('key') == 'Arrival Flight Date &amp; Time' or meta_item.get('key') == 'Arrival Date &amp; Time' or meta_item.get('key') == 'Flight Arrival Date &amp; Time':
                        # Extract and return the 'value'
                            flight_date_time = meta_item.get('value')
                            # if flight_date_time and flight_date_time not in [ 'June 23, 2024 16.05', 'June 13, 2024 12.35', 'May 1, 2024 15:55 pm','April 30, 2024 20:35 pm','Apr25th10-20am','Apr25th10-20am','April 8, 2024 15:55 pm']:
                            if flight_date_time:
                                # print("Shahzaib " + str(order["id"]))
                                adults= str(get_metadata_by_order_id(orders,order["id"], 'Adults'))
                                children=str(get_metadata_by_order_id(orders,order["id"], 'Children'))
                                try:
                                    # to add extra info in orders with 1 product only
                                    
                                    parsed_date = parser.parse(flight_date_time)
                                    # parsed_date, _ = parser.parse(flight_date_time, fuzzy_with_tokens=True)
                                
                                    tmpOrder = {
                                        'id': order["id"],
                                        'status': order["status"],
                                        'flight_date_time': parsed_date.strptime(str(parsed_date), '%Y-%m-%d %H:%M:%S'),
                                        'servicename': item.get('name'),
                                        'flight_date_time_raw': flight_date_time,
                                        'leadname' : get_metadata_by_order_id(orders,order["id"], 'Lead Name' ),
                                        'airport' : get_metadata_by_order_id(orders,order["id"], 'Select Airport'),   
                                        'flightnumber': get_metadata_by_order_id(orders,order["id"], 'Flight Number'),
                                        'no_of_pax_with_price': str(get_metadata_by_order_id(orders,order["id"], 'Adults')) + " + "+str(get_metadata_by_order_id(orders,order["id"], 'Children')) ,
                                        'no_of_bags_with_price': get_luggage_assistance_by_order_id(orders,order["id"], 'Luggage Assistance'),
                                        'no_of_pax':re.sub(r'\([^\)]+\)', '', str(adults)).strip() + " + "+ re.sub(r'\([^\)]+\)', '', str(children)).strip(),
                                        'no_of_bags': re.sub(r'\s*\(£?\d+(\.\d{2})?\)', '', str(get_luggage_assistance_by_order_id(orders,order["id"], 'Luggage Assistance'))).strip() ,
                                        'needspayment': ("Payment Not Needed" if not order["needs_payment"] and order["status"] == "cancelled" 
                 else "Paid" if not order["needs_payment"] 
                 else "Not Paid"),
                                        'extrainfo' : getextrainfo(meta_data),
                                        "order_url": wordpress_url
                                        }
                                except ValueError:
                                    exceptionhappened = True
                                    # print("Shahzaib" + str(meta_data[4].get('value')))
                                    notParsedTmpOrder = {
                                        'id': order["id"],
                                        'status': order["status"],
                                        'flight_date_time': flight_date_time,
                                        'servicename': item.get('name'),
                                        'flight_date_time_raw': flight_date_time,
                                        'leadname' : get_metadata_by_order_id(orders,order["id"], 'Lead Name' ),
                                        'airport' : get_metadata_by_order_id(orders,order["id"], 'Select Airport'),
                                        'flightnumber': get_metadata_by_order_id(orders,order["id"], 'Flight Number'),
                                        'no_of_pax_with_price': str(get_metadata_by_order_id(orders,order["id"], 'Adults')) + " + "+str(get_metadata_by_order_id(orders,order["id"], 'Children')) ,
                                        'no_of_bags_with_price': get_luggage_assistance_by_order_id(orders,order["id"], 'Luggage Assistance'),
                                        'no_of_pax':re.sub(r'\([^\)]+\)', '', str(adults)).strip() + " + "+ re.sub(r'\([^\)]+\)', '', str(children)).strip(),
                                        'no_of_bags': re.sub(r'\s*\(£?\d+(\.\d{2})?\)', '', str(get_luggage_assistance_by_order_id(orders,order["id"], 'Luggage Assistance'))).strip() ,
                                        'needspayment': ("Payment Not Needed" if not order["needs_payment"] and order["status"] == "cancelled" 
                 else "Paid" if not order["needs_payment"] 
                 else "Not Paid"),
                                        'extrainfo' : getextrainfo(meta_data),
                                        "order_url": wordpress_url
                                    
                                        }
        
            
                if tmpOrder and tmpOrder not in order_data:
                    order_data.append(tmpOrder)

                if notParsedTmpOrder and notParsedTmpOrder not in not_parsed:
                    not_parsed.append(notParsedTmpOrder)
        

        # sorted_order_data = sorted(order_data, key=lambda x: x['flight_date_time'])
        previous_day_orders, today_orders, tomorrow_orders, upcoming_orders, orders = categorize_orders(order_data)
        response_data = {
            # "previous_day_orders": previous_day_orders,
            "today_orders": today_orders,
            # "tomorrow_orders": tomorrow_orders,
            # "upcoming_orders": upcoming_orders,
            # 'notparsed': not_parsed,
            # 'all_orders' :  orders+not_parsed,
        }
        return jsonify(response_data )
    else:
        return jsonify({'error': 'Unable to fetch orders'}), response.status_code


