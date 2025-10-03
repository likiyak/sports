import firebase_admin
from firebase_admin import credentials, firestore
import os
import requests
from bs4 import BeautifulSoup
from http.server import BaseHTTPRequestHandler
import json

# --- CONFIGURATION ---
# Vercel handles environment variables securely. Set these in your Vercel Project Settings.
# 1. GOOGLE_APPLICATION_CREDENTIALS_JSON: The entire content of your serviceAccountKey.json file.
# 2. APP_ID: Your application's ID.

APP_ID = os.environ.get('APP_ID', 'default-app-id')

# --- Firebase Initialization ---
db = None
try:
    # Vercel will use the GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable
    # if it's set in the project settings. This is more secure than including the file.
    if 'GOOGLE_APPLICATION_CREDENTIALS_JSON' in os.environ:
        creds_json = json.loads(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_JSON'))
        cred = credentials.Certificate(creds_json)
    else:
        # Fallback for local development if you still have the file
        FIREBASE_CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), '..', 'serviceAccountKey.json')
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
        
    db = firestore.client()
    print("Firebase initialized successfully.")

except Exception as e:
    print(f"Error initializing Firebase: {e}")


def scrape_sports_from_web():
    # ... existing code ...
    print("Fetching list of sports from the web...")
    sports = []
    url = "https://en.wikipedia.org/wiki/List_of_sports"
    
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status() # Raise an exception for bad status codes
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all divs that contain sports lists
        sport_list_divs = soup.find_all('div', class_='div-col')
        
        for div in sport_list_divs:
            # Find all list items (li) within each div
            list_items = div.find_all('li')
            for item in list_items:
                # Get the text of the 'a' tag, which is the sport name
                sport_name = item.find('a').get_text(strip=True) if item.find('a') else None
                if sport_name:
                    sports.append(sport_name)
                    
        print(f"Successfully scraped {len(sports)} sports.")
        return list(set(sports)) # Return unique sports
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the URL: {e}")
        return []

def get_leagues_for_sport(sport_name):
    # ... existing code ...
    print(f"  -> Searching for leagues related to '{sport_name}'...")
    
    # MOCK DATA: Simulates results from a web search or sports API
    MOCK_LEAGUE_DATA = {
        "Football (Soccer)": ["Premier League", "La Liga", "Serie A", "Bundesliga", "Major League Soccer"],
        "Basketball": ["National Basketball Association (NBA)", "EuroLeague", "NBL (Australia)"],
        "Cricket": ["Indian Premier League (IPL)", "The Ashes", "Big Bash League"],
        "American Football": ["National Football League (NFL)"],
        "Ice Hockey": ["National Hockey League (NHL)", "Kontinental Hockey League (KHL)"],
        "Baseball": ["Major League Baseball (MLB)", "Nippon Professional Baseball (NPB)"],
        "Formula 1": ["Formula 1 World Championship"] # Technically a series, but fits here
    }
    
    # Return the list of leagues if the sport is in our mock database
    leagues = MOCK_LEAGUE_DATA.get(sport_name, [])
    if leagues:
        print(f"  -> Found {len(leagues)} leagues for '{sport_name}'.")
    return leagues

def update_database_with_scraped_data(sports_list):
    # ... existing code ...
    if not db:
        print("Firestore is not initialized. Cannot populate data.")
        return {"sports_added": 0, "leagues_added": 0, "message": "Firestore not initialized."}

    print("\nConnecting to Firestore to update sports and leagues...")
    public_data_path = f'artifacts/{APP_ID}/public/data'
    sports_collection = db.collection(public_data_path, 'sports')
    leagues_collection = db.collection(public_data_path, 'leagues')
    
    existing_sports_docs = sports_collection.stream()
    existing_sports_names = [doc.to_dict().get('name', '') for doc in existing_sports_docs]
    
    sports_added_count = 0
    leagues_added_count = 0

    for sport_name in sports_list:
        if sport_name not in existing_sports_names:
            try:
                # --- Step 1: Add the new sport ---
                new_sport_data = {
                    'name': sport_name,
                    'description': f'The sport of {sport_name}.',
                    'iconUrl': '' 
                }
                # Add the sport and get its new document reference
                update_time, sport_ref = sports_collection.add(new_sport_data)
                print(f"- Added '{sport_name}' to the database (ID: {sport_ref.id}).")
                sports_added_count += 1

                # --- Step 2: Find and add leagues for this new sport ---
                leagues = get_leagues_for_sport(sport_name)
                for league_name in leagues:
                    new_league_data = {
                        'sportId': sport_ref.id, # Link back to the sport
                        'name': league_name,
                        'country': '', # A more advanced AI would find this
                        'logoUrl': ''
                    }
                    leagues_collection.add(new_league_data)
                    print(f"    - Added league: '{league_name}'")
                    leagues_added_count += 1

            except Exception as e:
                print(f"  - Error processing '{sport_name}': {e}")
    
    message = f"Finished. Added {sports_added_count} new sports and {leagues_added_count} new leagues to Firestore."
    print(message)
    return {"sports_added": sports_added_count, "leagues_added": leagues_added_count, "message": message}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """
        This function is executed when the /api/collector URL is accessed.
        """
        try:
            sports_to_add = scrape_sports_from_web()
            if sports_to_add:
                result = update_database_with_scraped_data(sports_to_add)
            else:
                result = {"sports_added": 0, "leagues_added": 0, "message": "Scraping returned no sports to add."}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
