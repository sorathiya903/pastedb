# 📋 PasteDB

> PasteDB is a modern paste-sharing platform built for quickly sharing code, notes, text snippets, and images through simple links.

🌐 Live Website: https://pastedb.netlify.app

![Frontend](https://img.shields.io/badge/Frontend-HTML%20%7C%20CSS%20%7C%20JS-blue)
![Backend](https://img.shields.io/badge/Backend-FastAPI-green)
![Database](https://img.shields.io/badge/Database-MongoDB-success)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow)


---

✨ Features

📝 Text & Code Sharing

- Create and share text snippets instantly.
- Syntax highlighting for multiple programming languages.
- Raw view for copying and exporting content.
- Markdown support with preview.

## 🔐 End-to-End Encrypted (E2EE) Pastes

PasteDB supports **End-to-End Encrypted (E2EE)** pastes for maximum privacy.

- 🔒 Content is encrypted before it leaves your device.
- 🗝️ The encryption key is never stored on the PasteDB server.
- 🚫 Server administrators cannot read encrypted pastes.
- 📱 Encryption keys remain on your trusted devices.
- 🔗 Share encrypted pastes securely with the intended recipient.
- 🛡️ Ideal for passwords, API keys, confidential notes, and sensitive code.

> **Note:** Since the server never has access to the encryption key, encrypted pastes cannot be recovered if all trusted devices or keys are lost.

🖼️ Image Sharing

- Upload and share images using links.
- Dedicated image viewer.
- View images associated with a paste.

🔒 Privacy Controls

- Public and private pastes.
- Password-protected pastes.
- Optional expiration times.

👤 User Dashboard

- Login and registration.
- Manage your own pastes.
- View and organize created content.

⚡ Built-in Utilities

- Copy to clipboard.
- HTML preview.
- Markdown rendering.
- Code execution support for selected languages.
- Mobile-friendly interface.

🎨 Modern Interface

- Responsive design.
- Dark and light themes.
- Glassmorphism-inspired UI.
- Optimized for desktop and mobile devices.

---

🚀 Tech Stack

Frontend

- HTML
- CSS
- JavaScript
- Highlight.js
- Marked.js
- DOMPurify

Backend

- FastAPI
- Python

Database

- MongoDB

Deployment

- Netlify (Frontend)
- Render (Backend)

---
## 🚀 Advanced Features
🔥 Burn after read pastes
📅 Custom expiration (10 min, 1 hour, 1 day, 1 week, 30 days, never)
📂 Image uploads alongside text and code
🎨 40+ syntax highlighting languages
🏷️ Ready-made code templates (HTML, Flask, FastAPI, Django, Tailwind CSS, etc.)
🔍 Public paste exploration and search
📱 QR code generation for quick sharing
🔗 Custom paste IDs
📊 Paste analytics (views, creation date)
🔑 API key management
🌐 REST API for creating and managing pastes
🖥️ Official VS Code extension
📄 One-click HTML preview
⚡ Code execution for supported languages

---

## 🖥️ VS Code Extension

Upload code directly from Visual Studio Code.

Features:

- Upload current file
- Upload selected text
- Secure API key storage
- Dashboard
- Copy URL automatically

Marketplace:
https://marketplace.visualstudio.com/items?itemName=adityasorathiya.pastedb

---

## 📡 Nearby Transfer

Share pastes instantly with nearby devices—no links or QR codes required.

### 🚀 How to Use

1. Open the **Transfer** page from the PasteDB **Home** or **Landing** page (`/transfer`).

2. Make the receiving device discoverable:
   - **📱 Mobile:** Hold **three fingers on the screen for 3 seconds** or **press and hold the "Be Discoverable" button for 3 seconds**.
   - **💻 Desktop / Laptop:** **Press and hold the "Be Discoverable" button for 3 seconds**.

3. The receiving device becomes **discoverable for 10 seconds**.

4. On the sender's device, open the paste you want to share and click **Nearby Share**.

5. Select the discovered device from the list and confirm the transfer.

6. The paste is sent instantly to the selected device.

### 📍 Location Permission

Nearby Transfer requires **location permission on both the sender and receiver** for reliable nearby device discovery. Your location is used only to improve discovery accuracy and is **not shared with other users**.

---

🔗 Project Links

- Website: https://pastedb.netlify.app
- Backend API: Hosted on Render
- Repository: https://github.com/sorathiya903/pastedb

---

🎯 Why PasteDB?

PasteDB was created as a learning project to explore real-world web development concepts such as:

- Authentication
- Database integration
- File handling
- API development
- Responsive UI design
- Frontend-backend communication
- Secure content sharing

The goal was to build something genuinely useful while learning modern web technologies.

---

📄 License

This project is available under the MIT License.

---

Made with passion and thousands of lines of code by Aditya Sorathiya.
