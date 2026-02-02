# How to Run the RAG Application (Non-Technical Guide)

This guide walks you through running the GitHub Repository Q&A app. You can ask questions about your GitHub projects and get AI-powered answers.

---

## What You Need

1. **Docker Desktop** — A free program that runs the app in a safe, isolated environment.  
   - Download: https://www.docker.com/products/docker-desktop/  
   - Install it, then **restart your computer** and open Docker Desktop. Wait until it shows "Docker Desktop is running."

2. **Two API Keys** — Free keys that let the app talk to GitHub and an AI service:
   - **GitHub Token** — So the app can read your repositories
   - **Groq API Key** — So the app can generate answers

---

## Step 1: Get Your API Keys

### GitHub Token
1. Go to https://github.com/settings/tokens  
2. Sign in if needed  
3. Click **Generate new token** → **Generate new token (classic)**  
4. Give it a name (e.g. "RAG App")  
5. Under permissions, check **repo** (this lets it read your repositories)  
6. Click **Generate token**  
7. **Copy the token** and save it somewhere safe (you won’t see it again)

### Groq API Key
1. Go to https://console.groq.com  
2. Sign up or sign in  
3. Open **API Keys** in the left menu  
4. Click **Create API Key**  
5. Name it (e.g. "RAG App") and create it  
6. **Copy the key** and save it somewhere safe

---

## Step 2: Prepare the Application

1. **Find the project folder**  
   Open the folder where the RAG project lives (e.g. `RAG` or `e:\RAG\RAG`).

2. **Create the `.env` file**  
   - In that folder, find the file named `.env.example`  
   - Copy it and rename the copy to `.env`  
   - On Windows: right‑click `.env.example` → Copy → Paste → rename the new file to `.env`  
   - On Mac: duplicate `.env.example` and rename the copy to `.env`

3. **Put your keys in `.env`**  
   - Open `.env` in Notepad (or any text editor)  
   - Replace the placeholder text with your real keys:

   ```
   GITHUB_TOKEN=paste_your_github_token_here
   GROQ_API_KEY=paste_your_groq_api_key_here
   ```

   - Save and close the file

---

## Step 3: Start the App

1. Open **Docker Desktop** and make sure it is running.

2. Open **Terminal** (Mac/Linux) or **Command Prompt / PowerShell** (Windows).

3. Go to the project folder:
   - Windows: `cd e:\RAG\RAG` (or your actual path)
   - Mac/Linux: `cd /path/to/RAG`

4. Start the app:
   ```text
   docker compose up -d
   ```

5. Wait 1–2 minutes for everything to start.

6. Open your web browser and go to:
   ```text
   http://localhost:8501
   ```

   You should see the app page.

---

## Step 4: Load Your Data (First Time Only)

The app needs your GitHub data before you can ask questions. Do this once:

1. Make sure the app is running (`docker compose up -d`).

2. In the same project folder, run:
   ```text
   docker compose --profile pipeline run --rm pipeline
   ```

3. Wait for it to finish (it may take a few minutes). You’ll see messages about projects and commits being fetched.

4. When it’s done, go back to the app at http://localhost:8501 and ask a question.

---

## Step 5: Using the App

1. Go to http://localhost:8501  
2. Type a question in the box (e.g. "What are my most popular Python projects?")  
3. Click **Ask**  
4. The answer will appear below

---

## Stopping the App

When you’re done:

```text
docker compose down
```

This stops the app and frees system resources.

---

## Troubleshooting

### "Set GROQ_API_KEY environment variable"
- You didn’t create `.env` or didn’t put your Groq key in it.  
- Make sure `.env` is in the project folder and contains `GROQ_API_KEY=your_actual_key`.

### "Cannot connect to the Docker daemon" or similar
- Docker Desktop is not running. Start it and wait until it’s fully ready.

### The app page won’t load (http://localhost:8501)
- Give it 2–3 minutes after `docker compose up -d`.  
- Make sure nothing else is using port 8501.  
- Try restarting: `docker compose down` then `docker compose up -d`.

### "No results found" or empty answers
- Run the data loading step (Step 4) first.  
- Make sure your GitHub token has access to the repositories you expect.

### How do I update my data later?
- Run the same command as in Step 4:
  ```text
  docker compose --profile pipeline run --rm pipeline
  ```

---

## Quick Reference

| Action | Command |
|--------|---------|
| Start the app | `docker compose up -d` |
| Load or refresh data | `docker compose --profile pipeline run --rm pipeline` |
| Stop the app | `docker compose down` |
| Open the app | http://localhost:8501 |
