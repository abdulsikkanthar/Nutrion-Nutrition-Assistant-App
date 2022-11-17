from flask import Flask, render_template, request, redirect, url_for, flash, session
import ibm_db
import re
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import os
from werkzeug.utils import secure_filename
from clarifai_grpc.channel.clarifai_channel import ClarifaiChannel
from clarifai_grpc.grpc.api import service_pb2_grpc
from clarifai_grpc.grpc.api import service_pb2, resources_pb2
from clarifai_grpc.grpc.api.status import status_code_pb2
import spoonacular as sp


#creating instance of flask class
app = Flask(__name__)

#connecting with ibm db2
app.secret_key = "nutritionassistantapplication"
conn = ibm_db.connect("DRIVER={IBM DB2 ODBC DRIVER}; DATABASE=bludb; HOSTNAME=xxxx; PORT=xxxx; SECURITY=SSL;SSLServerCertificate=DigiCertGlobalRootCA.crt; UID=xxx; PWD=xxx;",'','')

# Defining upload folder path
UPLOAD_FOLDER = os.path.join('static', 'uploads')
# # Define allowed files
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def index():
    return render_template("index.html")


def send_confirmation_mail(user, mail):
    message = Mail(
        from_email = "nutritionassistantapplication@gmail.com",
        to_emails = mail,
        subject = "Congrats! Your Account was created Successfully",
        html_content = f"<strong>Congrats {user}!</strong><br>Account Created with username {mail}"
    )

    SENDGRID_API_KEY='xxxx'
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        print(response.status_code)
        #print(response.body)
        #print(response.headers)
    except Exception as e:
        print(f"Some error in sendgrid, {e}")

@app.route('/register', methods=["POST", "GET"])
def register():
    msg = ''
    #render_template("register.html")
    if request.method=="POST":
        #getting data from register form
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        #checking an account existing 
        sql = "SELECT * FROM USERS WHERE email = ? "
        stmt = ibm_db.prepare(conn, sql)
        ibm_db.bind_param(stmt, 1, email)
        ibm_db.execute(stmt)

        account  = ibm_db.fetch_assoc(stmt)

        if(account):
            msg = "Account already registered!"
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = "Invalid email address"
        elif not re.match(r'[A-Za-z\s]*$', name):
            msg = "Name should contain characters and space only"
        elif password:
            if(len(password)<8):
                msg = "Make sure your password is at lest 8 letters"
            elif (re.search('[0-9]',password) is None):
                msg = "Make sure your password has a number in it"
            elif (re.search('[a-z]', password) is None):
                msg = "Make sure your password has a small letter in it"
            elif (re.search('[a-z]', password) is None):
                msg = "Make sure your password has a Capital letter in it"
            elif (re.compile('[^0-9a-zA-Z]+').search(password) is None):
                msg = "Make sure your password has a special character in it"
            else:
                #inserting the data into db2 database
                sql = "INSERT INTO USERS VALUES(?,?,?)"
                stmt = ibm_db.prepare(conn, sql)
                ibm_db.bind_param(stmt, 1, name)
                ibm_db.bind_param(stmt, 2, email)
                ibm_db.bind_param(stmt, 3, password)
                ibm_db.execute(stmt)   
 
                msg = "Account created successfully, Kindly login"
                
                #sending confirmation mail to user
                send_confirmation_mail(name, email)

                return redirect(url_for("login"))
    else:
        if "user" in session:
            return render_template("profile.html", msg='', name=session['name'], email=session['user'])
    
    return render_template("register.html", msg=msg)

"""@app.route("/home/<msg>")
def home(msg, account):
    if "user" in session:
        return render_template("home.html", msg=msg, account=account)
    else:
        return redirect(url_for("login", msg="Kindly login"))
"""

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ""
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']

        #retrieving the user details
        sql = "SELECT * FROM users WHERE email = ? AND pwd = ?"
        stmt = ibm_db.prepare(conn, sql)
        ibm_db.bind_param(stmt, 1, email)
        ibm_db.bind_param(stmt, 2, password)
        ibm_db.execute(stmt)

        account = ibm_db.fetch_assoc(stmt)

        if account:
            name = account['NAME']
            session['loggedin'] = True 
            session['user'] = email
            session['name'] = name
            
            msg = "Login successfully"

            return render_template("profile.html", msg=msg, name=name, email=email)

        elif "user" in session:
            return render_template("profile.html", msg=msg, name=name, email=email)

        else:
            msg = "Incorrect password or email address"

    else:
        if "user" in session:
            return render_template("profile.html", msg='', name=session['name'], email=session['user'])

    return render_template("login.html", msg=msg)

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('name', None)
    session.pop('user', None)
    flash("Loged out successfully")
    return render_template("index.html", msg="Loged out successfully", clr="red", cls="msg")

@app.route("/delete/<email>")
def delete(email):
    sql = "DELETE FROM USERS WHERE email = ?"
    stmt = ibm_db.prepare(conn, sql)
    ibm_db.bind_param(stmt, 1, email)
    ibm_db.execute(stmt)
    return render_template("register.html", msg="Account deleted successfully")

@app.route('/newscan',  methods=("POST", "GET"))
def uploadFile():

    if request.method == 'POST':
        # Upload file flask
        uploaded_img = request.files['uploaded-file']
        # Extracting uploaded data file name
        img_filename = secure_filename(uploaded_img.filename)
        # Upload file to database (defined uploaded folder in static path)
        path = os.path.join(app.config['UPLOAD_FOLDER'], img_filename)
        uploaded_img.save(path)
        food = predictConcept(path)
        # Storing uploaded file path in flask session
        session['uploaded_img_file_path'] = os.path.join(app.config['UPLOAD_FOLDER'], img_filename)
        print("File name: ",img_filename)

    return f"<h3>File uploaded successfully<br>Given food item is {food}</h3>"


#Predict the food item in the given using the image recognition in clarifai model
def predictConcept(path):
    USER_ID = 'emayakeerthi'
    # Your PAT (Personal Access Token) can be found in the portal under Authentification
    PAT = 'xxxx'
    APP_ID = 'Nutrion'
    # Change these to whatever model and image input you want to use
    MODEL_ID = 'general-image-recognition'
    IMAGE_FILE_LOCATION = path
    # This is optional. You can specify a model version or the empty string for the default
    MODEL_VERSION_ID = ''

    channel = ClarifaiChannel.get_grpc_channel()
    stub = service_pb2_grpc.V2Stub(channel)

    metadata = (('authorization', 'Key ' + PAT),)

    userDataObject = resources_pb2.UserAppIDSet(user_id=USER_ID, app_id=APP_ID)

    with open(IMAGE_FILE_LOCATION, "rb") as f:
        file_bytes = f.read()

    post_model_outputs_response = stub.PostModelOutputs(
        service_pb2.PostModelOutputsRequest(
            user_app_id=userDataObject,  # The userDataObject is created in the overview and is required when using a PAT
            model_id=MODEL_ID,
            version_id=MODEL_VERSION_ID,  # This is optional. Defaults to the latest model version
            inputs=[
                resources_pb2.Input(
                    data=resources_pb2.Data(
                        image=resources_pb2.Image(
                            base64=file_bytes
                        )
                    )
                )
            ]
        ),
        metadata=metadata
    )
    if post_model_outputs_response.status.code != status_code_pb2.SUCCESS:
        print(post_model_outputs_response.status)
        raise Exception("Post model outputs failed, status: " + post_model_outputs_response.status.description)

    # Since we have one input, one output will exist here
    output = post_model_outputs_response.outputs[0]

    print("Predicted concepts:")
    for concept in output.data.concepts:
        print("%s %d" % (concept.name, concept.value))
        getNutritions(concept.name)
        return concept.name
        

    
#search the nutrition in given food using FatSecret API
api = sp.API("xxx")
def getNutritions(food_item):
    response = api.guess_nutrition_by_dish_name(food_item)
    data = response.json()
    fat = data['fat']
    carbs = data['carbs']
    protein = data['protein']

    print("Fat: ",str(fat['value'])+fat['unit'])
    print("Carbs: ",str(carbs['value'])+carbs['unit'])
    print("Protein: ",str(protein['value'])+protein['unit'])



if __name__=="__main__":
    app.run(debug=True)