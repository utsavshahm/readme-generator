from flask import Flask, render_template, request, jsonify
import re
from main import processRepo, askQuery
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./utsav-463717-d032d876cdd3.json"

# vectorstore = None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        github_url = request.form.get('github_url', '').strip()
        response_json, status_code = processRepo(github_url)
        
        return jsonify( {'msg' : "Repo processed successfully"}), status_code

    return render_template('index.html')


@app.route('/ask', methods=['POST'])
def ask_repo():
    query = request.form.get('query', '').strip()
    response, status = askQuery(query)
    return jsonify(response), status



if __name__ == '__main__':
    app.run(debug=True)


