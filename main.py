import json
import uuid
from typing import Optional
import certifi
import motor.motor_asyncio
import psycopg2
import requests
import uvicorn
from azure.storage.blob import BlobServiceClient
from bson import ObjectId
from fastapi import Depends, FastAPI, File, UploadFile, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2AuthorizationCodeBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from fastapi_socketio import SocketManager
from datetime import date, datetime
import socketio
import asyncio
import websockets
import time
import pymongo
import logging
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocket



#
sql_user = "freelance@postgresfreelance"
sql_host = "postgresfreelance.postgres.database.azure.com"
sql_pass = "Rogers@123"
sql_db = "postgresfreelance"
mongodb_url = "mongodb+srv://admin:admin@freelancedmongo.hthxmyp.mongodb.net/?retryWrites=true&w=majority"

# Google OAuth2 credentials
GOOGLE_CLIENT_ID = "825776228723-acjhna5u0tf3730fj8eam3vbk3irr23u.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"
connect_str = "DefaultEndpointsProtocol=https;AccountName=freelancedblob;AccountKey=/mBfa3fVMqhs1A185qC/pcJdhEwX6KqJ5kV0nVhYzgYY8NqRZu/0qCfVUj6izMZE1DoVIUAf3+9Z+AStqdl8qg==;EndpointSuffix=core.windows.net"


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



# Initialize the SocketManager
socket_manager = SocketManager(app=app, cors_allowed_origins="*")

# socket_manager = SocketManager(app=app,cors_allowed_origins="*", mount_location='/ws')
# sio = socketio.Client()


try:
    connection = psycopg2.connect(user=sql_user,
                                  password=sql_pass,
                                  host=sql_host,
                                  port="5432",
                                  database="postgres")
    print("connection successful")
    cursor = connection.cursor()
except (Exception, psycopg2.Error) as error:
    print("Error while connecting to PostgreSQL", error)

try:
    mongo_client = mongo_client = motor.motor_asyncio.AsyncIOMotorClient(mongodb_url,tlsCAFile= certifi.where())
    db1 = mongo_client.user
    db2 = mongo_client.recruiter
except Exception as e:
    print(e)

#connect to Blob storage
try:
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
except Exception as e:
    print(e)


class Item(BaseModel):
    email: str = Query(...)
    firstname: str = Query(...)
    lastname: str = Query(...)


class User(BaseModel):
    email: str = Query(None)
    phone: Optional[str] = Query(None)
    profile_pic: Optional[str] = Query(None)
    worksamples: Optional[list] = Query(None)
    website: Optional[str] = Query(None)
    description: Optional[str] = Query(None)
    language: Optional[str] = Query(None)
    occupation: Optional[str] = Query(None)
    experience: Optional[int] = Query(None)
    university: Optional[str] = Query(None)
    uni_country: Optional[str] = Query(None)
    uni_degree: Optional[str] = Query(None)
    uni_grad_date: Optional[str] = Query(None)
    skills: Optional[list] = Query(None)
    proficiency: Optional[list] = Query(None)
    certificates: Optional[list] = Query(None)
    payment_status: Optional[bool] = Query(None)
    payment_date: Optional[str] = Query(None)
    order_status: Optional[bool] = Query(None)
    recruiter_mail: Optional[str] = Query(None)
    ratings: Optional[int] = Query(None)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class Recruiter(BaseModel):
    email: str = Query(None)
    phone: Optional[str] = Query(None)
    profile_pic: Optional[str] = Query(None)
    language: Optional[str] = Query(None)
    occupation: Optional[str] = Query(None)
    project_area: Optional[list] = Query(None)
    project_area_details: Optional[list] = Query(None)
    documents: Optional[list] = Query(None)
    skills: Optional[list] = Query(None)
    proficiency: Optional[list] = Query(None)
    timeline: Optional[bool] = Query(None)
    deadline: Optional[str] = Query(None)
    budget: Optional[str] = Query(None)
    user_email: Optional[str] = Query(None)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


#
class Uploader(BaseModel):
    email: str = Query(...)


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
        url=f"https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id={GOOGLE_CLIENT_ID}&redirect_uri=https://freelancedit.azurewebsites.net/callback&scope=openid%20email%20profile")
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
            "redirect_uri": "https://freelancedit.azurewebsites.net/callback", # might need to change this
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
        return json.dumps({"token":access_token,"payload":id_info}) #id_info is a dictionary of all the user's info


@app.get("/protected-resource")
def protected_route(token: str = Depends(oauth2_scheme)):
    # User is authenticated, do something with token
    return {"Hello": "Authenticated User!"}

#USer existance check

# POSTGRES
@app.get("/personexists/{email}")
async def person_exists(email: str):
    try:
        cursor.execute("SELECT * FROM public.user_login_1 WHERE email = %s", (email,))
        item = cursor.fetchone()
        if item is None:
            cursor.execute("SELECT * FROM public.business_login WHERE email = %s", (email,))
            item = cursor.fetchone()
            if item is None:
                logging.info("User does not exist")
                raise HTTPException(status_code=404, detail="Item not found")

            else:
                return {"message": "Recruiter exists"}

        else:
            return {"message": "User exists"}

    except (Exception, psycopg2.Error) as error:
        logging.error(error)
        print("Error while connecting to PostgreSQL", error)
        raise HTTPException(status_code=500, detail="Internal Server Error")





# @app.get("/userexists/{email}")
# async def user_exists(email: str):
#     try:
#         cursor.execute("SELECT * FROM public.user_login_1 WHERE email = %s", (email,))
#         item = cursor.fetchone()
#         if item is None:
#             raise HTTPException(status_code=404, detail="Item not found")
#         else:
#             return {"message": "User exists"}
#
#     except (Exception, psycopg2.Error) as error:
#         print("Error while connecting to PostgreSQL", error)
#         raise HTTPException(status_code=500, detail="Internal Server Error")



@app.post("/newuser")
async def new_user(item: Item):
    try:
        print("entered")
        #Create User ID#
        cursor.execute("INSERT INTO public.user_login_1 (email, firstname, lastname) VALUES (%s, %s, %s)", (item.email, item.firstname, item.lastname,))
        print("done")
        connection.commit()
        count = cursor.rowcount
        print(count, "Record inserted successfully into users table")
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)",(now, "New User Inserted",))
        # connection.commit()
        return {"message": "User added successfully"}
    except (Exception, psycopg2.Error) as error:
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        logging.error(error)
        return{"message":error}


# Get user Info from the database
@app.post("/newrecruiter")
async def new_recruiter(item: Item, background_tasks: BackgroundTasks):
    try:
        #Create User ID#
        cursor.execute("INSERT INTO public.business_login (email, firstname, lastname) VALUES (%s, %s, %s)", (item.email, item.firstname, item.lastname,))
        connection.commit()
        count = cursor.rowcount
        print(count, "Record inserted successfully into users table")
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "New Recruiter Instered",))
        # connection.commit()
        return {"message": "User added successfully"}
    except (Exception, psycopg2.Error) as error:
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        return{"message":error}

@app.get("/getuser/{email}")
async def get_user(email: str):
    try:
        cursor.execute("SELECT * FROM public.user_login_1 WHERE email = %s", (email,))
        item = cursor.fetchone()
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")

        else:
            print(item)
            # now = datetime.today()
            # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "User Fetched",))
            # connection.commit()
            return {"email": item[0], "Firstname": item[1], "Lastname": item[2],"id":item[3]}
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL", error)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.delete("/deleteuser/{email}")  #DELETE USER
async def delete_user(email: str ):
    try:
        cursor.execute("DELETE FROM public.user_login_1 WHERE email = %s", (email,))
        connection.commit()
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "User Deleted",))
        # connection.commit()
        return ("Item Deleted")
    except psycopg2.Error as error:
        print("Error while connecting to PostgreSQL", error)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.delete("/deleteRecruiter/{email}")  #DELETE Recruiter
async def delete_recuiter(email: str ):
    try:
        cursor.execute("DELETE FROM public.business_login WHERE email = %s", (email,))
        connection.commit()
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Recruiter Deleted",))
        # connection.commit()
        return ("Item Deleted")
    except psycopg2.Error as error:
        print("Error while connecting to PostgreSQL", error)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.put("/UpdateUser/{email}")  #Update User in Postgres
async def update_user(item : Item ):
    try:
        cursor.execute("UPDATE public.user_login_1 SET firstname = %s, lastname = %s WHERE email = %s", (str(item.firstname),str(item.lastname), str(item.email),))
        connection.commit()
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "User Updated",))
        # connection.commit()
        return ("Item Updated")
    except psycopg2.Error as error:
        print("Error while connecting to PostgreSQL", error)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.put("/UpdateRecruiter/{email}")  #Update Recruiter in Postgres
async def update_user(item : Item ):
    try:
        cursor.execute("UPDATE public.business_login SET firstname = %s, lastname = %s WHERE email = %s", (str(item.firstname),str(item.lastname), str(item.email),))
        connection.commit()
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Recruiter updated",))
        # connection.commit()
        return ("Item Updated")
    except psycopg2.Error as error:
        print("Error while connecting to PostgreSQL", error)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error")


# Update user Info in the database
@app.get("/getbusiness/{email}")
async def get_buisness(email: str):
    try:
        cursor.execute("SELECT * FROM public.business_login WHERE email = %s", (email,))
        item = cursor.fetchone()
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        else:
            # now = datetime.today()
            # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Get Business",))
            # connection.commit()
            return {"email": item[0], "Firstname": item[1], "Lastname": item[2],"id":item[3]}
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL", error)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.put("/updateuser/{email}")
async def update_user(email: str,item: Item):
    try:
        cursor.execute("UPDATE public.user_login_1 SET firstname = %s, lastname = %s WHERE email = %s", (item.firstname, item.lastname,email,))
        connection.commit()
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "User Updated",))
        # connection.commit()
        return {"message": "User updated successfully"}
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL", error)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.put("/updaterecriter/{email}")
async def update_recruiter(email: str, item: Item):
    try:

        cursor.execute("UPDATE public.business_login SET firstname = %s, lastname = %s WHERE email = %s", (item.firstname, item.lastname, email,))
        connection.commit()
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Recruiter Updated",))
        # connection.commit()
        return {"message": "User updated successfully"}
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL", error)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error")


#MONGODB

#all data from mongo db2
@app.get("/allProject/")
async def allProject():
    try:
        collections = await db1.list_collection_names()
        for ix in collections:
            print(type(ix))
            collection = db2[ix]
            cursor = collection.find({})
            result = {"data": []}
            print(cursor)
            while await cursor.fetch_next:
                res = cursor.next_object()
                print(res)
                result["data"].append(res)

        return result

    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to MONGO", error)
        raise HTTPException(status_code=500, detail="Internal Server Error")


# Add a new user to the database
@app.post("/newusermongo/")
async def new_user_mongo(item: User):
    try:
        collection_name = str(item.email)
        itemx = item.dict()
        itemx["_id"] = str(ObjectId())
        await db1.create_collection(collection_name)
        collection = db1[collection_name]
        #convert skills to lower case and convert to string seperated by comma
        itemx["skills"] = [x.lower() for x in itemx["skills"]] #convert to lower case
        itemx["skills"] = ",".join(itemx["skills"]) #convert to string seperated by comma
        #convert description to lower case
        # itemx["description"] = [x.lower() for x in itemx["description"]]  # convert to lower case
        # itemx["description"] = ",".join(itemx["description"])  # convert to string seperated by comma
        await collection.insert_one(itemx)
        # save id to postgres also for future use

        # write to postgres
        cursor.execute("UPDATE public.user_login_1 SET id = %s WHERE email = %s", (str(itemx["_id"]), str(itemx["email"]),))
        connection.commit()
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "New User Inserted Mongo",))
        # connection.commit()
        return {"message": "Item created successfully & User updated successfully", "id": itemx["_id"]}

    except Exception as e:
        print(e)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error, User not added")

@app.put("/updateusermongo/")  #User Update
async def update_user_mongo(item: User, objid:str =Query(...)):
    try:
        collection_name = str(item.email)
        itemg = item.dict(exclude_unset=True)

        # itemg["_id"] = objid

        # convert skills to lower case and convert to string seperated by comma
        if "skills" in itemg.keys() and itemg["skills"] !=None:
            itemg["skills"] = [x.lower() for x in itemg["skills"]]  # convert to lower case
            itemg["skills"] = ",".join(itemg["skills"])  # convert to string seperated by comma


        collection = db1[collection_name]
    #
        await collection.update_one({"_id" : objid}, {'$set' : itemg})
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "User Updated Mongo",))
        # connection.commit()
        return {"message": "User updated successfully", "id": objid}
    except Exception as e:
        print(e)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error, User not added")



@app.put("/updateRecruitermongo/")  #Recruiter Update
async def update_recruiter_mongo(item: Recruiter, objid:str =Query(...)):
    try:
        collection_name = str(item.email)
        itemg = item.dict(exclude_unset=True)

        itemg["_id"] = objid
        # Convert project description to lower case and convert to string seperated by comma
        # itemx["project_description"] = [x.lower() for x in itemx["project_description"]]  # convert to lower case
        # itemx["project_description"] = ",".join(itemx["project_description"])  # convert to string seperated by comma
        if "skills" in itemg.keys() and itemg["skills"] !=None:
            itemg["skills"] = [x.lower() for x in itemg["skills"]]  # convert to lower case
            itemg["skills"] = ",".join(itemg["skills"])  # convert to string seperated by comma
        collection = db2[collection_name]

        await collection.update_one({"_id" : objid}, {'$set' : itemg})
        return {"message": "Recruiter updated successfully", "id": itemg["_id"]}
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Updated Recruiter Mongo",))
        # connection.commit()
    except Exception as e:
        print(e)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error, User not added")


@app.delete("/DeleteRecruitermongo/")  #Recruiter delete
async def delete_recruiter_mongo(email:str =Query(...)):
    try:
        collection_name = email
        collection = db2[collection_name]
        collection.drop()
        # #await collection.update_one({"_id" : objid}, {'$set' : itemx})
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Recruiter Deleted mongo",))
        # connection.commit()
        return {"message": "Recruiter Deleted successfully"}
    except Exception as e:
        print(e)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error, Recruiter not deleted")


@app.delete("/DeleteUsermongo/")  #User delete mongo
async def delete_recruiter_mongo(email:str =Query(...)):
    try:
        collection_name = email
        collection = db1[collection_name]
        collection.drop()
        #await collection.update_one({"_id" : objid}, {'$set' : itemx})
        return {"message": "User Deleted successfully"}
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "User Deleted Mongo",))
        # connection.commit()
    except Exception as e:
        print(e)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error, User not deleted")


@app.post("/newrecruitermongo/")
async def new_recruiter_mongo(item: Recruiter):
    try:
        collection_name = str(item.email)
        itemx = item.dict()
        itemx["_id"] = str(ObjectId())
        # Convert project description to lower case and convert to string seperated by comma
        #convert skills to lowercase and convert to string seperated by comma
        itemx["skills"] = [x.lower() for x in itemx["skills"]]  # convert to lower case
        itemx["skills"] = ",".join(itemx["skills"])  # convert to string seperated by comma
        await db2.create_collection(collection_name)
        collection = db2[collection_name]
        await collection.insert_one(itemx)




        #save id to postgres also for future use

        #write to postgres
        cursor.execute("UPDATE public.business_login SET id = %s WHERE email = %s", (str(itemx["_id"]), str(itemx["email"]),))
        connection.commit()
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "New Recruiter Mongo",))
        # connection.commit()
        return {"message": "Item created successfully & User updated successfully","id":itemx["_id"]}
    except Exception as e:
        print(e)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error, User not added")

#
@app.get("/getusermongo/{email}/{item_id}")
async def get_user_mongo(email: str, item_id: str):
    try:
        collection = db1[email]

        item = await collection.find_one({"_id": item_id})
        if item:
            #skills string to list
            if type(item["skills"]) == str:
                item["skills"] = item["skills"].split(",")
            return item
            # now = datetime.today()
            # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Fetch user Mongo",))
            # connection.commit()
        else:
            # now = datetime.today()
            # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
            # connection.commit()
            return {"message": "Item not found"}
        # else:
        #     raise HTTPException(status_code=404, detail="Item not found")
    except Exception as e:
        print(e)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error")



@app.get("/getrecruitermongo/{email}/{item_id}")
async def get_recruiter_mongo(email: str, item_id: str):
    try:
        collection = db2[email]

        item = await collection.find_one({"_id": item_id})
        if item:

            if type(item["skills"]) == str:
                item["skills"] = item["skills"].split(",")
            # now = datetime.today()
            # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Recruiter Fetch Mongo",))
            # connection.commit()
            return item
        else:
            # now = datetime.today()
            # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
            # connection.commit()
            return {"message": "Item not found"}
        # else:
        #     raise HTTPException(status_code=404, detail="Item not found")
    except Exception as e:
        print(e)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error")

# ##UPDATE##
#
# #Search Keyword in Mongo
@app.get("/searchuserdetailsmongo/{phrase}",response_description="Stringified List of keywords seperated by comma")
async def search_mongo(phrase: str):
    keywords = list(phrase.split(","))
    print(keywords)
    result = {"data": []}
    try:


        collections = await db1.list_collection_names()
        print(collections)
        print("1")
        for collection in collections:
            print(type(collection))
            for ix in keywords:
                #search dict to search based on description & skills
                search_dict = {"$or": [{"description": {"$in": [str(ix).lower()]}}, {"skills": {"$in": [str(ix).lower()]}}]}
                res = db1[collection].find(search_dict)
                while await res.fetch_next:
                    result["data"].append(res.next_object())
                print(res)

            # result = await db1.find({"$text": {"$search": str(ix).lower(), "$caseSensitive": False, "$diacriticSensitive": False}})
            # now = datetime.today()
            # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Search success",))
            # connection.commit()
            # return json.dumps(result)
        return result
    except Exception as e:
            print(e)
            # now = datetime.today()
            # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
            # connection.commit()
            raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/searchrecruiterdetailsmongo/{phrase}",response_description="Stringified List of keywords seperated by comma")
async def search_mongo(phrase: str):
    keywords = list(phrase.split(","))
    result = {"data": []}
    try:
        collections = await db2.list_collection_names()
        for collection in collections:
            for ix in keywords:
                search_dict = {"$or": [{"project_area_details": {"$in":[str(ix).lower()]}},{"skills": {"$in":[str(ix).lower()]}}]}
                res = db2[collection].find(search_dict)
                while await res.fetch_next:
                    result["data"].append(res.next_object())
                print(res)



        return result
    except Exception as e:
            print(e)
            # now = datetime.today()
            # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
            # connection.commit()
            raise HTTPException(status_code=500, detail="Internal Server Error")

#FILTERING
@app.get("/filteruserdetailsmongo/",response_description="Queried List of keywords seperated by comma")
async def searchfreelancer(

        skills: Optional[str] = Query(None),
        experience: Optional[int] = Query(None),
        # pay: Optional[int] = Query(None),
        ratings: Optional[int] = Query(None),
        category: Optional[str] = Query(None),
):
    try:
        collection = db1
        # create filter dictionary based on query parameters
        filter_dict = {}
        if skills:
            filter_dict['skills'] = {'$all': skills.split(',')}
        if experience:
            filter_dict['experience'] = {'$gte': experience}
        if ratings:
            filter_dict['ratings'] = {'$gte': ratings}
        if category:
            filter_dict['occupation'] = {'$all':category}


        # search for freelancers in MongoDB with matching filter conditions
        collections = await db1.list_collection_names()
        result = {"data": []}
        for collection in collections:
            # sort by score in descending order
            res = db1[collection].find(filter_dict)
            while await res.fetch_next:
                if len(result["data"]) < 10:
                    result["data"].append(res.next_object())
                else:
                    break




    # return result as JSON string
        return result
    except Exception as e:
        print(e)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error")

# @app.get("/filterrecruiterdetailsmongo/",response_description="Queried List of keywords seperated by comma")
@app.get("/filterbuyerdetailsmongo/",response_description="Queried List of keywords seperated by comma")
async def searchproject(
        category:Optional[str] = Query(None),
        skills: Optional[str] = Query(None),
        min_budget: Optional[int] = Query(None),
        delivery_time: Optional[int] = Query(None),

):
    try:
        collection = db2
        # create filter dictionary based on query parameters
        filter_dict = {}
        if category:
            filter_dict['project_area'] = {'$all':category}
        if skills:
            filter_dict['skills'] = {'$all': skills.split(',')}
        if min_budget:
            filter_dict['budget'] = {'$gte': min_budget}
        if delivery_time:
            filter_dict['delivery_time'] = {'$gte': delivery_time}

        # search for freelancers in MongoDB with matching filter conditions
        collections = await db2.list_collection_names()
        result = {"data": []}
        for collection in collections:
            res = db2[collection].find(filter_dict)
            while await res.fetch_next:
                if len(result["data"]) < 10:
                    result["data"].append(res.next_object())
                else:
                    break
        return result
    except Exception as e:
        print(e)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error")




def check_existance(containername):
    container_client = blob_service_client.get_container_client(containername)

    if container_client.get_container_properties():
        print("Container already exists")
    else:
        container_client.create_container()


@app.post("/uploadimage")
async def upload_image( item: Uploader,file: UploadFile = File(...)):
    try:

        containername = str(item.email)
        check_existance(containername)
        file_name = str(uuid.uuid4()) + '-' + file.filename

        # Create a BlobClient object
        blob_client = blob_service_client.get_blob_client(container=containername, blob=file_name)

        # Upload the file to Azure Blob Storage
        blob_client.upload_blob(await file.read())

        # Return the URL to the uploaded file
        url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{containername}/{file_name}"
        return {'url': url}
    except Exception as e:
        print(e)
        # now = datetime.today()
        # cursor.execute("INSERT INTO public.logs (date, log) VALUES (%s, %s)", (now, "Error",))
        # connection.commit()
        raise HTTPException(status_code=500, detail="Internal Server Error")


#SOCKET IO

# Add the WebSocket route with a path parameter
@app.websocket("/ws/{path:path}")
async def websocket_endpoint(websocket: WebSocket, path: str):
    await socket_manager.connect(websocket)
    try:
        # Wait for messages from the client
        while True:
            data = await websocket.receive_text()
            print(f"Message received from {websocket.sid}: {data}")
    except:
        await socket_manager.disconnect(websocket)


# Add the socket.io event handlers
@socket_manager.on("connect")
async def connect(sid, environ):
    print(f"New client connected: {sid}")

@socket_manager.on("disconnect")
async def disconnect(sid):
    print(f"Client disconnected: {sid}")

@socket_manager.on("message")
async def message(sid, data):
    print(f"Message received from {sid}: {data}")

@socket_manager.on("chat_message")
async def chat_message(sid, data):
    print(f"Received message from {sid}: {data}")
    # Get the recipient's sid from the message data
    recipient_sid = data["recipient_sid"]
    # Send the message to the recipient
    await socket_manager.emit("chat_message", data, room=recipient_sid)

@socket_manager.on("join_room")
async def join_room(sid, data):
    print(f"Client {sid} joined room {data['room']}")
    await socket_manager.enter_room(sid, data["room"])

@socket_manager.on("leave_room")
async def leave_room(sid, data):
    print(f"Client {sid} left room {data['room']}")
    await socket_manager.leave_room(sid, data["room"])

@socket_manager.on("get_clients")
async def get_clients(sid, data):
    room = data.get("room")
    if room:
        clients = list(socket_manager.rooms.get(room, set()))
        await socket_manager.emit("clients_list", {"clients": clients}, room=sid)


@socket_manager.on("get_rooms")
async def get_rooms(sid):
    rooms = await socket_manager.get_rooms()
    print(f"Current rooms: {rooms}")



# #portx = os.environ.get('PORT', 8000)
# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port = 8000, log_level='info')










