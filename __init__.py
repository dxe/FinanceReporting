import os
import mysql.connector
from flask import Flask, redirect, url_for, flash, jsonify, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from flask_dance.contrib.google import make_google_blueprint, google

from .helpers import sanitize, login_required, usd, urlencode_filter, format_date

# configure app
app = Flask(__name__)
# Google OAuth config
app.secret_key = os.environ.get("FLASK_SECRET_KEY")
app.config["GOOGLE_OAUTH_CLIENT_ID"] = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
app.config["GOOGLE_OAUTH_CLIENT_SECRET"] = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
google_bp = make_google_blueprint(scope=["profile", "email"])
app.register_blueprint(google_bp, url_prefix="/login")
# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filters
app.jinja_env.filters["usd"] = usd
app.jinja_env.filters["urlencode"] = urlencode_filter
app.jinja_env.filters["formatdate"] = format_date


# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_TYPE"] = "filesystem"
app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET_KEY")
# keep sessions alive for 2 hours before requiring auth again
app.config["PERMANENT_SESSION_LIFETIME"] = 7200
Session(app)


def db_query(q, commit = False):

    mydb = mysql.connector.connect(
        user=os.environ.get("DB_USER"),
        passwd=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB"),
        host=os.environ.get("DB_HOST"),
        port=os.environ.get("DB_PORT"),
        ssl_ca=os.environ.get("SSL_CA"),
        ssl_verify_cert=True
    )
    mycursor = mydb.cursor(dictionary=True)

    mycursor.execute(q)

    print(mycursor.statement)

    rows = list()

    for x in mycursor:
        rows.append(x)

    if commit:
        mydb.commit()

    mycursor.close()

    mydb.close()

    return rows  


@app.route("/")
def login():
    # direct to login page
    if not google.authorized:
        # send to oauth
        return redirect(url_for("google.login"))
    # get user info, or sent back to login if token expired
    try:
        resp = google.get("/oauth2/v1/userinfo")
        # make sure resp.ok exists, else show resp.text as error
        assert resp.ok, resp.text
    except: 
        return redirect(url_for("google.login"))

    # email address provided by google oauth
    email = resp.json()["email"]

    # check if email is authorized
    query = "select id from users where email = '" + email + "'"
    rows = db_query(query)
    if rows:
        # set user id in session
        session["user_id"] = rows[0]["id"]
        
        # update last_auth in database
        query = "UPDATE users SET last_auth = now() WHERE id = " + str(session["user_id"])
        db_query(query, True)

        # success, you are logged in
        return redirect('/donations')

    session.clear()
    return "You are unauthorized!"


@app.route('/logout')
def logout():

    if google.authorized:
        google.post(
            'https://accounts.google.com/o/oauth2/revoke',
            params={'token': app.blueprints['google'].token["access_token"]},
            headers = {'content-type': 'application/x-www-form-urlencoded'}
        )

    session.clear()

    return redirect("/")


@app.route('/donations', methods=["GET", "POST"])
@login_required
def donations():

    if request.method == "GET":

        # if url args are supplied, then we are seraching for a specific donor by name
        if request.args.get('n'):
            donorName = sanitize(request.args.get("n"))

            # query here

            query = (" SELECT * FROM " +
                    " (SELECT amount, cretime as date, status, type, donorEmail, formName, donorName FROM funraise_donations_friends WHERE formName <> 'Facebook' " +
                    " UNION ALL SELECT amount, cretime as date, IF(amount > 0, 'Complete', 'Refunded') as status, 'One Time' as type, donorEmail, concat('Facebook - ', page) as formName, name as donorName FROM `facebook_donations`) temp ")

            query += " WHERE donorName = '" + donorName + "'"

            rows = db_query(query)

            heading1 = f"{donorName}"

            return render_template("donations.html", rows=rows, heading1=heading1)

        # if GET request w/o any url args, just show recent donor list

        heading1 = "Recent donations"

        rows = db_query(("SELECT amount, cretime as date, status, type, donorEmail, formName, donorName FROM funraise_donations_friends WHERE donorName not like '%for good%' and formName <> 'Facebook' " +
                        " UNION ALL SELECT amount, cretime as date, IF(amount > 0, 'Complete', 'Refunded') as status, 'One Time' as type, donorEmail, concat('Facebook - ', page) as formName, name as donorName FROM `facebook_donations` " +
                        " ORDER BY date desc LIMIT 500 "))

        return render_template("donations.html", rows=rows, heading1=heading1)

    # if POST request, generate a custom query for search
    if request.method == "POST":

        query = (" SELECT * FROM " +
                " (SELECT amount, cretime as date, status, type, donorEmail, formName, donorName FROM funraise_donations_friends WHERE formName <> 'Facebook' " +
                " UNION ALL SELECT amount, cretime as date, IF(amount > 0, 'Complete', 'Refunded') as status, 'One Time' as type, donorEmail, concat('Facebook - ', page) as formName, name as donorName FROM `facebook_donations`) temp ")

        donorName = sanitize(request.form.get("donorName"))
        donorEmail = sanitize(request.form.get("donorEmail"))
        status = sanitize(request.form.get("status"))
        donationType = sanitize(request.form.get("donationType"))
        donationForm = sanitize(request.form.get("donationForm"))
        minAmount = sanitize(request.form.get("minAmount"))
        maxAmount = sanitize(request.form.get("maxAmount"))
        minDate = sanitize(request.form.get("minDate"))
        maxDate = sanitize(request.form.get("maxDate"))

        query += " WHERE "

        if donorName:
            query += " donorName like '%" + donorName + "%'"
            query += " AND "

        if status:
            query += " status = '" + status + "'"
            query += " AND "

        if donationType:
            query += " type = '" + donationType + "'"
            query += " AND "

        if donationForm:
            query += " formName like '%" + donationForm + "%'"
            query += " AND "

        if minAmount:
            query += " amount >= '" + minAmount + "'"
            query += " AND "

        if maxAmount:
            query += " amount <= '" + maxAmount + "'"
            query += " AND "

        if minDate:
            query += " date >= '" + minDate + "'"
            query += " AND "

        if maxDate:
            query += " DATE_ADD(date, INTERVAL -1 DAY) <= '" + maxDate + "'"
            query += " AND "

        # always need to add this line so we don't show facebook donations entered into funraise
        query += " donorName not like '%for good%'"

        query += " ORDER BY date desc"

        heading1 = "Donation results"

        rows = db_query(query)

        return render_template("donations.html", rows=rows, heading1=heading1)


@app.route('/donations_search')
@login_required
def donations_search():

    # get list of possible donation form names
    donationForms = db_query("SELECT formName FROM funraise_donations_friends group by formName UNION ALL  select 'Facebook - Friends of DxE'  UNION ALL  select 'Facebook - Direct Action Everywhere'")

    return render_template("donations_search.html", donationForms=donationForms)


@app.route('/donors', methods=["GET", "POST"])
@login_required
def donors():
    # if GET request, show recent donors
    if request.method == "GET":

        query = ("SELECT name, max(email) as email, max(phone) as phone, max(location) as location, max(photo) as photo, max(fb) as fb, if(max(status) <> '', 'RECURRING', max(type)) as type, if(group_concat(status) like '%active%', 'Active', max(status)) as status, max(lastDate) as lastDate, min(firstDate) as firstDate, sum(amount) as amount" +
                " FROM (" +
                "   SELECT name, max(email) as email, max(phone) as phone, max(concat(city, ' ', state)) as location, max(photoUrl) as photo, max(facebookUrl) as fb, if(recurringStatus <> '', 'RECURRING', max(donorType)) as type, if(group_concat(recurringStatus) like '%active%', 'Active', max(recurringStatus)) as status, lastDate, firstDate, amount FROM funraise_donors_friends left join (   SELECT max(cretime) as lastDate, min(cretime) as firstDate, donorName, sum(CASE WHEN status = 'Complete' AND formName <> 'Facebook' THEN amount ELSE 0 END) as amount    FROM `funraise_donations_friends`   group by donorName ) temp on temp.donorName = funraise_donors_friends.name WHERE donorType <> 'POTENTIAL' group by name" +
                "   UNION ALL SELECT name, max(donorEmail) as email, '' as phone, '' as location, '' as photo, '' as fb, if(count(amount) > 1 AND sum(amount) > 0, 'RETURNING', 'ONE_TIME') as type, '' as status, max(cretime) as lastDate, min(cretime) as firstDate, sum(amount) as amount  from facebook_donations  where name <> '' group by name" +
                " ) temp" +
                " group by name order by lastDate desc LIMIT 200 ")

        rows = db_query(query)

        heading1 = "Recent donors"

        return render_template("donors.html", rows=rows, heading1=heading1)

    # if POST request, generate a custom query for search
    if request.method == "POST":

        query = ("SELECT * FROM ( " +
                "  SELECT name, max(email) as email, max(phone) as phone, max(location) as location, max(photo) as photo, max(fb) as fb, if(max(status) <> '', 'RECURRING', max(type)) as type, if(group_concat(status) like '%active%', 'Active', max(status)) as status, max(lastDate) as lastDate, min(firstDate) as firstDate, sum(amount) as amount" +
                "  FROM (" +
                "     SELECT name, max(email) as email, max(phone) as phone, max(concat(city, ' ', state)) as location, max(photoUrl) as photo, max(facebookUrl) as fb, if(recurringStatus <> '', 'RECURRING', max(donorType)) as type, if(group_concat(recurringStatus) like '%active%', 'Active', max(recurringStatus)) as status, lastDate, firstDate, amount FROM funraise_donors_friends left join (   SELECT max(cretime) as lastDate, min(cretime) as firstDate, donorName, sum(CASE WHEN status = 'Complete' AND formName <> 'Facebook' THEN amount ELSE 0 END) as amount    FROM `funraise_donations_friends`   group by donorName ) temp on temp.donorName = funraise_donors_friends.name WHERE donorType <> 'POTENTIAL' group by name" +
                "     UNION ALL SELECT name, max(donorEmail) as email, '' as phone, '' as location, '' as photo, '' as fb, if(count(amount) > 1 AND sum(amount) > 0, 'RETURNING', 'ONE_TIME') as type, '' as status, max(cretime) as lastDate, min(cretime) as firstDate, sum(amount) as amount  from facebook_donations  where name <> ''  group by name" +
                "   ) temp GROUP BY name ORDER BY lastDate desc" + 
                ") temp2 ")

        donorName = sanitize(request.form.get("donorName"))
        firstDate = sanitize(request.form.get("firstDate"))
        lastDate = sanitize(request.form.get("lastDate"))
        minAmount = sanitize(request.form.get("minAmount"))
        maxAmount = sanitize(request.form.get("maxAmount"))
        status = sanitize(request.form.get("status"))
        donorType = sanitize(request.form.get("donorType"))

        query += " WHERE "

        if donorName:
            query += " name like '%" + donorName + "%'"
            query += " AND "

        if firstDate:
            query += " firstDate >= '" + firstDate + "'"
            query += " AND "

        if lastDate:
            query += " DATE_ADD(lastDate, INTERVAL -1 DAY) <= '" + lastDate + "'"
            query += " AND "

        if minAmount:
            query += " amount >= '" + minAmount + "'"
            query += " AND "

        if maxAmount:
            query += " amount <= '" + maxAmount + "'"
            query += " AND "

        if status:
            query += " status = '" + status + "'"
            query += " AND "

        if donorType:
            query += " type = '" + donorType + "'"
            query += " AND "

        # only show donors who have are positive (hides ppl who have been refunded
        # or have fb donations in funraise that aren't actually on fb)
        query += " name = name and amount > 0"

        heading1 = "Donor results"

        rows = db_query(query)

        return render_template("donors.html", rows=rows, heading1=heading1)

@app.route('/donors_search')
@login_required
def donors_search():
    return render_template("donors_search.html")

@app.route('/admin', methods=["GET", "POST"])
@login_required
def admin():

    if request.method == "GET":
        query = "select * from users"
        rows = db_query(query)
        return render_template("admin.html", rows=rows)

    if request.method == "POST":

        name = sanitize(request.form.get("name"))
        email = sanitize(request.form.get("email"))

        # insert user
        query = "INSERT INTO users (id, name, email, last_auth) VALUES (NULL, '" + name + "', '" + email + "', NULL)"
        db_query(query, True)

        # refresh list
        query = "select * from users"
        rows = db_query(query)
        return render_template("admin.html", rows=rows)



