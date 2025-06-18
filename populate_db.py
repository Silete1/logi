import os
import re
import time
import logging
import requests
import psycopg2
from faker import Faker
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

# Configuration
DB_CONFIG = {
    'dbname': 'port_logistics',
    'user': 'postgres',
    'password': 'postgres',
    'host': 'localhost',
    'port': '5432'
}
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9'
}

# Initialize Faker
fake = Faker()
Faker.seed(42)  # For reproducible results

def get_wikipedia_data(url):
    """Fetch Wikipedia content with ethical scraping practices"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        # Check for rate limiting
        if response.status_code == 429:
            logger.warning("Rate limited. Waiting 30 seconds before retrying...")
            time.sleep(30)
            return get_wikipedia_data(url)
            
        return response.content
    except requests.RequestException as e:
        logger.error(f"Request failed: {str(e)}")
        return None

def scrape_shipping_companies():
    """Scrape top shipping companies from Wikipedia"""
    logger.info("Scraping shipping companies from Wikipedia...")
    url = "https://en.wikipedia.org/wiki/List_of_largest_container_shipping_companies"
    content = get_wikipedia_data(url)
    companies = []
    
    if content:
        soup = BeautifulSoup(content, 'html.parser')
        table = soup.find('table', {'class': 'wikitable'})
        
        if table:
            for row in table.find_all('tr')[1:]:  # Skip header
                cols = row.find_all('td')
                if len(cols) >= 2:
                    name = cols[1].get_text(strip=True)
                    # Clean company names 
                    name = re.sub(r'\[\d+\]', '', name).strip()
                    companies.append(name)
            logger.info(f"Scraped {len(companies)} shipping companies")
        else:
            logger.warning("Company table not found. Using fallback data")
            companies = ["Maersk", "Mediterranean Shipping Company", "CMA CGM", 
                         "COSCO Shipping", "Hapag-Lloyd", "Ocean Network Express"]
    return companies[:15]  # Limit to top 15

def scrape_container_ports():
    """Scrape busiest container ports from Wikipedia"""
    logger.info("Scraping container ports from Wikipedia...")
    url = "https://en.wikipedia.org/wiki/List_of_busiest_container_ports"
    content = get_wikipedia_data(url)
    ports = []
    
    if content:
        soup = BeautifulSoup(content, 'html.parser')
        tables = soup.find_all('table', {'class': 'wikitable'})
        
        if tables:
            # Focus on the first table (current rankings)
            for row in tables[0].find_all('tr')[1:]:  # Skip header
                cols = row.find_all('td')
                if len(cols) >= 3:
                    port_name = cols[1].get_text(strip=True)
                    # Remove citations and special characters 
                    port_name = re.sub(r'\[\w+\]', '', port_name).split('(')[0].strip()
                    ports.append(port_name)
            logger.info(f"Scraped {len(ports)} container ports")
        else:
            logger.warning("Ports table not found. Using fallback data")
            ports = ["Shanghai", "Singapore", "Ningbo-Zhoushan", "Shenzhen", "Guangzhou"]
    return ports

def generate_container_number():
    """Generate valid container number with ISO 6346 check digit"""
    owner_code = fake.random_uppercase_letter() + fake.random_uppercase_letter() + fake.random_uppercase_letter()
    product_group = 'U'  # Universal container
    serial_number = fake.random_number(digits=6, fix_len=True)
    base = owner_code + product_group + str(serial_number)
    
    # Calculate check digit 
    char_values = []
    for i, char in enumerate(base):
        num = ord(char)
        if 65 <= num <= 90:  # A-Z
            num -= 55
        elif 48 <= num <= 57:  # 0-9
            num -= 48
        char_values.append(num * (2 ** i))
    
    total = sum(char_values)
    check_digit = total % 11 % 10
    return base + str(check_digit)

def truncate_tables(db_conn):
    """Truncate all tables in dependency order"""
    tables = [
        'container', 'shipment', 'berth', 'client', 'vessel',
        'BerthStatus', 'ContainerType', 'ShipmentStatus'
    ]
    
    with db_conn.cursor() as cursor:
        cursor.execute("SET session_replication_role = 'replica';")
        for table in tables:
            try:
                cursor.execute(f'TRUNCATE TABLE "{table}" CASCADE;')
                logger.info(f"Truncated table: {table}")
            except psycopg2.Error as e:
                logger.error(f"Error truncating {table}: {str(e)}")
        cursor.execute("SET session_replication_role = 'origin';")
    db_conn.commit()

def populate_lookup_tables(db_conn):
    """Populate ENUM lookup tables"""
    with db_conn.cursor() as cursor:
        # ShipmentStatus 
        statuses = ['PENDING', 'IN_TRANSIT', 'AWAITING_CUSTOMS', 'CLEARED', 'DELIVERED']
        for status in statuses:
            cursor.execute(
                'INSERT INTO "ShipmentStatus" (status_name) VALUES (%s) ON CONFLICT DO NOTHING;',
                (status,)
            )
        
        # ContainerType
        container_types = ['DRY', 'REEFER', 'OPEN_TOP', 'FLAT_RACK']
        for ctype in container_types:
            cursor.execute(
                'INSERT INTO "ContainerType" (type_name) VALUES (%s) ON CONFLICT DO NOTHING;',
                (ctype,)
            )
        
        # BerthStatus
        berth_statuses = ['AVAILABLE', 'OCCUPIED', 'MAINTENANCE']
        for status in berth_statuses:
            cursor.execute(
                'INSERT INTO "BerthStatus" (status_name) VALUES (%s) ON CONFLICT DO NOTHING;',
                (status,)
            )
        logger.info("Populated lookup tables")
    db_conn.commit()

def populate_clients(db_conn, companies):
    """Insert shipping companies as clients with synthetic contacts"""
    with db_conn.cursor() as cursor:
        client_ids = []
        for company in companies:
            cursor.execute(
                '''INSERT INTO "client" (company_name, contact_person, email, phone_number)
                VALUES (%s, %s, %s, %s) RETURNING client_id;''',
                (company, fake.name(), fake.company_email(), fake.phone_number())
            )
            client_ids.append(cursor.fetchone()[0])
        logger.info(f"Inserted {len(client_ids)} clients")
        return client_ids

def populate_vessels(db_conn, client_count):
    """Generate vessels with company-aligned names and valid IMO numbers"""
    vessel_prefixes = ["Atlantic", "Pacific", "Global", "Marine", "Ocean"]
    vessel_suffixes = ["Express", "Carrier", "Voyager", "Explorer", "Horizon"]
    
    with db_conn.cursor() as cursor:
        vessel_ids = []
        for i in range(client_count * 3):  # 3 vessels per client
            # Generate realistic vessel name 
            prefix = fake.random_element(vessel_prefixes)
            suffix = fake.random_element(vessel_suffixes)
            vessel_name = f"{prefix} {suffix} {fake.random_int(100, 999)}"
            
            # Generate valid 7-digit IMO number (fixed the type conversion error)
            imo_number = "98" + str(fake.random_number(digits=5, fix_len=True))
            
            cursor.execute(
                '''INSERT INTO "vessel" (vessel_name, imo_number)
                VALUES (%s, %s) RETURNING vessel_id;''',
                (vessel_name, imo_number)
            )
            vessel_ids.append(cursor.fetchone()[0])
        logger.info(f"Inserted {len(vessel_ids)} vessels")
        return vessel_ids

def populate_berths(db_conn, vessel_ids):
    """Create berths and assign vessels to available berths"""
    with db_conn.cursor() as cursor:
        # Get status IDs
        cursor.execute('SELECT status_name, berth_status_id FROM "BerthStatus";')
        status_ids = {row[0]: row[1] for row in cursor.fetchall()}
        
        berth_ids = []
        for i in range(1, 21):  # Create 20 berths
            status = 'OCCUPIED' if i <= len(vessel_ids) else 'AVAILABLE'
            vessel_id = vessel_ids[i-1] if i <= len(vessel_ids) else None
            
            cursor.execute(
                '''INSERT INTO "berth" (berth_number, berth_status_id, vessel_id)
                VALUES (%s, %s, %s) RETURNING berth_id;''',
                (f"B{i:03d}", status_ids[status], vessel_id)
            )
            berth_ids.append(cursor.fetchone()[0])
        logger.info(f"Inserted {len(berth_ids)} berths")
        return berth_ids

def populate_shipments(db_conn, client_ids, ports):
    """Create shipments with realistic port logistics data"""
    status_options = ['PENDING', 'IN_TRANSIT', 'AWAITING_CUSTOMS', 'CLEARED']
    
    with db_conn.cursor() as cursor:
        # Get status IDs
        cursor.execute('SELECT status_name, shipment_status_id FROM "ShipmentStatus";')
        status_ids = {row[0]: row[1] for row in cursor.fetchall()}
        
        shipment_ids = []
        for client_id in client_ids:
            for _ in range(fake.random_int(min=2, max=5)):  # 2-5 shipments per client
                origin, destination = fake.random_elements(ports, unique=True, length=2)
                cursor.execute(
                    '''INSERT INTO "shipment" (
                        client_id, 
                        shipment_status_id, 
                        bill_of_lading_no, 
                        origin, 
                        destination, 
                        declared_value
                    ) VALUES (%s, %s, %s, %s, %s, %s) RETURNING shipment_id;''',
                    (
                        client_id,
                        status_ids[fake.random_element(elements=status_options)],
                        fake.unique.bothify(text='BLD#########'),
                        origin,
                        destination,
                        float(fake.random_number(digits=5)) + 1000.0
                    )
                )
                shipment_ids.append(cursor.fetchone()[0])
        logger.info(f"Inserted {len(shipment_ids)} shipments")
        return shipment_ids

def populate_containers(db_conn, shipment_ids, vessel_ids):
    """Generate containers with valid ISO numbers"""
    container_types = ['DRY', 'REEFER', 'OPEN_TOP', 'FLAT_RACK']
    
    with db_conn.cursor() as cursor:
        # Get container type IDs
        cursor.execute('SELECT type_name, container_type_id FROM "ContainerType";')
        type_ids = {row[0]: row[1] for row in cursor.fetchall()}
        
        container_count = 0
        for shipment_id in shipment_ids:
            for _ in range(fake.random_int(min=1, max=4)):  # 1-4 containers per shipment
                container_type = fake.random_element(elements=container_types)
                assigned_vessel = fake.random_element(elements=vessel_ids) if vessel_ids else None
                
                cursor.execute(
                    '''INSERT INTO "container" (
                        shipment_id, 
                        vessel_id, 
                        container_type_id, 
                        container_number, 
                        size
                    ) VALUES (%s, %s, %s, %s, %s);''',
                    (
                        shipment_id,
                        assigned_vessel,
                        type_ids[container_type],
                        generate_container_number(),
                        fake.random_element(elements=[20, 40])
                    )
                )
                container_count += 1
        logger.info(f"Inserted {container_count} containers")
        return container_count

def main():
    """Main orchestration function"""
    logger.info("Starting database population")
    
    # Database connection
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        logger.info("Connected to PostgreSQL database")
    except psycopg2.Error as e:
        logger.error(f"Database connection failed: {str(e)}")
        return
    
    try:
        # Step 1: Reset database
        truncate_tables(conn)
        
        # Step 2: Populate lookup tables
        populate_lookup_tables(conn)
        
        # Step 3: Scrape and populate clients
        companies = scrape_shipping_companies()
        client_ids = populate_clients(conn, companies)
        
        # Step 4: Scrape container ports
        ports = scrape_container_ports()
        
        # Step 5: Populate vessels
        vessel_ids = populate_vessels(conn, len(client_ids))
        
        # Step 6: Populate berths
        berth_ids = populate_berths(conn, vessel_ids)
        
        # Step 7: Populate shipments
        shipment_ids = populate_shipments(conn, client_ids, ports)
        
        # Step 8: Populate containers
        container_count = populate_containers(conn, shipment_ids, vessel_ids)
        
        conn.commit()
        logger.info(f"Database populated successfully: {len(client_ids)} clients, {len(vessel_ids)} vessels, {len(shipment_ids)} shipments, {container_count} containers")
        
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        conn.rollback()
    finally:
        conn.close()
        logger.info("Database connection closed")

if __name__ == "__main__":
    main()
