# actor3.py
# Removed Apify SDK and async to make it a plain Python script with def main().

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import time
import re

# ===== CONFIG =====
AIRTABLE_INPUT_BASE_ID = "app79G4gcDC3l2f4g"
AIRTABLE_INPUT_TABLE_ID = "tblLu03udJ2S5fptj"
AIRTABLE_INPUT_VIEW_ID = "viwegaYlquPC7KgS5"
AIRTABLE_OUTPUT_TABLE_ID = "tblgGtpYsyn1kpjO0"
AIRTABLE_API_KEY = "pat2WsZZK3mMRPkua.51d5ffef9db33b0b866b55870f74343ae70d132f2481f1af2de5456b5622bd50"

AIRTABLE_INPUT_URL = f"https://api.airtable.com/v0/{AIRTABLE_INPUT_BASE_ID}/{AIRTABLE_INPUT_TABLE_ID}"
AIRTABLE_OUTPUT_URL = f"https://api.airtable.com/v0/{AIRTABLE_INPUT_BASE_ID}/{AIRTABLE_OUTPUT_TABLE_ID}"
HEADERS = {"Authorization": f"Bearer {AIRTABLE_API_KEY}", "Content-Type": "application/json"}

# ===== SELENIUM SETUP =====
# Note: In Apify, Selenium is pre-installed, but ensure Chrome is available in the container.

# ===== HELPERS =====
def clean_available_units(value):
    try:
        if value is None:
            return 0.0
        cleaned = re.sub(r"[^0-9.\-]", "", str(value))
        if cleaned == "":
            return 0.0
        return float(cleaned)
    except:
        return 0.0

def clean_currency(value):
    try:
        if value is None:
            return 0.0
        cleaned = re.sub(r"[^0-9.\-]", "", str(value))
        if cleaned == "":
            return 0.0
        return float(cleaned)
    except:
        return 0.0

def escape_for_airtable_formula(value):
    """Escape single quotes for Airtable filterByFormula."""
    if value is None:
        return ""
    return str(value).replace("'", "\\'")

def get_or_create_property_listing_id(dev_name):
    """Look up a record ID in the Property Listing table by Development Name, create if missing."""
    PROPERTY_LISTING_TABLE_ID = "tblLu03udJ2S5fptj"  # linked table ID
    url = f"https://api.airtable.com/v0/{AIRTABLE_INPUT_BASE_ID}/{PROPERTY_LISTING_TABLE_ID}"
    
    print(f"🔍 Looking up property listing ID for: {dev_name}")
    safe_name = escape_for_airtable_formula(dev_name)
    params = {"filterByFormula": f"{{Development Name}}='{safe_name}'"}
    r = requests.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    data = r.json()
    
    if data["records"]:
        rec_id = data["records"][0]["id"]
        print(f"✅ Found existing linked record ID for {dev_name}: {rec_id}")
        return rec_id
    else:
        print(f"⚠️ No linked record found for {dev_name} — creating new one.")
        payload = {"fields": {"Development Name": dev_name}}
        create_r = requests.post(url, headers=HEADERS, json=payload)
        if create_r.status_code == 200:
            new_id = create_r.json()["id"]
            print(f"✅ Created new linked record ID for {dev_name}: {new_id}")
            return new_id
        else:
            print(f"❌ Failed to create linked record for {dev_name}: {create_r.text}")
            return None

def get_all_records_with_yes_units():
    """Fetch all records from Airtable where 'Units Data Available' is 'yes'."""
    records = []
    offset = None

    while True:
        params = {
            "view": AIRTABLE_INPUT_VIEW_ID,
            "fields[]": ["URL to Scrape Unit Details", "Development Name", "Units Data Available"]
        }
        if offset:
            params["offset"] = offset

        r = requests.get(AIRTABLE_INPUT_URL, headers=HEADERS, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()

        for rec in data.get("records", []):
            fields = rec.get("fields", {})
            units_available_status = fields.get("Units Data Available")
            url = fields.get("URL to Scrape Unit Details")
            dev_name = fields.get("Development Name")

            if url and dev_name and str(units_available_status).strip().lower() == "yes":
                records.append({"id": rec["id"], "url": url, "dev_name": dev_name})

        offset = data.get("offset")
        if not offset:
            break

    return records

def update_units_data_available(record_id, status):
    """Update the 'Units Data Available' field in the Property Listing table."""
    url = f"{AIRTABLE_INPUT_URL}/{record_id}"
    payload = {"fields": {"Units Data Available": status}}
    r = requests.patch(url, headers=HEADERS, json=payload, timeout=60)
    if r.status_code == 200:
        print(f"✅ Updated record {record_id}: Units Data Available = {status}")
    else:
        print(f"❌ Error updating record {record_id}: {r.text}")

def check_units_table_exists(driver):
    """Check if the units table exists and has rows."""
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".table-responsive tbody tr"))
        )
        return True
    except:
        return False

def post_with_retry(url, headers, json_data, retries=3, backoff_factor=1):
    """Send a POST request with retries and exponential backoff."""
    for attempt in range(retries):
        try:
            response = requests.post(url, headers=headers, json=json_data)
            response.raise_for_status()  # Raise if not 2xx status
            return response
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Request failed (attempt {attempt + 1}/{retries}): {e}")
            if attempt == retries - 1:
                raise  # Raise on last attempt
            time.sleep(backoff_factor * (2 ** attempt))  # Exponential backoff
    return None

def chunk_list(lst, n):
    """Split a list into chunks of size n."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def patch_with_retry(url, headers, json_data, retries=3, backoff_factor=1):
    """Send a PATCH request with retries and exponential backoff."""
    for attempt in range(retries):
        try:
            response = requests.patch(url, headers=headers, json=json_data)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"⚠️ PATCH failed (attempt {attempt + 1}/{retries}): {e}")
            if attempt == retries - 1:
                raise
            time.sleep(backoff_factor * (2 ** attempt))
    return None

def get_with_retry(url, headers, params=None, retries=3, backoff_factor=1):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=60)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"⚠️ GET failed (attempt {attempt + 1}/{retries}): {e}")
            if attempt == retries - 1:
                raise
            time.sleep(backoff_factor * (2 ** attempt))
    return None

def parse_units_table(driver):
    """Parse units table into list of dicts with robust error handling and validation."""
    try:
        # Try multiple selectors for table container
        table_selectors = [
            ".table-responsive",
            "table",
            ".table",
            "[class*='table']",
            "div[class*='responsive']"
        ]
        
        table_container = None
        for selector in table_selectors:
            try:
                table_container = driver.find_element(By.CSS_SELECTOR, selector)
                print(f"✅ Found table with selector: {selector}")
                break
            except:
                continue
        
        if not table_container:
            print("❌ No table container found with any selector")
            return []

        # Try multiple selectors for rows
        row_selectors = [
            "tbody tr",
            "tr",
            "tbody > tr",
            ".table-responsive tbody tr"
        ]
        
        rows = []
        for selector in row_selectors:
            try:
                rows = table_container.find_elements(By.CSS_SELECTOR, selector)
                if rows:
                    print(f"✅ Found {len(rows)} rows with selector: {selector}")
                    break
            except:
                continue
        
        if not rows:
            print("❌ No rows found in table")
            return []

        last_bedroom_type = None
        data_list = []
        row_index = 0

        for row in rows:
            row_index += 1
            try:
                # Get all cells (th and td) in the row
                cells_elems = row.find_elements(By.XPATH, ".//th|.//td")
                if not cells_elems:
                    print(f"⚠️ Row {row_index}: No cells found, skipping")
                    continue
                
                # Extract text from cells and clean
                cells = []
                for i, cell_elem in enumerate(cells_elems):
                    try:
                        cell_text = cell_elem.text.strip()
                        cells.append(cell_text)
                    except Exception as e:
                        print(f"⚠️ Row {row_index}, Cell {i}: Error extracting text: {e}")
                        cells.append("")
                
                # Check if this row has header cells (th elements)
                th_elements = row.find_elements(By.XPATH, ".//th")
                has_header = len(th_elements) > 0
                
                # Debug: Print raw cells for first few rows
                if row_index <= 3:
                    print(f"🔍 Row {row_index} raw cells: {cells}")
                
                # Handle the specific table structure with rowspan
                if has_header and len(cells) == 5:
                    # This is a row with bedroom type (th) + unit data (td)
                    # First, try to get bedroom type from th elements
                    th_text = [th.text.strip() for th in th_elements if th.text.strip()]
                    bedroom_type_from_th = th_text[0] if th_text else ""
                    
                    bedroom_type = cells[0] if cells[0] else bedroom_type_from_th or (last_bedroom_type or "")
                    unit_name = cells[1] if len(cells) > 1 else ""
                    area = cells[2] if len(cells) > 2 else ""
                    available_units = cells[3] if len(cells) > 3 else "0"
                    price_from = cells[4] if len(cells) > 4 else "0"
                    
                    # Update last_bedroom_type if we have a valid one
                    if bedroom_type and bedroom_type != last_bedroom_type:
                        last_bedroom_type = bedroom_type
                        
                elif has_header and len(cells) == 4:
                    # This might be a header row or a row with bedroom type but no unit data
                    # First, try to get bedroom type from th elements
                    th_text = [th.text.strip() for th in th_elements if th.text.strip()]
                    bedroom_type_from_th = th_text[0] if th_text else ""
                    
                    # Check if first cell looks like a bedroom type
                    first_cell = cells[0] if cells[0] else ""
                    if any(keyword in first_cell.upper() for keyword in ['BEDROOM', 'STUDY', 'PREMIUM']):
                        # This is a bedroom type header row, skip it
                        print(f"⚠️ Row {row_index}: Bedroom type header row, skipping")
                        continue
                    else:
                        # This might be a data row with th element - could be continuation row
                        bedroom_type = bedroom_type_from_th or last_bedroom_type or ""
                        unit_name = cells[0] if len(cells) > 0 else ""
                        area = cells[1] if len(cells) > 1 else ""
                        available_units = cells[2] if len(cells) > 2 else "0"
                        price_from = cells[3] if len(cells) > 3 else "0"
                        
                        # If this is a continuation row with th element but empty data, 
                        # it might still be meaningful (e.g., "no units available" for this type)
                        if not any([unit_name, area, available_units, price_from]) and bedroom_type:
                            # This could be a row indicating no units available for this bedroom type
                            unit_name = "No units available"
                            available_units = "0"
                            price_from = "0"
                        
                elif not has_header and len(cells) == 4:
                    # Regular data row without bedroom type
                    bedroom_type = last_bedroom_type or ""
                    unit_name = cells[0] if len(cells) > 0 else ""
                    area = cells[1] if len(cells) > 1 else ""
                    available_units = cells[2] if len(cells) > 2 else "0"
                    price_from = cells[3] if len(cells) > 3 else "0"
                    
                    # If this row has no meaningful data but we have a bedroom type from previous row,
                    # it might indicate "no units available" for this type
                    if not any([unit_name, area, available_units, price_from]) and bedroom_type:
                        unit_name = "No units available"
                        available_units = "0"
                        price_from = "0"
                    
                elif not has_header and len(cells) == 5:
                    # Data row with 5 cells, might have bedroom type in first cell
                    bedroom_type = cells[0] if len(cells) > 0 and any(keyword in cells[0].upper() for keyword in ['BEDROOM', 'STUDY', 'PREMIUM']) else (last_bedroom_type or "")
                    unit_name = cells[1] if len(cells) > 1 else ""
                    area = cells[2] if len(cells) > 2 else ""
                    available_units = cells[3] if len(cells) > 3 else "0"
                    price_from = cells[4] if len(cells) > 4 else "0"
                    
                    # Update last_bedroom_type if we found one
                    if bedroom_type and bedroom_type != last_bedroom_type:
                        last_bedroom_type = bedroom_type
                else:
                    # Unknown structure, try to parse as best we can
                    print(f"⚠️ Row {row_index}: Unknown structure with {len(cells)} cells, attempting basic parse")
                    bedroom_type = last_bedroom_type or ""
                    unit_name = cells[0] if len(cells) > 0 else ""
                    area = cells[1] if len(cells) > 1 else ""
                    available_units = cells[2] if len(cells) > 2 else "0"
                    price_from = cells[3] if len(cells) > 3 else "0"
                    
                    # If this row has no meaningful data but we have a bedroom type from previous row,
                    # it might indicate "no units available" for this type
                    if not any([unit_name, area, available_units, price_from]) and bedroom_type:
                        unit_name = "No units available"
                        available_units = "0"
                        price_from = "0"
                
                # Skip if this looks like a header row (no meaningful data)
                # Be more lenient - only skip if we have absolutely no meaningful data
                has_any_data = any([bedroom_type, unit_name, area, available_units, price_from])
                is_continuation_row = has_header and len(cells) >= 4  # Rows with th elements might be continuation rows
                has_bedroom_type = bool(bedroom_type and bedroom_type.strip())
                
                # Skip only if no data AND not a continuation row AND no bedroom type
                # This allows rows with just bedroom type to pass through
                if not has_any_data and not is_continuation_row and not has_bedroom_type:
                    print(f"⚠️ Row {row_index}: Header row or no meaningful data, skipping")
                    continue
                
                # Clean and normalize data
                bedroom_type = (bedroom_type or "").replace("\u2019", "'").replace("'", "'").strip()
                unit_name = (unit_name or "").replace("\u2019", "'").replace("'", "'").strip()
                area = (area or "").strip()
                

                
                # Handle special price values
                if price_from == "-" or price_from == "N/A" or not price_from:
                    price_from = "0"
                
                # Create data record
                data = {
                    "Bedroom Type": bedroom_type,
                    "Unit Name": unit_name,
                    "Area (sqft)": area,
                    "Available Units": clean_available_units(available_units),
                    "Price From": clean_currency(price_from),
                }
                
                # Validate the record before adding
                # Be more lenient - accept rows with bedroom type even if unit name/area are empty
                # This handles cases where bedroom type spans multiple rows
                has_bedroom_type = bool(data["Bedroom Type"].strip())
                has_unit_info = bool(data["Unit Name"].strip() or data["Area (sqft)"].strip())
                has_any_meaningful_data = has_bedroom_type or has_unit_info
                
                if has_any_meaningful_data:
                    data_list.append(data)
                    if row_index <= 3:  # Show first 3 rows for debugging
                        print(f"✅ Row {row_index} parsed: {data}")
                else:
                    print(f"⚠️ Row {row_index}: Insufficient data, skipping")
                    
            except Exception as e:
                print(f"❌ Row {row_index}: Error parsing row: {e}")
                continue

        print(f"📊 Successfully parsed {len(data_list)} unit records from {row_index} rows")
        return data_list
        
    except Exception as e:
        print(f"❌ Error in parse_units_table: {e}")
        return []

def generate_unit_key(unit_fields):
    parts = [
        str(unit_fields.get("Bedroom Type", "")).strip().lower(),
        str(unit_fields.get("Unit Name", "")).strip().lower(),
        str(unit_fields.get("Area (sqft)", "")).strip().lower(),
    ]
    norm = [re.sub(r"\s+", " ", p.replace("\u2019", "'").replace("'", "'")) for p in parts]
    return "|".join(norm)

def generate_unit_type_key(unit_fields):
    """Generate a unique Unit_Type_Key for deduplication."""
    parts = [
        str(unit_fields.get("Bedroom Type", "")).strip().lower(),
        str(unit_fields.get("Unit Name", "")).strip().lower(),
        str(unit_fields.get("Area (sqft)", "")).strip().lower(),
    ]
    # Normalize and clean the parts
    norm = [re.sub(r"\s+", " ", p.replace("\u2019", "'").replace("'", "'")) for p in parts]
    # Create a unique key
    return "|".join(norm)

def fetch_existing_units_for_property(linked_property_id):
    existing = {}
    offset = None
    while True:
        params = {
            "pageSize": 100,
            "fields[]": [
                "Bedroom Type",
                "Unit Name",
                "Area (sqft)",
                "Available Units",
                "Price From",
                "Property Listing",
            ],
        }
        if offset:
            params["offset"] = offset
        r = get_with_retry(AIRTABLE_OUTPUT_URL, HEADERS, params=params)
        data = r.json()
        for rec in data.get("records", []):
            fields = rec.get("fields", {})
            linked_list = fields.get("Property Listing", []) or []
            if linked_property_id in linked_list:
                key = generate_unit_key(fields)
                existing[key] = {"id": rec["id"], "fields": fields}
        offset = data.get("offset")
        if not offset:
            break
    return existing

def fetch_existing_units_by_type_key():
    """Fetch all existing units and create a map using Unit_Type_Key for deduplication."""
    existing = {}
    offset = None
    while True:
        params = {
            "pageSize": 100,
            "fields[]": [
                "Bedroom Type",
                "Unit Name",
                "Area (sqft)",
                "Available Units",
                "Price From",
                "Property Listing",
                "Unit_Type_Key",
            ],
        }
        if offset:
            params["offset"] = offset
        r = get_with_retry(AIRTABLE_OUTPUT_URL, HEADERS, params=params)
        data = r.json()
        for rec in data.get("records", []):
            fields = rec.get("fields", {})
            type_key = generate_unit_type_key(fields)
            existing[type_key] = {"id": rec["id"], "fields": fields}
        offset = data.get("offset")
        if not offset:
            break
    return existing

def batch_create_units(units, linked_property_id):
    if not units:
        return
    print(f"📤 Creating {len(units)} new unit type(s) ...")
    payload_records = []
    for u in units:
        # Generate Unit_Type_Key for deduplication
        unit_type_key = generate_unit_type_key(u)
        
        fields = {
            "Bedroom Type": u.get("Bedroom Type", ""),
            "Unit Name": u.get("Unit Name", ""),
            "Area (sqft)": u.get("Area (sqft)", ""),
            "Available Units": clean_available_units(u.get("Available Units", 0)),
            "Price From": clean_currency(u.get("Price From", 0)),
            "Property Listing": [linked_property_id],
            "Unit_Type_Key": unit_type_key,
        }
        payload_records.append({"fields": fields})

    for batch in chunk_list(payload_records, 10):
        payload = {"records": batch}
        try:
            response = post_with_retry(AIRTABLE_OUTPUT_URL, HEADERS, payload)
            if response and response.status_code == 200:
                print(f"✅ Created batch of {len(batch)} unit type(s)")
            else:
                print(f"❌ Error creating batch: {response.text if response else 'No response'}")
        except Exception as e:
            print(f"⚠️ Failed to create batch: {e}")
        time.sleep(0.3)

def batch_update_units(updates):
    if not updates:
        return
    print(f"🛠️ Updating {len(updates)} unit record(s) ...")
    records = [{"id": u["id"], "fields": u["fields"]} for u in updates]
    for batch in chunk_list(records, 10):
        payload = {"records": batch}
        try:
            response = patch_with_retry(AIRTABLE_OUTPUT_URL, HEADERS, payload)
            if response and response.status_code == 200:
                print(f"✅ Updated batch of {len(batch)} record(s)")
            else:
                print(f"❌ Error updating batch: {response.text if response else 'No response'}")
        except Exception as e:
            print(f"⚠️ Failed to update batch: {e}")
        time.sleep(0.3)

def get_all_records_with_yes_units():
    """Records with Units Data Available == 'yes' and URL present."""
    records = []
    offset = None
    while True:
        params = {
            "view": AIRTABLE_INPUT_VIEW_ID,
            "fields[]": ["URL to Scrape Unit Details", "Development Name", "Units Data Available"],
        }
        if offset:
            params["offset"] = offset
        r = requests.get(AIRTABLE_INPUT_URL, headers=HEADERS, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        for rec in data.get("records", []):
            fields = rec.get("fields", {})
            url = fields.get("URL to Scrape Unit Details")
            dev_name = fields.get("Development Name")
            status = str(fields.get("Units Data Available", "")).strip().lower()
            if url and dev_name and status == "yes":
                records.append({"id": rec["id"], "url": url, "dev_name": dev_name})
        offset = data.get("offset")
        if not offset:
            break
    return records

def process_initial_scrape(driver, record_id, url, dev_name):
    print(f"\n🌐 Scraping (initial): {url} ({dev_name})")
    try:
        driver.get(url)
    except Exception as e:
        print(f"⚠️ Navigation failed: {e}")
        update_units_data_available(record_id, "no")
        return

    if not check_units_table_exists(driver):
        print(f"⚠️ No table found for {dev_name}")
        update_units_data_available(record_id, "no")
        return

    update_units_data_available(record_id, "yes")
    linked_id = get_or_create_property_listing_id(dev_name)
    if not linked_id:
        print(f"❌ Skipping — no valid linked_id for {dev_name}")
        return

    data_list = parse_units_table(driver)
    if not data_list:
        print("⚠️ No rows parsed from table")
        return

    # Check for duplicates and updates using Unit_Type_Key within the same property
    existing_units = fetch_existing_units_for_property(linked_id)
    new_units = []
    update_units = []
    duplicate_count = 0
    update_count = 0
    
    # Create a map of existing unit type keys to their data for this property
    existing_type_map = {}
    for existing_data in existing_units.values():
        existing_type_key = generate_unit_type_key(existing_data["fields"])
        existing_type_map[existing_type_key] = existing_data
    
    for unit in data_list:
        unit_type_key = generate_unit_type_key(unit)
        if unit_type_key in existing_type_map:
            # Check if values have changed
            existing_data = existing_type_map[unit_type_key]
            existing_fields = existing_data["fields"]
            
            # Compare Available Units and Price From
            new_available = clean_available_units(unit.get("Available Units", 0))
            new_price = clean_currency(unit.get("Price From", 0))
            existing_available = clean_available_units(existing_fields.get("Available Units", 0))
            existing_price = clean_currency(existing_fields.get("Price From", 0))
            
            # Use small tolerance for floating point comparisons
            tolerance = 0.01
            available_changed = abs(new_available - existing_available) > tolerance
            price_changed = abs(new_price - existing_price) > tolerance
            
            if available_changed or price_changed:
                # Values have changed, need to update
                update_count += 1
                update_fields = {}
                if available_changed:
                    update_fields["Available Units"] = new_available
                if price_changed:
                    update_fields["Price From"] = new_price
                
                update_units.append({
                    "id": existing_data["id"],
                    "fields": update_fields
                })
                print(f"🔄 Updating unit: {unit.get('Bedroom Type', '')} - {unit.get('Unit Name', '')} (Available: {existing_available}→{new_available}, Price: {existing_price}→{new_price})")
            else:
                # No changes, skip
                duplicate_count += 1
                print(f"⚠️ Skipping unchanged unit: {unit.get('Bedroom Type', '')} - {unit.get('Unit Name', '')}")
        else:
            new_units.append(unit)
    
    if duplicate_count > 0:
        print(f"⚠️ Skipped {duplicate_count} unchanged units")
    
    if update_count > 0:
        print(f"🔄 Found {update_count} units to update")
    
    # Process updates first
    if update_units:
        batch_update_units(update_units)
    
    if not new_units and not update_units:
        print("⚠️ No new units to add and no updates needed")
        return

    print(f"📤 Sending {len(new_units)} new units to Airtable in batches...")
    for batch in chunk_list(new_units, 10):
        payload = {"records": [{"fields": {**d, "Property Listing": [linked_id]}} for d in batch]}
        try:
            response = post_with_retry(AIRTABLE_OUTPUT_URL, HEADERS, payload)
            if response and response.status_code == 200:
                print(f"✅ Added batch of {len(batch)} units")
            else:
                print(f"❌ Error adding batch: {response.text if response else 'No response'}")
        except Exception as e:
            print(f"⚠️ Failed to add batch: {e}")
        time.sleep(0.3)

def process_update_scrape(driver, url, dev_name):
    print(f"\n🌐 Scraping (update): {url} ({dev_name})")
    try:
        driver.get(url)
    except Exception as e:
        print(f"⚠️ Navigation failed: {e}")
        return

    if not check_units_table_exists(driver):
        print(f"⚠️ No table found for {dev_name}")
        return

    linked_id = get_or_create_property_listing_id(dev_name)
    if not linked_id:
        print(f"❌ Skipping — no valid linked_id for {dev_name}")
        return

    website_units = parse_units_table(driver)
    website_map = {generate_unit_key(u): u for u in website_units}

    existing_map = fetch_existing_units_for_property(linked_id)

    # Add new unit types
    new_units = []
    for key, unit in website_map.items():
        if key not in existing_map:
            new_units.append(unit)
    batch_create_units(new_units, linked_id)

    # Update changed fields
    updates = []
    for key, existing in existing_map.items():
        if key in website_map:
            web_unit = website_map[key]
            existing_fields = existing["fields"]
            changed = {}

            web_available = clean_available_units(web_unit.get("Available Units", 0))
            web_price = clean_currency(web_unit.get("Price From", 0))

            cur_available = clean_available_units(existing_fields.get("Available Units", 0))
            cur_price = clean_currency(existing_fields.get("Price From", 0))

            # Use small tolerance for floating point comparisons
            tolerance = 0.01
            
            if abs(web_available - cur_available) > tolerance:
                changed["Available Units"] = web_available
            if abs(web_price - cur_price) > tolerance:
                changed["Price From"] = web_price

            if changed:
                updates.append({"id": existing["id"], "fields": changed})
    batch_update_units(updates)

    # Sold out/removed (missing on website)
    sold_out_updates = []
    for key, existing in existing_map.items():
        if key not in website_map:
            sold_out_updates.append({
                "id": existing["id"],
                "fields": {"Available Units": 0.0, "Price From": 0.0},
            })
    batch_update_units(sold_out_updates)

def main():
    # Setup Selenium
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.page_load_strategy = "eager"

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(60)

    try:
        # Initial data collection: scrape all fields for records with 'yes' status
        records = get_all_records_with_yes_units()
        print(f"📌 Found {len(records)} records to scrape (Units Data Available = 'yes').")
        for rec in records:
            process_initial_scrape(driver, rec["id"], rec["url"], rec["dev_name"])

    finally:
        driver.quit()

if __name__ == "__main__":
    main()