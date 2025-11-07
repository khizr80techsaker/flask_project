# -*- coding: utf-8 -*-
"""
Fetch WooCommerce order by specific ID (5086)
"""

from woocommerce import API
from datetime import datetime
from dateutil import parser
import json
import logging
import os
import re

def json_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

# 🧠 Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)

# 🛒 WooCommerce Credentials
wcapi = API(
    url="https://meetandgreetheathrow.com",
    consumer_key="ck_bcc01c92ff106c98d303ba7b0bf4775bfd4911da",
    consumer_secret="cs_1bb7b3da942206be797b0757ca69ecbd10a3cab2",
    version="wc/v3",
    timeout=300
)

# ----------------------------------------------------------
# Helper Functions
# ----------------------------------------------------------

def get_metadata_value(meta_data, key):
    """Find metadata value by key."""
    for meta in meta_data:
        if meta.get("key") == key:
            return meta.get("value")
    return None

def getextrainfo(meta_data):
    """Extract extra custom fields."""
    skip_keys = [
        'Flight Date Time', 'Arrival Flight Date &amp; Time', '_WCPA_order_meta_data',
        'Lead Name', 'Select Airport', 'Flight Number', 'Luggage Assistance', 'Adults', 'Children'
    ]
    extra = ''
    for meta_item in meta_data:
        if meta_item.get('key') not in skip_keys:
            extra += f"<div><strong>{meta_item.get('key')}:</strong> {meta_item.get('value')}</div>"
    return extra

# ----------------------------------------------------------
# Main Function
# ----------------------------------------------------------

def main():
    order_id = 1573
    logging.info(f"🚀 Fetching WooCommerce order ID {order_id}...")

    order = wcapi.get(f"orders/{order_id}").json()

    if "id" not in order:
        logging.error("❌ Order not found or API error.")
        print(order)
        return

    wordpress_url = f"{wcapi.url}/wp-admin/post.php?post={order_id}&action=edit"

    item = order['line_items'][0]
    meta_data = item.get('meta_data', [])
    flight_date_time = None

    for meta_item in meta_data:
        if meta_item['key'] in [
            'Flight Date Time', 'Arrival Flight Date &amp; Time',
            'Arrival Date &amp; Time', 'Flight Arrival Date &amp; Time'
        ]:
            flight_date_time = meta_item.get('value')
            break
    
    try:
        parsed_date = parser.parse(flight_date_time)
        logging.info(f"✅ Saved order to {flight_date_time}")
        logging.info(f"✅ Saved order to {parsed_date}")

    except Exception:
        parsed_date = None

    processed_order = {
        'id': order["id"],
        'status': order["status"],
        'flight_date_time': parsed_date,
        'servicename': item.get('name'),
        'leadname': get_metadata_value(meta_data, 'Lead Name'),
        'airport': get_metadata_value(meta_data, 'Select Airport'),
        'flightnumber': get_metadata_value(meta_data, 'Flight Number'),
        'no_of_pax': f"{get_metadata_value(meta_data, 'Adults')} + {get_metadata_value(meta_data, 'Children')}",
        'no_of_bags': get_metadata_value(meta_data, 'Luggage Assistance'),
        'needspayment': "Paid" if not order.get("needs_payment", True) else "Not Paid",
        'extrainfo': getextrainfo(meta_data),
        'order_url': wordpress_url
    }

    # 💾 Save to file
    os.makedirs("orders_output", exist_ok=True)
    filename = f"orders_output/order_{order_id}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(processed_order, f, ensure_ascii=False, indent=2, default=json_serializer)

    # logging.info(f"✅ Saved order {order_id} to {filename}")

    # Print result
    print(json.dumps(processed_order, indent=2, default=json_serializer))


if __name__ == "__main__":
    main()
