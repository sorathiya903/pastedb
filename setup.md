# PasteDB Setup Guide

This guide explains the initial steps for running your own PasteDB
instance.

> **Status:** This is an initial self-hosting guide. Some deployment
> details may need to be updated after testing the setup on a clean
> server.

## 1. Requirements

Before starting, make sure you have:

-   Python installed (use a version supported by the project's
    dependencies).
-   MongoDB available locally or through a MongoDB connection string.
-   Git installed.
-   A Google OAuth client ID for Google sign-in.
-   A Groq API key if you want to use the AI code-explanation feature.

For a public production deployment, use a domain with HTTPS. PasteDB's
authentication cookie is configured with `Secure` and `SameSite=None`,
so normal cookie-based sign-in requires HTTPS in production.

## 2. Get the source code

Clone the repository and enter its directory:

``` bash
git clone https://github.com/sorathiya903/pastedb.git
cd pastedb
```

## 3. Configure environment variables

The backend reads the following environment variables:

  -----------------------------------------------------------------------
  Variable                Purpose                 Required?
  ----------------------- ----------------------- -----------------------
  `MONGO_URI`             MongoDB connection      Yes
                          string                  

  `SECRET_KEY`            Secret used to sign and Yes
                          verify authentication   
                          tokens                  

  `GOOGLE_CLIENT_ID`      Google OAuth client ID  Needed for Google
                          used to verify Google   sign-in
                          sign-in tokens          

  `GROQ_API_KEY`          API key for the AI      Optional if you do not
                          code-explanation        need that feature
                          endpoint                
  -----------------------------------------------------------------------

Create a `.env` file in the backend's working directory (or configure
these variables in your hosting provider):

``` env
MONGO_URI=mongodb://localhost:27017/
SECRET_KEY=replace_with_a_long_random_secret
GOOGLE_CLIENT_ID=your_google_client_id
GROQ_API_KEY=your_groq_api_key
```

Replace the example values with your own values.

**Important:**

-   Generate a strong, random value for `SECRET_KEY`. Do not use the
    example placeholder in production.
-   Keep `.env` private. Do not commit it to GitHub or share it
    publicly.
-   If you use a hosted MongoDB database, put its connection string in
    `MONGO_URI`.
-   `GROQ_API_KEY` is only needed for the AI code-explanation feature.
    The endpoint cannot provide that feature when the key is missing.

If you use a `.env` file, make sure it is loaded before importing
application modules that read environment variables during startup. The
current backend creates MongoDB clients when `main.py` and `auth.py` are
imported. Alternatively, set the environment variables directly in your
shell or hosting provider before starting the app.

## 4. Install Python dependencies

Install the dependencies listed in the repository's `requirements.txt`:

``` bash
pip install -r requirements.txt
```

If the repository does not contain a `requirements.txt`, check the
project's dependency instructions before proceeding.

## 5. Configure Google sign-in

The backend uses `GOOGLE_CLIENT_ID` to verify Google ID tokens.

Create or use a Google OAuth client ID and configure the corresponding
authorized web origins for the domain where you host the PasteDB
frontend. The frontend's Google Identity Services configuration must use
the same client ID.

The backend source provided for this guide does not use a
`GOOGLE_CLIENT_SECRET` environment variable.

## 6. Start the backend

From the directory containing `main.py`, start the FastAPI application:

``` bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

For local testing, open:

-   API health check: `http://localhost:8000/health`
-   API documentation: `http://localhost:8000/docs`

Do not expose a production server over plain HTTP. Put it behind an
HTTPS reverse proxy or use a hosting platform that provides HTTPS.

## 7. MongoDB

PasteDB uses a MongoDB database named `pasteDB`. The backend uses
collections for pastes, users, API keys, paste versions, devices, and
transfers.

Make sure the MongoDB user in your connection string has permission to
read and write to the database. Keep your database credentials private.

## 8. Frontend and custom domain

The backend and frontend are separate parts of the application. The
backend setup above does not automatically configure the frontend to use
your self-hosted API.

Before using your own deployment, check the frontend configuration and
update its API base URL to point to your backend's HTTPS address. Also
update the backend's CORS configuration to allow your frontend's origin.

**Note:** In the current backend source, the CORS origins and some
public frontend URLs are hard-coded. They are not controlled by the
environment variables listed above. A self-hosting release should make
these values configurable before treating this guide as a complete
one-command deployment.

## 9. External services and feature availability

Some backend features call external services:

-   **Groq:** used by the AI code-explanation endpoint. Configure
    `GROQ_API_KEY` to use it.
-   **SearXNG:** used by the search endpoint. The current backend source
    points to `https://searx.be/search`.
-   **Judge0:** used by the code-running endpoint. The current backend
    source points to `https://ce.judge0.com`.

These service URLs are currently hard-coded in the backend source, not
read from environment variables. Their availability and usage limits
depend on those external services.

## 10. Production checklist

Before making your instance publicly available:

-   [ ] Set a strong, private `SECRET_KEY`.
-   [ ] Use a private MongoDB connection string and restrict database
    access.
-   [ ] Configure Google OAuth for your frontend domain.
-   [ ] Serve the frontend and backend over HTTPS.
-   [ ] Update the frontend API base URL.
-   [ ] Update CORS to allow only your frontend origin(s).
-   [ ] Keep `.env` out of version control.
-   [ ] Test sign-in, paste creation, paste retrieval, and any features
    you plan to enable.

## Notes and known limitations

This guide is based on the backend source currently reviewed. The
frontend configuration, `collab.py`, and the exact dependency
manifest/deployment setup still need to be checked before all
self-hosting steps can be guaranteed. In particular, real-time
nearby-transfer behavior uses in-memory server state, so a multi-worker
deployment may need additional configuration or changes.
