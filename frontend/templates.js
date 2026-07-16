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
    <title>PasteDB HTML Boilerplate Document</title>
</head>
<body>
<h1>Hello World</h1>

</body>
</html>`
},
    
{
    id: "tailwind-css",
    title: "TailwindCSS Starter",
    category: "HTML",
    language: "html",
    description: "Basic TailwindCSS App",
    code: `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Tailwind CSS Starter Template</title>
  <!-- Tailwind CSS CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-800 font-sans min-h-screen flex flex-col justify-between">

  <!-- Header / Navigation -->
  <header class="bg-white shadow-sm border-b border-slate-200">
    <div class="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
      <h1 class="text-xl font-bold text-indigo-600">MyWebsite</h1>
      <nav class="space-x-4">
        <a href="#" class="text-slate-600 hover:text-indigo-600 transition">Home</a>
        <a href="#" class="text-slate-600 hover:text-indigo-600 transition">Features</a>
        <a href="#" class="text-slate-600 hover:text-indigo-600 transition">Contact</a>
      </nav>
    </div>
  </header>

  <!-- Hero Section -->
  <main class="max-w-6xl mx-auto px-4 py-16 flex-grow flex flex-col items-center justify-center text-center">
    <span class="bg-indigo-100 text-indigo-800 text-xs font-semibold px-3 py-1 rounded-full uppercase tracking-wider mb-4">
      Ready to build
    </span>
    <h2 class="text-4xl md:text-6xl font-extrabold text-slate-900 tracking-tight max-w-2xl">
      Rapidly build websites with <span class="text-indigo-600">Tailwind CSS</span>
    </h2>
    <p class="mt-4 text-lg text-slate-600 max-w-xl">
      A clean, responsive HTML starter template featuring a header, main card component, and a sticky layout.
    </p>
    <div class="mt-8 flex gap-4">
      <a href="#" class="bg-indigo-600 text-white font-medium px-6 py-3 rounded-lg shadow-md hover:bg-indigo-700 transition">
        Get Started
      </a>
      <a href="#" class="bg-white border border-slate-300 text-slate-700 font-medium px-6 py-3 rounded-lg hover:bg-slate-50 transition">
        Learn More
      </a>
    </div>
  </main>

  <!-- Footer -->
  <footer class="bg-slate-900 text-slate-400 py-6 border-t border-slate-800">
    <div class="max-w-6xl mx-auto px-4 text-center text-sm">
      <p>&copy; 2026 MyWebsite. Powered by <a href="https://tailwindcss.com" class="hover:underline text-white">Tailwind CSS</a>.</p>
    </div>
  </footer>

</body>
</html>

`
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
},
    
{
    id: "fastapi-basic",
    title: "FastAPI App",
    category: "Python",
    language: "python",
    description: "Basic  FastAPI App",
    code: `from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def my_app():
    return {"message": "Hello World"}
`
    },
    {
    id: "django-basic",
    title: "Django Basic Project",
    language: "django",
    category: "Python",
    description: "Minimal Django project structure with a Hello World view.",
    code: `# Install Django
pip install django

# Create a new project
django-admin startproject myproject

cd myproject

# Start the development server
python manage.py runserver

# myproject/views.py
from django.http import HttpResponse

def home(request):
    return HttpResponse("Hello, Django!")

# myproject/urls.py
from django.contrib import admin
from django.urls import path
from .views import home

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home),
]
`
    }
];
