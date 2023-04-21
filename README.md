# Drink Inventory Alert Bot

Track drink inventory and alert to various users via text when new inventory comes on the market.

There are two parts to this project, a frontend and a backend. This project represents the backend.

## Backend: Inventory Monitoring and SMS Alerts
- Inventory is monitored from this [site](https://abc.nc.gov/StoresBoards/Stocks)
- Inventory is updated every 15 minutes
- Inventory can be exported to CSV vie the following endpoint: https://abc.nc.gov/StoresBoards/ExportData
- CSV contains drink items. Each item is identified by a six digit code. 

This script monitors the inventory and creates alerts based on a mapping of clients to drink items. The alert system is done using Twilio and sends the text message alert to the associated client.

## Database
The client/drink database will be a sqlite backed Firebase database that will be integrated into a web frontend that will allow

In this script, the database will be accessed using [Firebase authenticated API calls](https://firebase.google.com/docs/auth/web/start) and will listen to database changes made by the user on the frontend website.

## Frontend: Assign Inventory Watch to Clients
The Firebase backed frontend will be a separate repo of a React/Typescript based website. Link to be provided once it is developed.

The frontend will have a simple interface, that will require Google authentication to access. 

It will allow the user to input new clients, their contact info, and the associated product codes to watch and alert on.
