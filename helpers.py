import os
import requests
import urllib
from flask import redirect, render_template, request, session
from functools import wraps
from html import escape
from markupsafe import Markup

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/")
        return f(*args, **kwargs)
    return decorated_function

# filter to jinja to format currency
def usd(value):
    if value:
        return f"${value:,.2f}"
    return ''

# filter for jinja to url encode strings - https://coderwall.com/p/4zcoxa/urlencode-filter-in-jinja2
def urlencode_filter(s):
    if s:
        if type(s) == 'Markup':
            s = s.unescape()
        s = s.encode('utf8')
        s = urllib.parse.quote_plus(s)
        return Markup(s)
    return ''

def format_date(value):
    if value:
        return value.strftime('%Y-%m-%d')
    return ''

def sanitize(input):
    if input:
        input = input.replace("'","")
        input = input.replace('"',"")
        input = input.replace("%","")
        input = input.replace("&","")
        input = input.replace(";","")
        input = input.replace(",","")
    return input


