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
import socketio



#
sql_user = "freelance@postgresfreelance"
sql_host = "postgresfreelance.postgres.database.azure.com"
sql_pass = "Rogers@123"
sql_db = "postgresfreelance"
mongodb_url = "mongodb://freelancedapi:CjViwnSIvg8Ri724f9CP05mkaeCLDoLK4ynu5UxtNeYMxwxjueNzqddyNdIUfp7YMFCgPtvWErsbACDb9vRtnA==@freelancedapi.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000&appName=@freelancedapi@"

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

socket_manager = SocketManager(app=app,cors_allowed_origins="*", mount_location='/ws')
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
    email: str = Query(...)
    phone: str = Query(...)
    profile_pic: Optional[str] = Query(...)
    worksamples: Optional[list] = Query(...)
    website: Optional[str] = Query(...)
    description: Optional[str] = Query(...)
    language: Optional[str] = Query(...)
    occupation: Optional[str] = Query(...)
    experience: Optional[int] = Query(...)
    university: Optional[str] = Query(...)
    uni_country: Optional[str] = Query(...)
    uni_degree: Optional[str] = Query(...)
    uni_grad_date: Optional[str] = Query(...)
    skills: Optional[list] = Query(...)
    proficency: Optional[list] = Query(...)
    certificates: Optional[list] = Query(...)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class Recruiter(BaseModel):
    email: str = Query(...)
    phone: str = Query(...)
    profile_pic: Optional[str] = Query(...)
    language: Optional[str] = Query(...)
    occupation: Optional[str] = Query(...)
    project_area: Optional[list] = Query(...)
    project_area_details: Optional[list] = Query(...)
    documents: Optional[list] = Query(...)
    skills: Optional[list] = Query(...)
    proficency: Optional[list] = Query(...)
    timeline: Optional[bool] = Query(...)
    deadline: Optional[str] = Query(...)
    budget: Optional[str] = Query(...)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


#
class Uploader(BaseModel):
    email: str = Query(...)


    #More Fields#


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
        return (json.dumps(id_info)) #id_info is a dictionary of all the user's info


@app.get("/protected")
def protected_route(token: str = Depends(oauth2_scheme)):
    # User is authenticated, do something with token
    return {"Hello": "Authenticated User!"}

#USer existance check

# POSTGRES
@app.get("/userexists/{email}")
async def user_exists(email: str):
    try:
        cursor.execute("SELECT * FROM public.user_login_1 WHERE email = %s", (email,))
        item = cursor.fetchone()
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        else:
            return {"message": "User exists"}

    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL", error)
        raise HTTPException(status_code=500, detail="Internal Server Error")



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
        return {"message": "User added successfully"}
    except (Exception, psycopg2.Error) as error:
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
        return {"message": "User added successfully"}
    except (Exception, psycopg2.Error) as error:
        return{"message":error}

@app.get("/getuser/{email}")
async def get_user(email: str):
    try:
        cursor.execute("SELECT * FROM public.user_login_1 WHERE email = %s", (email,))
        item = cursor.fetchone()
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        else:
            return {"email": item[2], "Firstname": item[0], "Lastname": item[1]}
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL", error)
        raise HTTPException(status_code=500, detail="Internal Server Error")

#@app.delete("/deleteuser/{email}")  #DELETE USER
async def delete_user(email: str):
    try:
        cursor.execute("DELETE FROM public.user_login_1 WHERE email = %s", (email))
        raise "Item Deleted"
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL", error)
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
            return {"email": item[2], "Firstname": item[0], "Lastname": item[1]}
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL", error)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.put("/updateuser/{email}")
async def update_user(email: str,item: Item):
    try:
        cursor.execute("UPDATE public.user_login_1 SET firstname = %s, lastname = %s WHERE email = %s", (item.firstname, item.lastname,email,))
        connection.commit()
        return {"message": "User updated successfully"}
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL", error)
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.put("/updaterecriter/{email}")
async def update_user(email: str, item: Item):
    try:
        cursor.execute("UPDATE public.business_login SET firstname = %s, lastname = %s WHERE email = %s", (item.firstname, item.lastname, email,))
        connection.commit()
        return {"message": "User updated successfully"}
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL", error)
        raise HTTPException(status_code=500, detail="Internal Server Error")


#MONGODB

# Add a new user to the database
@app.post("/newusermongo/")
async def new_user_mongo(item: User):
    try:
        collection_name = str(item.email)
        itemx = item.dict()
        itemx["_id"] = str(ObjectId())
        await db1.create_collection(collection_name)
        collection = db1[collection_name]
        await collection.insert_one(itemx)
        # save id to postgres also for future use

        # write to postgres
        cursor.execute("UPDATE public.user_login_1 SET id = %s WHERE email = %s", (str(itemx["_id"]), str(itemx["email"]),))
        connection.commit()

        return {"message": "Item created successfully & User updated successfully", "id": itemx["_id"]}

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Internal Server Error, User not added")

@app.put("/updateusermongo/")  #User Update
async def update_user_mongo(item: User, objid:str =Query(...)):
    try:
        collection_name = str(item.email)
        itemx = item.dict()
        itemx["_id"] = objid

        collection = db1[collection_name]

        await collection.update_one({"_id" : objid}, {'$set' : itemx})
        return {"message": "User updated successfully", "id": itemx["_id"]}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Internal Server Error, User not added")


@app.put("/updateRecruitermongo/")  #Recruiter Update
async def update_recruiter_mongo(item: Recruiter, objid:str =Query(...)):
    try:
        collection_name = str(item.email)
        itemx = item.dict()
        itemx["_id"] = objid

        collection = db2[collection_name]

        await collection.update_one({"_id" : objid}, {'$set' : itemx})
        return {"message": "Recruiter updated successfully", "id": itemx["_id"]}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Internal Server Error, User not added")


@app.delete("/DeleteRecruitermongo/")  #Recruiter delete
async def delete_recruiter_mongo(email:str =Query(...)):
    try:
        collection_name = email
        collection = db2[collection_name]
        collection.drop()
        #await collection.update_one({"_id" : objid}, {'$set' : itemx})
        return {"message": "Recruiter Deleted successfully"}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Internal Server Error, Recruiter not deleted")


@app.delete("/DeleteUsermongo/")  #User delete mongo
async def delete_recruiter_mongo(email:str =Query(...)):
    try:
        collection_name = email
        collection = db1[collection_name]
        collection.drop()
        #await collection.update_one({"_id" : objid}, {'$set' : itemx})
        return {"message": "User Deleted successfully"}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Internal Server Error, User not deleted")


@app.post("/newrecruitermongo/")
async def new_recruiter_mongo(item: Recruiter):
    try:
        collection_name = str(item.email)
        itemx = item.dict()
        itemx["_id"] = str(ObjectId())
        await db2.create_collection(collection_name)
        collection = db2[collection_name]
        await collection.insert_one(itemx)
        #save id to postgres also for future use

        #write to postgres
        cursor.execute("UPDATE public.business_login SET id = %s WHERE email = %s", (str(itemx["_id"]), str(itemx["email"]),))
        connection.commit()

        return {"message": "Item created successfully & User updated successfully","id":itemx["_id"]}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Internal Server Error, User not added")

#
@app.get("/getusermongo/{email}/{item_id}")
async def get_user_mongo(email: str, item_id: str):
    try:
        collection = db1[email]

        item = await collection.find_one({"_id": item_id})
        if item:
            return item
        else:
            return {"message": "Item not found"}
        # else:
        #     raise HTTPException(status_code=404, detail="Item not found")
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Internal Server Error")



@app.get("/getrecruitermongo/{email}/{item_id}")
async def get_user_mongo(email: str, item_id: str):
    try:
        collection = db2[email]

        item = await collection.find_one({"_id": item_id})
        if item:
            return item
        else:
            return {"message": "Item not found"}
        # else:
        #     raise HTTPException(status_code=404, detail="Item not found")
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

            result = await db1.find({"$text": {"$search": str(ix).lower(), "$caseSensitive": False, "$diacriticSensitive": False}})
            return json.dumps(result)
    except Exception as e:
            print(e)
            raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/searchrecruiterdetailsmongo/{phrase}",response_description="Stringified List of keywords seperated by comma")
async def search_mongo(phrase: str):
    keywords = list(phrase.split(","))
    try:
        for ix in keywords:

            result = await db2.find({"$text": {"$search": str(ix).lower(), "$caseSensitive": False, "$diacriticSensitive": False}})
            return json.dumps(result)
    except Exception as e:
            print(e)
            raise HTTPException(status_code=500, detail="Internal Server Error")

#FILTERING
@app.get("/filteruserdetailsmongo/",response_description="Queried List of keywords seperated by comma")
async def searchfreelancer(

        skills: Optional[list] = Query(None),
        experience: Optional[int] = Query(None),
        pay: Optional[int] = Query(None),
        ratings: Optional[int] = Query(None),
        category: Optional[list] = Query(None),
):
    try:
        collection = db1
        # create filter dictionary based on query parameters
        filter_dict = {}
        if skills:
            filter_dict['skills'] = {'$all': skills.split(',')}
        if experience:
            filter_dict['experience'] = {'$gte': experience}
        if pay:
            filter_dict['pay'] = {'$lte': pay}
        if ratings:
            filter_dict['ratings'] = {'$gte': ratings}
        if category:
            filter_dict['category'] = {'$all':category.split('')}

        # search for freelancers in MongoDB with matching filter conditions
        result = collection.find(filter_dict).sort([('score', -1)]).limit(10)

    # return result as JSON string
        return json.dumps(result)
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Internal Server Error")

# @app.get("/filterrecruiterdetailsmongo/",response_description="Queried List of keywords seperated by comma")
@app.get("/filterbuyerdetailsmongo/",response_description="Queried List of keywords seperated by comma")
async def searchproject(
        category:Optional[list] = Query(None),
        skills: Optional[list] = Query(None),
        min_budget: Optional[int] = Query(None),
        ratings: Optional[int] = Query(None),
        experience: Optional[int] = Query(None),
        delivery_time: Optional[int] = Query(None),

):
    try:
        collection = db2
        # create filter dictionary based on query parameters
        filter_dict = {}
        if category:
            filter_dict['category'] = {'$all':category.split(',')}
        if skills:
            filter_dict['skills'] = {'$all': skills.split(',')}
        if min_budget:
            filter_dict['budget'] = {'$gte': min_budget}
        if ratings:
            filter_dict['ratings'] = {'$gte': ratings}
        if experience:
            filter_dict['experience'] = {'$lte': experience}
        if delivery_time:
            filter_dict['delivery_time'] = {'$gte': delivery_time}

        # search for freelancers in MongoDB with matching filter conditions
        result = collection.find(filter_dict).sort([('score', -1)]).limit(10)
        return json.dumps(result)
    except Exception as e:
        print(e)
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
        raise HTTPException(status_code=500, detail="Internal Server Error")


#SOCKET IO

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
async def get_clients(sid):
    clients = await socket_manager.get_clients()
    print(f"Current clients: {clients}")

@socket_manager.on("get_rooms")
async def get_rooms(sid):
    rooms = await socket_manager.get_rooms()
    print(f"Current rooms: {rooms}")




# #portx = os.environ.get('PORT', 8000)
# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port = 8000, log_level='info')










