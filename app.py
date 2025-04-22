import os
import json
import streamlit as st
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import plotly.express as px
import folium
from streamlit_folium import st_folium
import time

# Load environment variables
load_dotenv()

# API configurations
PALMETTO_API_KEY = os.getenv('PALMETTO_API_KEY')
BAYOU_API_KEY = os.getenv('BAYOU_API_KEY')
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
BAYOU_DOMAIN = "staging.bayou.energy"

# API URLs
PALMETTO_BASE_URL = "https://ei.palmetto.com/api/v0/bem/calculate"
BAYOU_BASE_URL = f"https://{BAYOU_DOMAIN}/api/v2"

def get_onboarding_token(customer_id):
    """Get onboarding token for the customer"""
    try:
        response = requests.get(
            f"{BAYOU_BASE_URL}/customers/{customer_id}",
            auth=(BAYOU_API_KEY, '')
        )
        response.raise_for_status()
        return response.json().get("onboarding_token"), None
    except requests.exceptions.RequestException as e:
        return None, f"Error getting onboarding token: {str(e)}"

def create_bayou_customer():
    """Create a new customer in Bayou"""
    try:
        response = requests.post(
            f"{BAYOU_BASE_URL}/customers",
            json={
                "utility": "pacific_gas_and_electric",
                "email": "test@example.com"  # Required field
            },
            auth=(BAYOU_API_KEY, '')
        )
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as e:
        return None, f"Error creating Bayou customer: {str(e)}"

def get_bayou_data(customer_id):
    """
    Get billing data from Bayou
    """
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {BAYOU_API_KEY}"
    }
    
    try:
        # Check customer status and wait for data to be ready
        st.write("Checking if utility data is ready...")
        while True:
            status_response = requests.get(
                f"{BAYOU_BASE_URL}/customers/{customer_id}",
                auth=(BAYOU_API_KEY, '')
            )
            status_response.raise_for_status()
            customer_status = status_response.json()
            
            # Debug print for status
            print("\n=== Bayou Customer Status ===")
            print(json.dumps(customer_status, indent=2))
            
            if customer_status.get("bills_are_ready"):
                st.success("Utility data is ready!")
                break
                
            st.info("Waiting for utility data to be processed...")
            time.sleep(5)  # Wait for 5 seconds before checking again
        
        # Now get the bills
        bills_response = requests.get(
            f"{BAYOU_BASE_URL}/customers/{customer_id}/bills",
            auth=(BAYOU_API_KEY, '')
        )
        bills_response.raise_for_status()
        bills = bills_response.json()
        
        # Debug print for bills
        print("\n=== Bayou Bills Data ===")
        print(json.dumps(bills, indent=2))
        
        return {
            "bills": bills
        }, None
    except requests.exceptions.RequestException as e:
        return None, f"Error fetching Bayou data: {str(e)}"

def get_energy_insights(payload):
    """
    Get energy insights from Palmetto Energy Insights API
    """
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "X-API-Key": PALMETTO_API_KEY
    }
    
    try:
        response = requests.post(PALMETTO_BASE_URL, json=payload, headers=headers)
        response.raise_for_status()
        return parse_response(response.text), None
    except requests.exceptions.RequestException as e:
        if hasattr(e.response, 'json'):
            st.write("Palmetto API Error Details:", e.response.json())
        return None, f"Error fetching data: {str(e)}"

def parse_response(json_string):
    """
    Parse the Palmetto API response following the demo implementation
    """
    parsed = json.loads(json_string)
    predictions = {}
    for prediction_dict in parsed['data']['intervals']:
        month = datetime.fromisoformat(prediction_dict['from_datetime']).strftime('%B')
        predictions[month] = prediction_dict['value']
    return predictions

def get_address_suggestions(query):
    """Get address suggestions from Google Maps Places Autocomplete API"""
    if not query:
        return []
    
    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {
        "input": query,
        "key": GOOGLE_MAPS_API_KEY,
        "components": "country:us",
        "types": "address"  # Only return addresses
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        predictions = response.json().get("predictions", [])
        
        # Get full details for each prediction
        suggestions = []
        for prediction in predictions:
            place_id = prediction["place_id"]
            details_url = "https://maps.googleapis.com/maps/api/place/details/json"
            details_params = {
                "place_id": place_id,
                "key": GOOGLE_MAPS_API_KEY,
                "fields": "formatted_address,geometry"
            }
            
            details_response = requests.get(details_url, params=details_params)
            details_response.raise_for_status()
            place_details = details_response.json().get("result", {})
            
            if place_details:
                suggestions.append({
                    "address": place_details["formatted_address"],
                    "lat": place_details["geometry"]["location"]["lat"],
                    "lng": place_details["geometry"]["location"]["lng"]
                })
        return suggestions
    except Exception as e:
        st.error(f"Error fetching address suggestions: {str(e)}")
        return []

def check_palmetto_service_area(lat, lon, postal_code):
    """
    Check if Palmetto services the area
    """
    headers = {
        "accept": "application/json",
        "X-API-Key": PALMETTO_API_KEY
    }
    
    try:
        url = f"{PALMETTO_BASE_URL}/service-area"
        params = {
            "lat": lat,
            "lon": lon,
            "postalCode": postal_code
        }
        
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as e:
        if hasattr(e.response, 'json'):
            st.write("Palmetto Service Area API Error Details:", e.response.json())
        return None, f"Error checking service area: {str(e)}"

def parse_bayou_to_palmetto(bayou_data):
    """
    Parse Bayou data into Palmetto's preferred format
    """
    if not bayou_data or "bills" not in bayou_data:
        return None, "No bills data available"
    
    try:
        # Debug print to see the structure
        print("\n=== Bayou Data Structure ===")
        print(json.dumps(bayou_data, indent=2))
        
        # Get address from the first bill's electric meter
        first_bill = bayou_data["bills"][0]
        if "meters" not in first_bill:
            return None, "No meters found in bills"
            
        # Find the electric meter for address
        electric_meter = None
        for meter in first_bill["meters"]:
            if meter.get("type") == "electric":
                electric_meter = meter
                break
                
        if not electric_meter or "address" not in electric_meter:
            return None, "No electric meter with address found"
            
        address = electric_meter["address"]
        # Format the full address string
        address_str = f"{address['line_1']}"
        if address.get('line_2'):
            address_str += f" {address['line_2']}"
        address_str += f", {address['city']}, {address['state']} {address['postal_code']}"
        
        print(f"\nFormatted Address: {address_str}")
        
        # Create the base payload structure
        payload = {
            "parameters": {
                "from_datetime": "2025-01-01T00:00:00",
                "to_datetime": "2025-12-31T23:59:59",
                "variables": ["consumption.electricity"],
                "group_by": "month"
            },
            "location": {
                "address": address_str
            }
        }
        
        # Add consumption data
        actuals = []
        for bill in bayou_data["bills"]:
            if "electricity_consumption" in bill:  # First check if bill has consumption
                # Find the electric meter in each bill
                for meter in bill.get("meters", []):
                    if (meter.get("type") == "electric" and 
                        meter.get("billing_period_from") and 
                        meter.get("billing_period_to")):
                        actuals.append({
                            "from_datetime": meter["billing_period_from"],
                            "to_datetime": meter["billing_period_to"],
                            "variable": "consumption.electricity",
                            "value": float(bill["electricity_consumption"])/1000
                        })
                        break  # Only take the first electric meter reading
        
        if actuals:
            payload["consumption"] = {
                "actuals": actuals
            }
        
        # Debug print the final payload
        print("\n=== Final Palmetto Payload ===")
        print(json.dumps(payload, indent=2))
        
        return payload, None
    except Exception as e:
        print(f"\nError in parse_bayou_to_palmetto: {str(e)}")
        return None, f"Error parsing Bayou data: {str(e)}"

def display_results(monthly_predictions):
    """Display the energy insights in a user-friendly format"""
    st.header("Energy Insights")
    
    if monthly_predictions:
        # Calculate and display annual total first
        annual_total = sum(monthly_predictions.values())
        st.metric(
            label="Predicted Annual Energy Usage",
            value=f"{annual_total:.2f} kWh"
        )
        
        # Create a bar chart of monthly predictions
        st.subheader("Monthly Usage Prediction Trend")
        fig = px.bar(
            x=list(monthly_predictions.keys()),
            y=list(monthly_predictions.values()),
            labels={"x": "Month", "y": "Predicted Usage (kWh)"},
            title="Monthly Energy Usage Predictions"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Display monthly predictions in a table
        st.subheader("Monthly Energy Usage Predictions")
        df_data = {
            "Month": list(monthly_predictions.keys()),
            "Predicted Usage (kWh)": [f"{usage:.2f}" for usage in monthly_predictions.values()]
        }
        st.dataframe(
            data=df_data,
            use_container_width=True
        )
    
    # Display recommendations
    st.subheader("Recommendations")
    st.write("Based on your energy profile, here are some general recommendations:")
    recommendations = [
        "Consider solar installation based on your usage pattern",
        "Implement energy-efficient lighting",
        "Optimize HVAC scheduling",
        "Monitor peak usage times"
    ]
    for i, rec in enumerate(recommendations, 1):
        st.write(f"{i}. {rec}")

def main():
    st.title("Business Energy Insights Tool")
    
    # Initialize session state variables if not already set
    if "pg_form_completed" not in st.session_state:
        st.session_state.pg_form_completed = False
    if "bayou_data" not in st.session_state:
        st.session_state.bayou_data = None
    if "pg_skipped" not in st.session_state:
        st.session_state.pg_skipped = False
    if "onboarding_link" not in st.session_state:
        st.session_state.onboarding_link = None
    if "address_confirmed" not in st.session_state:
        st.session_state.address_confirmed = False
    if "selected_address" not in st.session_state:
        st.session_state.selected_address = None
    
    # P&G Connection Section
    if not st.session_state.pg_form_completed:
        st.header("P&G Connection")
        st.write("Connect to P&G to automatically retrieve your energy usage data, or skip to proceed.")
        
        col1, col2 = st.columns(2)
        
        # Only show the initial buttons if we haven't started the process
        if st.session_state.onboarding_link is None and not st.session_state.pg_skipped:
            with col1:
                if st.button("Connect to P&G"):
                    if not BAYOU_API_KEY:
                        st.error("Bayou API key is missing. Please check your configuration.")
                    else:
                        try:
                            # Create Bayou customer
                            customer_data, error = create_bayou_customer()
                            if error:
                                st.error(error)
                            else:
                                st.session_state.bayou_customer = customer_data
                                onboarding_link = customer_data.get("onboarding_link")
                                if onboarding_link:
                                    st.session_state.onboarding_link = onboarding_link
                                    st.rerun()
                                else:
                                    st.error("Failed to get onboarding link from Bayou")
                        except Exception as e:
                            st.error(f"Error creating Bayou customer: {str(e)}")
            
            with col2:
                if st.button("Skip P&G Connection"):
                    st.session_state.pg_skipped = True
                    st.session_state.pg_form_completed = True
                    st.rerun()
        
        # If we have an onboarding link, show it and the Completed Form button
        if st.session_state.onboarding_link:
            st.info(f"""
            Please complete your P&G login using this link:
            {st.session_state.onboarding_link}
            """)
            
            st.info("Once you've completed the login form and see the success message, click the button below.")
            
            if st.button("Completed Form"):
                customer_id = st.session_state.bayou_customer.get("id")
                if customer_id:
                    try:
                        response = requests.get(
                            f"{BAYOU_BASE_URL}/customers/{customer_id}",
                            auth=(BAYOU_API_KEY, '')
                        )
                        response.raise_for_status()
                        customer_status = response.json()
                        
                        if customer_status.get("has_filled_credentials"):
                            st.success("P&G connection successful!")
                            
                            # Get Bayou data
                            bayou_data, error = get_bayou_data(customer_id)
                            if error:
                                st.error(error)
                            else:
                                st.session_state.bayou_data = bayou_data
                                st.session_state.pg_form_completed = True
                                st.success("Successfully retrieved your utility data!")
                                st.rerun()
                        else:
                            st.warning("It seems the login form hasn't been completed yet. Please complete the form and try again.")
                    except requests.exceptions.RequestException as e:
                        st.error(f"Error checking connection status: {str(e)}")
                else:
                    st.error("No customer ID found. Please try connecting again.")
    
    # Energy Insights Section
    if st.session_state.pg_form_completed:
        st.header("Energy Insights")
        
        if st.button("Generate Insights"):
            if not PALMETTO_API_KEY:
                st.error("Palmetto API key is missing. Please check your configuration.")
            else:
                try:
                    # Parse Bayou data into Palmetto format
                    if st.session_state.bayou_data:
                        payload, error = parse_bayou_to_palmetto(st.session_state.bayou_data)
                        if error:
                            st.error(error)
                            return
                    else:
                        st.error("No utility data available. Please connect to P&G first.")
                        return
                    
                    # Get energy insights
                    insights, error = get_energy_insights(payload)
                    if error:
                        st.error(error)
                    else:
                        # Display results
                        display_results(insights)
                        
                except Exception as e:
                    st.error(f"Error getting energy insights: {str(e)}")

if __name__ == "__main__":
    main() 