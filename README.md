# NC ABC Inventory Alert Bot

[![Python application](https://github.com/droneshire/whiskey_inventory_alert_upwork/actions/workflows/python-app.yml/badge.svg)](https://github.com/droneshire/whiskey_inventory_alert_upwork/actions/workflows/python-app.yml)

Track drink inventory and alert to various users via text when new inventory comes on the market.

There are two parts to this project, a frontend and a backend. This project represents the backend.

# Backend: Inventory Monitoring and SMS Alerts

## Inventory Monitoring

- Inventory is monitored from this [site](https://abc.nc.gov/StoresBoards/Stocks)
- Inventory is updated every 15 minutes
- Inventory can be exported to CSV vie the following endpoint: https://abc.nc.gov/StoresBoards/ExportData
- CSV contains drink items. Each item is identified by a six digit code.

This script monitors the inventory and creates alerts based on a mapping of clients to drink items. Alerts will be determined by the heuristic of specified inventory going from sold out (qty 0) to various non-zero values. In other words, when inventory goes from out of stock to in stock for specified items.

The alert system is done using [Twilio](https://www.twilio.com/en-us/pricing) and sends the text message alert to the associated client. The initial setup will be pay as you go plan on Twilio, and should be fairly reasonable costwise.

## Setup

### Gmail

We use [`yagmail`](https://mailtrap.io/blog/yagmail-tutorial/) to send emails. This requires the credentials of a gmail account to send on behalf of.

You'll store the email address and password in the `.env` file below. Recommendation is to create a new gmail account for this purpose.

### Twilio

Set up a Twilio account for the SMS alerts.

https://www.twilio.com/try-twilio

You'll need the `SID`, `AUTH_TOKEN`, and phone number down below.

### Host Machine

Set up a linux device to deploy the inventory manager bot to.



### Config Files

- **`.env`**

Create a `.env` file and either upload it to the root of the repo or create it directly there with the following contents:

You'll need to replace anything within the `<>` with valid string entries e.g. `ADMIN_NAME="John Doe"`

```
DEFAULT_DB="inventory_manager.db"

# Configure the Twilio SMS provider.
TWILIO_FROM_SMS_NUMBER="<INSERT YOUR TWILIO SMS NUMBER HERE>"
TWILIO_AUTH_TOKEN="<INSERT YOUR TWILIO AUTH TOKEN HERE>"
TWILIO_ACCOUNT_SID="<INSERT YOUR TWILIO ACCOUNT SID HERE>"


# Test account to use for testing
TEST_CLIENT_NAME="<INSERT YOUR TEST CLIENT NAME HERE>"
TEST_CLIENT_PHONE="<INSERT YOUR TEST CLIENT PHONE NUMBER HERE>"
TEST_CLIENT_EMAIL="<INSERT YOUR TEST CLIENT EMAIL HERE>"

# Admin settings
ADMIN_NAME="<INSERT YOUR ADMIN NAME HERE>"
ADMIN_PHONE="<INSERT YOUR ADMIN PHONE NUMBER HERE>"
ADMIN_EMAIL="<INSERT YOUR ADMIN EMAIL HERE>"
ADMIN_EMAIL_PASSWORD="<INSERT YOUR ENCRYPTED ADMIN EMAIL PASSWORD HERE>"

# Firebase settings
GOOGLE_APPLICATION_CREDENTIALS="firebase_service_account.json"

```

- **`firebase_service_account.json`**

Finally, add a `firebase_service_account.json` to the repo `config` directory. The contents of this file can be found [here](https://console.firebase.google.com/u/0/project/inventory-860f0/settings/serviceaccounts/adminsdk).

# Database

The client/drink database will be a sqlite backed Firebase database that will be integrated into a web frontend that will allow clients to configure their settings as desired.

![image](https://user-images.githubusercontent.com/2355438/233558659-06ae0128-f788-4f0f-a594-2b26f459d32e.png)

In this script, the database will be accessed using [Firebase authenticated API calls](https://firebase.google.com/docs/auth/web/start) and will listen to database changes made by the user on the frontend website.

User will also be able to edit the database directly in the Firebase service manager in addition to making changes directly through the website.

The bot also has a local database that can either be used as the source of truth (using the `--use-local-db` argument), or will mirror what is seen in Firebase. This provides some redundancy and allows for easy migration should we switch DB hosts in the future.

# Frontend: Assign Inventory Watch to Clients

The Firebase backed frontend is a separate repo of a React/Typescript based website.

The frontend has a simple interface that will require Google authentication to access. It allows the user to input new clients, their contact info, and the associated product codes to watch and alert on.

Repo can be found here: https://github.com/droneshire/whiskey_inventory_firebase_client

## Icons

- https://abc.nc.gov/Images/Icons/ABC%20Warehouse%20Icon.png
- https://abc.nc.gov/Images/ABCImagePanel.png

# Hosting

The backend can be hosted on any server that supports python3 and has internet access. General backend setup will be the responsibility of the host so cost and maintenance are beyond the scope of this project. My recommendation is using a Digital Ocean Droplet for about $6/month. Setup is quick and easy.

The frontend will be a Firebase web app, so hosting will be managed through Google's Firebase hosting service (which is free as long as database access is reasonable, on the order of less than 1000 per day).
