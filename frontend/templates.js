const TEMPLATES = [
{
    id: "html-basic",
    title: "HTML Boilerplate",
    category: "HTML",
    language: "html",
    description: "Basic HTML5 page",
    code: `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
</head>
<body>

</body>
</html>`
},

{
    id: "python-basic",
    title: "Python Script",
    category: "Python",
    language: "python",
    description: "Basic Python program",
    code: `def main():
    print("Hello, World!")

if __name__ == "__main__":
    main()`
},

{
    id: "flask-basic",
    title: "Flask App",
    category: "Python",
    language: "python",
    description: "Simple Flask application",
    code: `from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Hello World"

if __name__ == "__main__":
    app.run(debug=True)`
}
];
