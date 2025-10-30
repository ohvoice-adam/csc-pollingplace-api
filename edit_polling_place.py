#!/usr/bin/env python3
"""
Helper script to edit specific polling place records in the database.
Usage: python3 edit_polling_place.py <polling_place_id>
"""

import sys
from app import app, db, PollingPlace

def edit_polling_place(polling_place_id):
    """Edit a specific polling place record"""
    
    with app.app_context():
        # Find the polling place
        place = PollingPlace.query.filter_by(id=polling_place_id).first()
        
        if not place:
            print(f"Polling place with ID '{polling_place_id}' not found")
            return False
        
        print(f"Current polling place: {place.id}")
        print(f"  Name: {place.name}")
        print(f"  Address: {place.address_line1}")
        print(f"  City: {place.city}, {place.state} {place.zip_code}")
        print(f"  Current coordinates: {place.latitude}, {place.longitude}")
        print(f"  County: {place.county}")
        print(f"  Source: {place.source_plugin}")
        
        print("\nWhat would you like to edit?")
        print("1. Latitude")
        print("2. Longitude") 
        print("3. Address line 1")
        print("4. City")
        print("5. County")
        print("6. All coordinates (lat/lon)")
        print("0. Cancel")
        
        try:
            choice = input("\nEnter choice (0-6): ").strip()
            
            if choice == '1':
                new_lat = float(input(f"Enter new latitude (current: {place.latitude}): "))
                place.latitude = new_lat
            elif choice == '2':
                new_lon = float(input(f"Enter new longitude (current: {place.longitude}): "))
                place.longitude = new_lon
            elif choice == '3':
                new_addr = input(f"Enter new address line 1 (current: {place.address_line1}): ")
                place.address_line1 = new_addr
            elif choice == '4':
                new_city = input(f"Enter new city (current: {place.city}): ")
                place.city = new_city
            elif choice == '5':
                new_county = input(f"Enter new county (current: {place.county}): ")
                place.county = new_county
            elif choice == '6':
                new_lat = float(input(f"Enter new latitude (current: {place.latitude}): "))
                new_lon = float(input(f"Enter new longitude (current: {place.longitude}): "))
                place.latitude = new_lat
                place.longitude = new_lon
            elif choice == '0':
                print("Cancelled")
                return False
            else:
                print("Invalid choice")
                return False
            
            # Save changes
            db.session.commit()
            print("\nChanges saved successfully!")
            
            # Show updated record
            print(f"\nUpdated polling place: {place.id}")
            print(f"  Coordinates: {place.latitude}, {place.longitude}")
            if hasattr(place, 'address_line1') and place.address_line1:
                print(f"  Address: {place.address_line1}")
            if hasattr(place, 'city') and place.city:
                print(f"  City: {place.city}")
            if hasattr(place, 'county') and place.county:
                print(f"  County: {place.county}")
            
            return True
            
        except (ValueError, KeyboardInterrupt):
            print("\nInvalid input or cancelled")
            return False

def search_polling_places(search_term):
    """Search for polling places"""
    
    with app.app_context():
        # Search by name, city, or ID
        places = PollingPlace.query.filter(
            (PollingPlace.id.contains(search_term)) |
            (PollingPlace.name.contains(search_term)) |
            (PollingPlace.city.contains(search_term))
        ).limit(10).all()
        
        if not places:
            print(f"No polling places found matching '{search_term}'")
            return []
        
        print(f"\nFound {len(places)} polling places:")
        for i, place in enumerate(places, 1):
            print(f"{i}. {place.id} - {place.name} ({place.city}, {place.state})")
            print(f"   Coordinates: {place.latitude}, {place.longitude}")
        
        return places

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 edit_polling_place.py <polling_place_id_or_search_term>")
        print("Examples:")
        print("  python3 edit_polling_place.py VA-00001")
        print("  python3 edit_polling_place.py 'Elementary School'")
        sys.exit(1)
    
    search_term = sys.argv[1]
    
    # Try to find exact ID match first
    place = PollingPlace.query.filter_by(id=search_term).first()
    
    if place:
        edit_polling_place(search_term)
    else:
        # Search for partial matches
        places = search_polling_places(search_term)
        if len(places) == 1:
            edit_polling_place(places[0].id)
        elif len(places) > 1:
            try:
                choice = int(input(f"\nSelect polling place (1-{len(places)}): ")) - 1
                if 0 <= choice < len(places):
                    edit_polling_place(places[choice].id)
                else:
                    print("Invalid choice")
            except (ValueError, KeyboardInterrupt):
                print("Invalid input")