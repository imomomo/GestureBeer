from flask import Flask

from util import shared

app = Flask(__name__)

@app.route("/")
def hello_world():
    user_name = shared.USER_NAME
    return f"Hello, {user_name}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)