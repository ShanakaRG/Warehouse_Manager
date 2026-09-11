# Putting the project on GitHub and building the .exe automatically

Once this is set up, every time you push code, GitHub builds the Windows program for you on
its own Windows computer. You never need to build the `.exe` yourself.

## Part 1: One-time setup (about 15 minutes)

1. **Create a GitHub account** at https://github.com/signup (free).
2. **Install Git for Windows** from https://git-scm.com/download/win. Keep the default options.
   Check it works: open Command Prompt and type `git --version`.
3. **Tell Git who you are** (once per computer):
   ```
   git config --global user.name "Shanaka Ramesh"
   git config --global user.email "you@example.com"
   ```
4. **Create an empty repository** on GitHub: click **+** (top right) → **New repository**.
   - Name: `warehouse-manager`
   - Choose **Private** (only you can see the code) or **Public**.
   - Do **not** tick "Add a README", ".gitignore" or "license". It must be empty.
   - Click **Create repository** and copy the address shown, e.g.
     `https://github.com/YOUR-USERNAME/warehouse-manager.git`

## Part 2: Upload the project

5. Unzip the project, e.g. to `C:\Projects\WarehouseManager-Tkinter`.
   Make sure the `.github` folder is inside it (it contains the build instructions).
6. Open Command Prompt **in that folder**: in File Explorer, click the address bar, type `cmd`,
   press Enter.
7. Run these commands one by one (use your own repository address in the 4th line):
   ```
   git init -b main
   git add .
   git commit -m "First version of Warehouse Manager"
   git remote add origin https://github.com/YOUR-USERNAME/warehouse-manager.git
   git push -u origin main
   ```
   The first push opens a browser window asking you to sign in to GitHub. Sign in and click
   **Authorize**. Git remembers this.

## Part 3: Watch the build

8. On your repository page, open the **Actions** tab. A run called **Build Windows installer**
   has started. It has two jobs:
   - **Tests** (about 2 minutes)
   - **Build .exe and installer** (about 8 to 12 minutes)

   A green tick means success. A red cross means a step failed (see Troubleshooting).

## Part 4: Download the files

9. Click the finished run, scroll to **Artifacts** at the bottom, and click
   **WarehouseManager-1.0.0-dev.1**. A zip downloads containing:

   | File | Give it to the client when... |
   |---|---|
   | `WarehouseManager-Setup-1.0.0-dev.1.exe` | they can install programs (normal installer, Start menu, desktop icon, uninstaller) |
   | `WarehouseManager-1.0.0-dev.1.exe` | they can only run an `.exe`: one file, double-click to run, nothing installed |
   | `WarehouseManager-Portable-1.0.0-dev.1.zip` | you want the faster-starting folder version without installing |

   None of them need Python on the client's PC. Artifacts are kept for 30 days.

## Part 5: Make an official numbered release

10. When a version is ready for the client:
    ```
    git tag v1.0.0
    git push origin v1.0.0
    ```
    After the build finishes, open the **Releases** section (right side of the repository page).
    **Warehouse Manager 1.0.0** is there with all three files attached, named `...1.0.0...`.
    The About window in the program shows version 1.0.0.

    If the repository is private, the client cannot open this page. Download the file and send
    it to them by email, Google Drive or USB.

## Part 6: Everyday work after changes

```
git add .
git commit -m "Short description of what you changed"
git push
```
This builds a test version (`1.0.0-dev.N`). For the next release to the client, use a new
tag number each time: `v1.0.1` for fixes, `v1.1.0` for new features.
```
git tag v1.0.1
git push origin v1.0.1
```

## Troubleshooting

| Problem | Fix |
|---|---|
| Red cross in Actions | Click the run, then the red step, and read the last lines of the log. If tests failed, run `runner.bat` option 5 on your PC to see the same error. |
| `git push` says *rejected ... fetch first* | The GitHub repository was not empty (a README was added). Run `git pull origin main --allow-unrelated-histories`, then `git push -u origin main`. |
| Build stops with *Tag must look like v1.2.3* | The tag format was wrong. Delete it with `git tag -d v1.0` and `git push origin :refs/tags/v1.0`, then tag again as `v1.0.0`. |
| Release step fails with *403* / *Resource not accessible* | Repository **Settings → Actions → General → Workflow permissions** → choose **Read and write permissions** → Save. Then re-run the job. |
| No runs appear in Actions | Check the `.github\workflows\build-windows.yml` file was uploaded (`git status` should not list it as untracked). |
| Windows says *"Windows protected your PC"* on the client | Normal for unsigned programs: **More info → Run anyway**. A code-signing certificate removes it (see docs/DESIGN.md). |

**Cost:** public repositories build for free. Private repositories include a monthly allowance
of free build minutes, and Windows minutes count at a higher rate; one build uses only a small
part of it. Check **Settings → Billing** on GitHub for your current usage.

**Prefer buttons to commands?** Install **GitHub Desktop** (https://desktop.github.com), choose
**File → Add local repository**, select the project folder, then **Publish repository**.
Later changes: write a summary, click **Commit**, then **Push origin**. Tags for releases are
created in the **History** tab (right-click a commit → **Create Tag...**, then push).
