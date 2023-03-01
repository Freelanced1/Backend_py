import logging
import os
import uuid
import psycopg2
from fastapi import FastAPI, Request, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sql_user = os.environ["suser"]
sql_host = os.environ["shost"]
sql_pass = os.environ["spassword"]

app = FastAPI(
    title="Freelanced",
    description="User Registraion and Info API",
    version="0.1.1",
    openapi_url="/api/v0.1.1/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    connection = psycopg2.connect(user=sql_user,
                                  password=sql_pass,
                                  host=sql_host,
                                  port="5432",
                                  database="postgres")
    cursor = connection.cursor()
except (Exception, psycopg2.Error) as error:
    print("Error while connecting to PostgreSQL", error)

class Item(BaseModel):
    username: str = Query(...)
    email: str = Query(...)
    Firstname: str = Query(...)
    Lastname: str = Query(...)

# Add a new user to the database

@app.post("/newuser")
async def new_user(item: Item, background_tasks: BackgroundTasks):
    try:
        cursor.execute("INSERT INTO user_details.user_details (username, email, Firstname, Lastname) VALUES (%s, %s, %s, %s)", (item.username, item.email, item.Firstname, item.Lastname))
        connection.commit()
        count = cursor.rowcount
        print(count, "Record inserted successfully into users table")
        return {"message": "User added successfully"}
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL", error)
        return {"message": "User not added"}

# Get user Info from the database

@app.get("/getuser/{username}")
async def get_user(username: str):
    try:
        cursor.execute("SELECT * FROM user_details.user_details WHERE username = %s", (username))
        item = cursor.fetchone()
        return {"username": item[0], "email": item[1], "Firstname": item[2], "Lastname": item[3]}
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL", error)
        return {"message": "User not found"}

# Update user Info in the database
@app.put("/updateuser/{username}")
async def update_user(username: str, item: Item):
    try:
        cursor.execute("UPDATE user_details.user_details SET email = %s, Firstname = %s, Lastname = %s WHERE username = %s", (item.email, item.Firstname, item.Lastname, username))
        connection.commit()
        return {"message": "User updated successfully"}
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL", error)
        return {"message": "User not updated"}










