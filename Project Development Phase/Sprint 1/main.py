from flask import Flask, render_template, request, redirect, url_for, flash, session
import ibm_db
import re

#creating instance of flask class
app = Flask(__name__)

#connecting with ibm db2
app.secret_key = "nutritionassistantapplication"
#conn = ibm_db.connect("DATABASE=bludb;HOSTNAME=19af6446-6171-4641-8aba-9dcff8e1b6ff.c1ogj3sd0tgtu0lqde00.databases.appdomain.cloud;PORT=30699;SECURITY=SSL;SSLServerCertificate=DigiCertGlobalRootCA.crt;UID=yyx69722;PWD=2YqarEmzriL08SP7",'','')
conn = ibm_db.connect("DRIVER={IBM DB2 ODBC DRIVER}; DATABASE=bludb; HOSTNAME=98538591-7217-4024-b027-8baa776ffad1.c3n41cmd0nqnrk39u98g.databases.appdomain.cloud; PORT=30875; SECURITY=SSL;SSLServerCertificate=DigiCertGlobalRootCA.crt; UID=jqb73841; PWD=E4pdcHrukFsv9qz2;",'','')

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/register', methods=["POST", "GET"])
def register():
    msg = ''
    #render_template("register.html")
    if request.method=="POST":
        #getting data from register form
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

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

                return redirect(url_for("login", msg=msg))

    return render_template("register.html", msg=msg)


@app.route("/home/<msg>")
def home(msg, account):
    if "user" in session:
        return render_template("home.html", msg=msg, account=account)
    else:
        return redirect(url_for("login", msg="Kindly login"))

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
            name = account['name']
            session['loggedin'] = True 
            session['user'] = email
            session['name'] = name
            
            msg = "Login successfully"

            return render_template("home.html", msg=msg, name=name, email=email)

        elif "user" in session:
            return redirect(url_for("home", message={'msg': "login", "account": account}))

        else:
            msg = "Incorrect password or email address"

    else:
        if "user" in session:
            return redirect(url_for("home", msg='', name=session['name'], email=session['email']))

    return render_template("login.html", msg=msg)

if __name__=="__main__":
    app.run(debug=True)