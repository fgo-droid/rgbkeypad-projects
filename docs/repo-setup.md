# Repository Setup

`git` was not available in the current shell session when this repo layout was created.

Once Git is installed or available in PATH, initialize the repo from this folder:

```powershell
cd C:\Users\fgobe\Documents\PicoRGBKeyPad\rgbkeypad-projects
git init
git add .
git commit -m "Initial RGB keypad projects"
```

Then create a GitHub repository and push:

```powershell
git branch -M main
git remote add origin https://github.com/<your-user>/<repo-name>.git
git push -u origin main
```
