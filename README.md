# Drink Inventory Alert Bot

Track drink inventory and alert to various users via text when new inventory comes on the market.

There are two parts to this project, a frontend and a backend. This project represents the backend.

## Backend: Inventory Monitoring and SMS Alerts

![image](https://user-images.githubusercontent.com/2355438/233558659-06ae0128-f788-4f0f-a594-2b26f459d32e.png)


### Inventory Monitoring
- Inventory is monitored from this [site](https://abc.nc.gov/StoresBoards/Stocks)
- Inventory is updated every 15 minutes
- Inventory can be exported to CSV vie the following endpoint: https://abc.nc.gov/StoresBoards/ExportData
- CSV contains drink items. Each item is identified by a six digit code. 

This script monitors the inventory and creates alerts based on a mapping of clients to drink items. 

The alert system is done using [Twilio](https://www.twilio.com/en-us/pricing) and sends the text message alert to the associated client. The initial setup will be pay as you go plan on Twilio, and should be fairly reasonable costwise. 

## Database
The client/drink database will be a sqlite backed Firebase database that will be integrated into a web frontend that will allow

In this script, the database will be accessed using [Firebase authenticated API calls](https://firebase.google.com/docs/auth/web/start) and will listen to database changes made by the user on the frontend website.

## Frontend: Assign Inventory Watch to Clients
The Firebase backed frontend will be a separate repo of a React/Typescript based website. Link to be provided once it is developed.

The frontend will have a simple interface, that will require Google authentication to access. 

It will allow the user to input new clients, their contact info, and the associated product codes to watch and alert on.

## Hosting

The backend can be hosted on any server that supports `python3` and has internet access. General backend setup will be the responsibility of the host so cost and maintenance are beyond the scope of this project. 

The frontend will be a Firebase web app, so hosting will be managed through Google's Firebase hosting service (which is free as long as database access is reasonable, on the order of less than 1000 per day).
