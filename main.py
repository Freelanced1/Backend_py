import logging
import os
import uuid
import psycopg2
from fastapi import FastAPI, Request, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from fastapi import FastAPI, Body, HTTPException, status
from fastapi.responses import Response, JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId
from typing import Optional, List
import motor.motor_asyncio

sql_user = os.environ["suser"]
sql_host = os.environ["shost"]
sql_pass = os.environ["spassword"]
mongodb_url = os.environ["mongodb_url"]


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")

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

try:
    mongo_client = motor.motor_asyncio.AsyncIOMotorClient(mongodb_url)
    db = mongo_client.freelanced
except Exception as e:
    print(e)


class Item(BaseModel):
    username: str = Query(...)
    email: str = Query(...)
    Firstname: str = Query(...)
    Lastname: str = Query(...)


class User(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    username: str = Field(...)
    profile_pic: Optional[str] = Field(...)
    description: Optional[str] = Field(...)
    languages: Optional[list] = Field(...)
    experience: Optional[list] = Field(...)
    current_employer: Optional[str] = Field(...)
    education: Optional[list] = Field(...)
    skills: Optional[list] = Field(...)
    certificates: Optional[list] = Field(...)
    otherdocs: Optional[list] = Field(...)
    projects: Optional[list] = Field(...)
    awards: Optional[list] = Field(...)
    socials: Optional[list] = Field(...)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# class Recruiter(BaseModel):
#     id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
#     username: str = Field(...)
#     profile_pic: str = Field(...)
#     #More Fields#


# Add a new user to the database
@app.get("/")
async def read_root():
    return {"Hello": "World, go to /docs for the API docs"}

#USer existance check

# POSTGRES
@app.get("/userexists/{username}")
async def user_exists(username: str):
    try:
        cursor.execute("SELECT * FROM user_details.user_details WHERE username = %s", (username))
        item = cursor.fetchone()
        if item is None:
            return {"message": "User does not exist"}
        else:
            return {"message": "User exists"}
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL", error)
        return {"message": "User not found"}



@app.post("/newuser")
async def new_user(item: Item, background_tasks: BackgroundTasks):
    try:
        #Create User ID#
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


#MONGODB

# Add a new user to the database
@app.post("/newusermongo")
async def new_user_mongo(item: User):
    try:
        document = item.dict()
        result = await db.user_details.insert_one(document)
        return {"message": "User added successfully"}
    except Exception as e:
        print(e)
        return {"message": "User not added"}

#
@app.get("/getusermongo/{username}")
async def get_user_mongo(username: str):
        if (result := await db.user_details.find_one({"username": username})) is not None:
            return result
        else:
            raise HTTPException(status_code=404, detail="Item not found")
# ##UPDATE##
#
# #Search Keyword in Mongo
@app.get("/searchuserdetailsmongo/{phrase}",response_description="Stringified List of keywords seperated by comma")
async def search_mongo(phrase: str):
    keywords = list(phrase.split(","))
    try:
        for ix in keywords:

            result = await db.user_details.find({"$text": {"$search": str(ix).lower(), "$caseSensitive": False, "$diacriticSensitive": False}})
            return result
    except Exception as e:
            print(e)
            return {"message": "User not found"}

#
#
#




if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)








