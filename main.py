import json
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
from fastapi import FastAPI, Depends
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi.responses import HTMLResponse, RedirectResponse
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import requests
from fastapi.security import (
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
    SecurityScopes,
)

sql_user = os.environ["suser"]
sql_host = os.environ["shost"]
sql_pass = os.environ["spassword"]
mongodb_url = os.environ["mongodb_url"]

# Google OAuth2 credentials
GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]

GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="https://accounts.google.com/o/oauth2/auth",
    tokenUrl="https://oauth2.googleapis.com/token",
    scopes={'openid': 'OpenID Connect', 'email': 'Access to your email address', 'profile': 'Access to your basic profile'},
)



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



# LOGIN

'''

the login endpoint redirects the user to the Google OAuth2 login page. After the user logs in and grants permission to the application, Google redirects the user back to the callback endpoint with an authorization code. The callback endpoint then exchanges the authorization code for an access token using Google's OAuth2 API.
 The access token is then verified with Google and if the user is authenticated, the id_info variable contains the user's information. Finally, the protected_route endpoint requires an authenticated user and the token parameter is automatically validated by the oauth2_scheme dependency.
'''
@app.get("/login")
async def login():
    # Redirect user to Google OAuth2 login page
    return RedirectResponse(
        url=f"https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id={GOOGLE_CLIENT_ID}&redirect_uri=http://127.0.0.1:8000/callback&scope=openid%20email%20profile")
@app.get("/callback", response_class=HTMLResponse)
def callback(code: str, error: str = None):
    if error:
        return f"<h1>Error: {error}</h1>"
    else:
        # Exchange authorization code for access token
        data = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": "http://127.0.0.1:8000/callback", # might need to change this
            "grant_type": "authorization_code"
        }
        token_response = requests.post("https://oauth2.googleapis.com/token", data=data)
        token_data = token_response.json()
        # print(token_data)
        access_token = token_data["id_token"]

        #SOMETHING CAN BE DONE WITH THE TOKEN HERE, ITS PAYLOAD IS IMPORTANT

        # Verify access token with Google
        id_info = id_token.verify_oauth2_token(access_token, google_requests.Request(), GOOGLE_CLIENT_ID)
        # id_info contains the user's information, can be used to check if user exist in database
        # User is authenticated, do something with id_info
        # print(id_info)
        return (json.dumps(id_info)) #id_info is a dictionary of all the user's info


@app.get("/protected")
def protected_route(token: str = Depends(oauth2_scheme)):
    # User is authenticated, do something with token
    return {"Hello": "Authenticated User!"}

#USer existance check

# POSTGRES
@app.get("/userexists/{username}")
async def user_exists(username: str):
    try:
        cursor.execute("SELECT * FROM user_details.user_details WHERE username = %s", (username))
        item = cursor.fetchone()
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        else:
            return {"message": "User exists"}
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL", error)
        raise HTTPException(status_code=500, detail="Internal Server Error")



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
        raise HTTPException(status_code=500, detail="Internal Server Error")

# Get user Info from the database

@app.get("/getuser/{username}")
async def get_user(username: str):
    try:
        cursor.execute("SELECT * FROM user_details.user_details WHERE username = %s", (username))
        item = cursor.fetchone()
        return {"username": item[0], "email": item[1], "Firstname": item[2], "Lastname": item[3]}
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL", error)
        raise HTTPException(status_code=500, detail="Internal Server Error")

# Update user Info in the database
@app.put("/updateuser/{username}")
async def update_user(username: str, item: Item):
    try:
        cursor.execute("UPDATE user_details.user_details SET email = %s, Firstname = %s, Lastname = %s WHERE username = %s", (item.email, item.Firstname, item.Lastname, username))
        connection.commit()
        return {"message": "User updated successfully"}
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL", error)
        raise HTTPException(status_code=500, detail="Internal Server Error")


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
        raise HTTPException(status_code=500, detail="Internal Server Error, User not added")

#
@app.get("/getusermongo/{username}")
async def get_user_mongo(username: str):
    try:
        if (result := await db.user_details.find_one({"username": username})) is not None:
            return result
        else:
            raise HTTPException(status_code=404, detail="Item not found")
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Internal Server Error")


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
            raise HTTPException(status_code=500, detail="Internal Server Error")

#
#
#
#
#
#
#
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)








