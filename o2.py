# -*- coding: utf-8 -*-
"""
Standalone WooCommerce Order Fetcher
Converts Flask route logic into a simple Python script.
"""

from woocommerce import API
from datetime import datetime, timedelta
from dateutil import parser
import concurrent.futures
import re
import json
import logging
import json
from datetime import datetime
import os

def json_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()  # Converts to "YYYY-MM-DDTHH:MM:SS"
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
        timeout=300  # increase to 60 seconds

)

# ----------------------------------------------------------
# Helper Functions
# ----------------------------------------------------------

def fetch_orders_page(wcapi, page, per_page):
    """Fetch a single page of WooCommerce orders."""
    return wcapi.get("orders", params={"per_page": per_page, "page": page}).json()

def get_all_orders(wcapi):
    """Fetch all orders using multi-threading."""
    per_page = 20
    all_orders = []

    # Fetch first page to get total order count
    first_page = wcapi.get("orders", params={"per_page": per_page, "page": 1})
    first_page_data = first_page.json()
    total_orders = int(first_page.headers.get("X-WP-Total", len(first_page_data)))
    total_pages = (total_orders // per_page) + 1

    all_orders.extend(first_page_data)
    logging.info(f"Total Orders: {total_orders} | Pages: {total_pages}")

    # Fetch remaining pages in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_orders_page, wcapi, page, per_page) for page in range(2, total_pages + 1)]
        for future in concurrent.futures.as_completed(futures):
            all_orders.extend(future.result())

    logging.info(f"✅ Finished fetching {len(all_orders)} orders total.")
    return all_orders

def get_metadata_by_order_id(orders, order_id, meta_key):
    """Find metadata value by key."""
    for order in orders:
        if order['id'] == order_id:
            for item in order['line_items']:
                for meta in item['meta_data']:
                    if meta['key'] == meta_key:
                        return meta['value']
    return None

def get_luggage_assistance_by_order_id(orders, order_id):
    """Find 'Luggage Assistance' field."""
    for order in orders:
        if order['id'] == order_id:
            for item in order['line_items']:
                luggage_entries = [m for m in item['meta_data'] if m.get("display_key") == "Luggage Assistance"]
                if len(luggage_entries) > 1:
                    return luggage_entries[1]['value']
    return ""

def getextrainfo(metadata):
    """Extract extra custom fields."""
    skip_keys = ['Flight Date Time', 'Arrival Flight Date &amp; Time', '_WCPA_order_meta_data',
                 'Lead Name', 'Select Airport', 'Flight Number', 'Luggage Assistance', 'Adults', 'Children']
    extra = ''
    for meta_item in metadata:
        if meta_item.get('key') not in skip_keys:
            extra += f"<div><strong>{meta_item.get('key')}:</strong> {meta_item.get('value')}</div>"
    return extra

def has_multiple_products(order):
    return len(order['line_items']) > 1

def categorize_orders(orders):
    """Split orders by date."""
    previous, today, tomorrow, upcoming = [], [], [], []
    today_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for order in orders:
        dt = order.get('flight_date_time')
        if not dt:
            continue
        flight_date = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        if flight_date < today_date:
            previous.append(order)
        elif flight_date == today_date:
            today.append(order)
        elif flight_date == today_date + timedelta(days=1):
            tomorrow.append(order)
        else:
            upcoming.append(order)
    return previous, today, tomorrow, upcoming



# ----------------------------------------------------------
# Main Function
# ----------------------------------------------------------

def main():
    logging.info("🚀 Fetching WooCommerce orders...")
    orders = get_all_orders(wcapi)
    processed_orders = []
    not_parsed = []

    for order in orders:
        wordpress_url = f"{wcapi.url}/wp-admin/post.php?post={order['id']}&action=edit"

        for item in order['line_items']:
            meta_data = item.get('meta_data', [])
            flight_date_time = None

            for meta_item in meta_data:
                if meta_item['key'] in ['Flight Date Time', 'Arrival Flight Date &amp; Time', 'Arrival Date &amp; Time', 'Flight Arrival Date &amp; Time']:
                    flight_date_time = meta_item.get('value')
                    break

            if not flight_date_time:
                continue

            try:
                parsed_date = parser.parse(flight_date_time)
            except Exception:
                not_parsed.append(order)
                continue

            adults = get_metadata_by_order_id(orders, order["id"], 'Adults')
            children = get_metadata_by_order_id(orders, order["id"], 'Children')
            no_of_bags = re.sub(r'\s*\(£?\d+(\.\d{2})?\)', '', str(get_luggage_assistance_by_order_id(orders, order["id"]))).strip()

            processed_orders.append({
                'id': order["id"],
                'status': order["status"],
                'flight_date_time': parsed_date,
                'servicename': item.get('name'),
                'leadname': get_metadata_by_order_id(orders, order["id"], 'Lead Name'),
                'airport': get_metadata_by_order_id(orders, order["id"], 'Select Airport'),
                'flightnumber': get_metadata_by_order_id(orders, order["id"], 'Flight Number'),
                'no_of_pax': f"{adults} + {children}",
                'no_of_bags': no_of_bags,
                'needspayment': (
                    "Payment Not Needed" if not order["needs_payment"] and order["status"] == "cancelled"
                    else "Paid" if not order["needs_payment"]
                    else "Not Paid"
                ),
                'extrainfo': getextrainfo(meta_data),
                'order_url': wordpress_url
            })

    # ✅ Categorize by date
    previous, today, tomorrow, upcoming = categorize_orders(processed_orders)

    result = {
        "previous_day_orders": previous,
        "today_orders": today,
        "tomorrow_orders": tomorrow,
        "upcoming_orders": upcoming,
        "not_parsed": not_parsed,
        "total_orders": len(processed_orders)
    }

    # ----------------------------------------------------------
    # 💾 Save each category to separate JSON files
    # ----------------------------------------------------------
    os.makedirs("orders_output", exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    file_map = {
        "previous_day_orders": previous,
        "today_orders": today,
        "tomorrow_orders": tomorrow,
        "upcoming_orders": upcoming,
        "not_parsed": not_parsed
    }

    for name, data in file_map.items():
        filename = f"orders_output/{name}_{timestamp}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=json_serializer)
        logging.info(f"💾 Saved {len(data)} {name} to {filename}")

    # Print summary
    print(f"\nTotal upcoming orders: {len(upcoming)}")
    print(f"Total today orders: {len(today)}")
    print(f"Total tomorrow orders: {len(tomorrow)}")
    print(f"Total previous orders: {len(previous)}")
    print(f"Total not parsed orders: {len(not_parsed)}")
    print(f"Total processed orders: {len(processed_orders)}")

    logging.info("✅ All JSON files saved successfully.")

if __name__ == "__main__":
    main()
