# FinanceReporting

A Flask app that provides reporting to the DxE Finance team. Live at http://finance-reporting.dxe.io.

## Requirements
- Python 3.6 or later
- Access to the finance database

## Local development
1. Clone this repo.
2. Create a virtual enviornment: ```python3 -m venv venv```
3. Activate that environment: ```. venv/bin/activate```
4. Install requirements: ```pip install -r requirements.txt```
5. Copy ```.env-temp``` to ```.env``` and fill in your secrets.
    - ```GOOGLE_OAUTH_CLIENT_ID``` see https://console.developers.google.com/apis/credentials
    - ```GOOGLE_OAUTH_CLIENT_SECRET```
    - ```FLASK_SECRET_ID``` a long random string of your choice
    - ```DB_IP``` database IP to connect to
    - ```DB``` database name to connect to
    - ```DB_USER``` database username
    - ```DB_PASSWORD``` database password
    - Paths to ssl keys for mysql
6. Run the app: ```flask run```

## Deploying changes
1. SSH into ec2.dxe.io
2. ```cd /var/www/FinanceReporting/FinanceReporting```
3. ```git pull```
4. ```sudo apachectl restart```
