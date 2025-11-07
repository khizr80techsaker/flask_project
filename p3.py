# -*- coding: utf-8 -*-
import mysql.connector
import re
import html
import json
import os
from datetime import datetime

# ------------------ Database Config ------------------
db_config = {
    "host": "195.250.26.218",
    "port": 3306,
    "user": "meetandgreet_wp_tbb61",
    "password": "r136W_Rt?PFDNx@S",
    "database": "meetandgreet_wp_pqpql",
    "ssl_disabled": True
}

# ------------------ Helper Functions ------------------

def parse_meta(meta_str):
    meta_list = []
    for pair in (meta_str or "").split("||"):
        if "::" in pair:
            key, value = pair.split("::", 1)
            value = html.unescape(value).replace("\u00a3", "£")
            meta_list.append((key.strip(), value.strip()))
    return meta_list

def clean_text(val):
    if not val:
        return ""
    val = re.sub(r'\s*\(£?[0-9.,]+\)', '', str(val))
    val = val.replace("\u00a3", "£")
    return val.strip()

# ------------------ Core Fetch Logic ------------------

def fetch_orders(condition_sql):
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SET time_zone = '+05:00'")

    query = f"""
SELECT *
FROM (
    SELECT
        p.ID AS order_id,
        p.post_status,
        p.post_date,
        oi.order_item_id,
        oi.order_item_name,
        all_meta.meta_data,

        -- 👇 Combined flight date logic (picks first non-null)
        COALESCE(
            STR_TO_DATE(
                REPLACE(TRIM(arrival.meta_value), '.', ':'),
                CASE
                    WHEN TRIM(arrival.meta_value) REGEXP 'am|pm' THEN '%M %e, %Y %l:%i %p'
                    WHEN TRIM(arrival.meta_value) REGEXP ':' THEN '%M %e, %Y %H:%i'
                    WHEN TRIM(arrival.meta_value) REGEXP '\\.' THEN '%M %e, %Y %H:%i'
                    ELSE '%M %e, %Y'
                END
            ),
            STR_TO_DATE(
                REPLACE(TRIM(connection.meta_value), '.', ':'),
                CASE
                    WHEN TRIM(connection.meta_value) REGEXP 'am|pm' THEN '%M %e, %Y %l:%i %p'
                    WHEN TRIM(connection.meta_value) REGEXP ':' THEN '%M %e, %Y %H:%i'
                    WHEN TRIM(connection.meta_value) REGEXP '\\.' THEN '%M %e, %Y %H:%i'
                    ELSE '%M %e, %Y'
                END
            ),
            STR_TO_DATE(
                REPLACE(TRIM(flight.meta_value), '.', ':'),
                CASE
                    WHEN TRIM(flight.meta_value) REGEXP 'am|pm' THEN '%M %e, %Y %l:%i %p'
                    WHEN TRIM(flight.meta_value) REGEXP ':' THEN '%M %e, %Y %H:%i'
                    WHEN TRIM(flight.meta_value) REGEXP '\\.' THEN '%M %e, %Y %H:%i'
                    ELSE '%M %e, %Y'
                END
            )
        ) AS parsed_flight_date,

        COALESCE(arrival.meta_value, connection.meta_value, flight.meta_value) AS flight_date_raw

    FROM pbDLs_posts p
    JOIN pbDLs_woocommerce_order_items oi
        ON p.ID = oi.order_id
        AND oi.order_item_type = 'line_item'

    -- ✅ Join all meta info
    LEFT JOIN (
        SELECT 
            order_item_id,
            GROUP_CONCAT(CONCAT(meta_key, '::', meta_value) SEPARATOR '||') AS meta_data
        FROM pbDLs_woocommerce_order_itemmeta
        GROUP BY order_item_id
    ) AS all_meta ON oi.order_item_id = all_meta.order_item_id

    -- ✅ Separate joins by meta key priority
    LEFT JOIN pbDLs_woocommerce_order_itemmeta arrival
        ON arrival.order_item_id = oi.order_item_id
        AND arrival.meta_key IN (
            'Arrival Flight Date & Time', 
            'Arrival Flight Date &amp; Time',
            'Arrival Date & Time',
            'Arrival Date &amp; Time',
            'Flight Arrival Date & Time',
            'Flight Arrival Date &amp; Time'
        )

    LEFT JOIN pbDLs_woocommerce_order_itemmeta connection
        ON connection.order_item_id = oi.order_item_id
        AND connection.meta_key IN (
            'Flight Connection Date & Time',
            'Flight Connection Date &amp; Time',
            'Connection Flight Date Time'
        )

    LEFT JOIN pbDLs_woocommerce_order_itemmeta flight
        ON flight.order_item_id = oi.order_item_id
        AND flight.meta_key IN (
            'Flight Date & Time',
            'Flight Date &amp; Time',
            'Flight Date Time'
        )

    WHERE 
        p.post_type = 'shop_order'
        AND p.post_status LIKE 'wc%%'
) AS sub
WHERE sub.parsed_flight_date IS NOT NULL
ORDER BY sub.order_id DESC;
"""

    print(f"⏳ Running query with condition: {condition_sql}")
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    connection.close()

    # ----------------- Process Rows -----------------
    allowed_extrainfo_keys = {
        "Additional Information", "Additonal services", "Adults",
        "Arrival Date & Time", "Arrival Flight Date & Time", "Children",
        "Class of Travel", "Color", "Connection Flight Date Time",
        "Connection Flight Number", "Contact Number", "Contact Number (Primary)",
        "Contact Number (Secondary)", "Departure Date & Time", "Driver Contact",
        "Driver Contact Number", "Driver Name", "Drop off Address",
        "Electric Buggy", "Flight Arrival Date & Time",
        "Flight Connection Date & Time", "Flight Date Time",
        "Infants", "Is transport to or from Airport pre-arranged?",
        "Late Booking Fee", "Lead Name", "Luggage Assistance",
        "Name To Display On Meet Sign", "Other Passenger's Name",
        "Passport Country", "Pickup Address", "Primary Contact",
        "Primary Contact Number", "Secondary Contact",
        "Secondary Contact Number", "Wheelchair"
    }

    results = []
    for row in rows:
        meta_list = parse_meta(row.get("meta_data") or "")
        meta_dict = {k: v for k, v in meta_list}

        leadname = meta_dict.get("Lead Name")
        airport = meta_dict.get("Select Airport") or meta_dict.get("Airport")
        flightnumber = meta_dict.get("Flight Number") or meta_dict.get("Flight No")
        adults = meta_dict.get("Adults")
        children = meta_dict.get("Children")
        luggage = clean_text(meta_dict.get("Luggage Assistance"))
        servicename = html.unescape(row.get("order_item_name", "")).replace("&amp;", "&")
        status = (row.get("post_status") or "").replace("wc-", "").lower()
        payment_status = "Paid"
        no_of_pax = f"{adults or '0'} + {children or 'None'}"

        flight_date_raw = row.get("flight_date_raw")
        try:
            parsed_flight_date = datetime.strptime(flight_date_raw, "%B %d, %Y %I:%M %p")
            flight_date_str = parsed_flight_date.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            flight_date_str = flight_date_raw

        extrainfo_parts = []
        for key, val in meta_list:
            if key in allowed_extrainfo_keys and val:
                display_key = "Airport" if key == "Select Airport" else key
                clean_val = val.replace("&amp;", "&").replace("\u00a3", "£")
                extrainfo_parts.append(f'<div class="custom-cell"><strong>{display_key}:</strong> {clean_val}</div>')
        extrainfo = "".join(extrainfo_parts)

        wordpress_url = f"https://meetandgreetheathrow.com/wp-admin/post.php?post={row['order_id']}&action=edit"

        results.append({
            "id": row["order_id"],
            "status": status,
            "flight_date_time": flight_date_str,
            "servicename": servicename,
            "leadname": leadname,
            "airport": airport,
            "flightnumber": flightnumber,
            "no_of_pax": no_of_pax,
            "no_of_bags": luggage,
            "needspayment": payment_status,
            "extrainfo": extrainfo,
            "order_url": wordpress_url
        })

    print(f"✅ Query completed — {len(results)} rows fetched.")
    return results


# ------------------ JSON Saving ------------------

def save_orders_to_json(data, name):
    os.makedirs("orders_output", exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"orders_output/{name}_{timestamp}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"💾 Saved {len(data)} orders to {filename}")


# ------------------ Main Runner ------------------

if __name__ == "__main__":
    print("Select option:")
    print("1. Today's Orders")
    print("2. Tomorrow's Orders")
    print("3. Upcoming Orders")
    print("4. Previous Orders")
    choice = input("Enter choice (1-4): ").strip()

    if choice == "1":
        cond = "DATE(parsed_flight_date) = CURDATE()"
        orders = fetch_orders(cond)
        save_orders_to_json(orders, "today_orders")

    elif choice == "2":
        cond = "DATE(parsed_flight_date) = DATE_ADD(CURDATE(), INTERVAL 1 DAY)"
        orders = fetch_orders(cond)
        save_orders_to_json(orders, "tomorrow_orders")

    elif choice == "3":
        cond = " DATE(parsed_flight_date) > DATE_ADD(CURDATE(), INTERVAL 1 DAY)"
        orders = fetch_orders(cond)
        save_orders_to_json(orders, "upcoming_orders")

    elif choice == "4":
        cond = "DATE(parsed_flight_date) < CURDATE()"
        orders = fetch_orders(cond)
        save_orders_to_json(orders, "previous_orders")

    else:
        print("❌ Invalid option selected.")
