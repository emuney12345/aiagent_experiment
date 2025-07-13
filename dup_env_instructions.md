# Guide: Creating a Duplicated Development Environment

This guide provides all the necessary steps and PowerShell commands to create a complete, independent, and parallel copy of your `ai-agent-dev` project.

---

### **Phase 1: Duplicate the Codebase**

This phase creates a physical copy of your project folder.

1.  **Navigate to Documents Directory and Copy:**
    *This command navigates to the Documents directory where your ai-agent-dev folder is located, then creates a copy.*

    ```powershell
    Set-Location "Documents"; Copy-Item -Path "ai-agent-dev" -Destination "ai-agent-dev-v2" -Recurse
    ```

2.  **(Optional) Initialize a New Git Repository for the Copy:**
    *This removes the old git history from the duplicated project and starts a fresh one, preventing any accidental pushes to your original repository.*

    ```powershell
    Set-Location "ai-agent-dev-v2"; Remove-Item -Path ".git" -Recurse -Force -ErrorAction SilentlyContinue; git init; git add .; git commit -m "Initial commit for duplicated project"
    ```

---

### **Phase 2: Manually Edit Configuration in the New Project**

Before running any Docker commands for the new project, you **must** open `ai-agent-dev-v2` in Cursor and make the following edits to prevent conflicts.

1.  **Edit `ai-agent-dev-v2/docker-compose.yml`:**
    *   Change all `ports` to be unique (e.g., `8001:8001` becomes `8002:8001`).
    *   Update the `volumes` section to point `postgres` to a new external volume.

    **Reference (`docker-compose.yml` changes):**
    ```yaml
    services:
      postgres:
        ports:
          - "127.0.0.1:5433:5432"  # CHANGED
        volumes:
          - pgdata:/var/lib/postgresql/data # This line will be replaced
    # ...
      n8n:
        ports:
          - "5679:5678"            # CHANGED
    # ...
      langchain-server:
        ports:
          - "3001:3000"            # CHANGED
    # ...
      chatbot-server:
        ports:
          - "8002:8001"            # CHANGED
    # ...
    volumes:
      pgdata:
        external: true
        name: ai-agent-dev-v2_pgdata # ADDED these three lines
    ```

2.  **Edit `ai-agent-dev-v2/chat.html`:**
    *   Update the `fetch` URL to point to the new `chatbot-server` port.

    **Reference (`chat.html` change):**
    ```javascript
    // Change this:
    fetch('http://localhost:8001/chat', { ... });
    // To this:
    fetch('http://localhost:8002/chat', { ... });
    ```

---

### **Phase 3: Duplicate the Docker Data Volume**

This phase creates a copy of your PostgreSQL database and vector embeddings.

1.  **Stop the Original System:**
    *This ensures a clean, safe copy of the database files.*

    ```powershell
    Set-Location "ai-agent-dev"; docker-compose down
    ```

2.  **Create a New, Empty Docker Volume:**

    ```powershell
    docker volume create ai-agent-dev-v2_pgdata
    ```

3.  **Copy Data from the Old Volume to the New Volume:**
    *This command uses a temporary container to copy all files from your original data volume to the new one.*

    ```powershell
    docker run --rm -v ai-agent-dev_pgdata:/source -v ai-agent-dev-v2_pgdata:/dest alpine sh -c "cp -r /source/* /dest/"
    ```

4.  **Restart the Original System:**
    *Your original environment is now back online.*

    ```powershell
    Set-Location "ai-agent-dev"; docker-compose up -d
    ```

---

### **Phase 4: Launch the Duplicated System**

Now you can build and run your new, fully independent environment.

1.  **Build and Start the Duplicated Services:**
    *The `--build` flag creates new Docker images for your `v2` project, and `-d` runs it in the background.*

    ```powershell
    Set-Location "ai-agent-dev-v2"; docker-compose up --build -d
    ```

2.  **Verify Both Systems are Running:**
    *You should see two sets of containers listed, one for `ai-agent-dev` and one for `ai-agent-dev-v2`, with different ports.*

    ```powershell
    docker ps
    ```

You now have two identical but completely separate systems. You can work in the `ai-agent-dev-v2` project without any impact on the original.
