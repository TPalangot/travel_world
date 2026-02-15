import mysql.connector

def get_server_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="DIA@19sql"
    )

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="DIA@19sql",
        database="travel_world"
    )
