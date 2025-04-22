# Small Business Energy Insights Tool

This tool helps small business owners understand their energy usage and get actionable insights using the Palmetto API. By simply entering your business address, you can get detailed energy metrics and recommendations for energy savings.

## Features

- Address-based energy metrics lookup
- Solar potential assessment
- Energy usage visualization
- Actionable recommendations for energy savings
- Simple and intuitive web interface

## Setup

1. Clone this repository
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a Palmetto API account and get your API key from https://api.palmetto.com
4. Copy your API key to the `.env` file:
   ```
   PALMETTO_API_KEY=your_api_key_here
   ```

## Running the Application

To start the application, run:
```bash
streamlit run app.py
```

The application will open in your default web browser. Enter your business address to get started!

## Data Sources

This tool uses the Palmetto API to fetch energy metrics and solar potential data. The recommendations are generated based on the energy usage patterns and solar potential of your property.

## Privacy

This application only stores the necessary data to provide you with energy insights. No personal information is stored or shared with third parties.

## Support

For any issues or questions, please open an issue in the repository or contact the maintainers. 