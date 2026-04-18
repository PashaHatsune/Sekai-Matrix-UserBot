import re
import os
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, field_validator
from mautrix.client import Client
from mautrix.api import HTTPAPI
from mautrix.crypto import OlmMachine
from mautrix.util.async_db import Database as MautrixDatabase
from mautrix.crypto.store.asyncpg import PgCryptoStore, PgCryptoStateStore
from fastapi.responses import HTMLResponse, RedirectResponse

from ... import utils, loader

DEFAULT_REPO_URL = "https://raw.githubusercontent.com/MxUserBot/mx-modules/main"

class LoginSchema(BaseModel):
    mxid: str
    password: str

    @field_validator('mxid')
    @classmethod
    def validate_mxid(cls, v: str):
        pattern = r"^@[\w\.\-]+:[\w\.\-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Format: @username:server.com")
        return v


class ModuleInstallSchema(BaseModel):
    target: str
    is_dev: bool = False


class ModuleNameSchema(BaseModel):
    name: str


class RepoSchema(BaseModel):
    url: str


async def auth_logic(data: LoginSchema, mx, auth_event):
    domain = data.mxid.split(":")[-1]
    base_url = f"https://{domain}"
    
    db_path = os.path.join(os.getcwd(), "sekai.db")
    crypto_db = MautrixDatabase.create(f"sqlite:///{db_path}")
    await crypto_db.start()
    
    await PgCryptoStore.upgrade_table.upgrade(crypto_db)
    await PgCryptoStateStore.upgrade_table.upgrade(crypto_db)

    state_store = PgCryptoStateStore(crypto_db)
    crypto_store = PgCryptoStore(data.mxid, "sekai_secret_pickle_key", crypto_db)

    temp_client = Client(
        api=HTTPAPI(base_url=base_url),
        state_store=state_store,
        sync_store=crypto_store
    )

    try:
        resp = await temp_client.login(
            identifier=data.mxid,
            password=data.password,
            initial_device_display_name="Sekai Userbot" 
        )

        temp_client.mxid = data.mxid
        temp_client.device_id = resp.device_id
        temp_client.api.token = resp.access_token

        temp_client.crypto = OlmMachine(temp_client, crypto_store, state_store)
        temp_client.crypto.allow_key_requests = True
        await temp_client.crypto.load()
        
        if not await crypto_store.get_device_id():
            await crypto_store.put_device_id(resp.device_id)
        
        await temp_client.crypto.share_keys() 
        await crypto_store.put_account(temp_client.crypto.account)

        await mx._db.set("core", "base_url", base_url)
        await mx._db.set("core", "username", data.mxid)
        await mx._db.set("core", "access_token", resp.access_token)
        await mx._db.set("core", "device_id", resp.device_id)
        await mx._db.set("core", "owner", data.mxid)
        mx.config.save()

        await temp_client.api.session.close()
        await crypto_db.stop()

        auth_event.set()
        
        return {"status": "success", "message": "Auth successful."}

    except Exception as e:
        if temp_client: await temp_client.api.session.close()
        await crypto_db.stop()
        raise HTTPException(status_code=401, detail=str(e))


def setup_routes(app: FastAPI, mx, auth_event):
    @app.post("/api/auth")
    async def auth_endpoint(data: LoginSchema = Body(...)):
        return await auth_logic(data, mx, auth_event)


    @app.get("/", response_class=HTMLResponse)
    async def get_login_page():
        if await mx._db.get("core", "access_token"):
            return RedirectResponse(url="/panel")

        html_path = os.path.join(os.getcwd(), "src/mxuserbot/core/web/index.html")
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="File index.html not found.")


    @app.get("/panel", response_class=HTMLResponse)
    async def get_panel_page():
        html_path = os.path.join(os.getcwd(), "src/mxuserbot/core/web/panel.html")
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="File panel.html not found.")

    @app.get("/api/modules/search")
    async def search_modules(query: str):
        """Search modules in all repositories"""
        if not query:
            raise HTTPException(status_code=400, detail="Query is required.")
        
        comm_repo = await utils.get_community_repo(mx._db)
        result = await utils.search_modules_in_repo(
            query.lower(), DEFAULT_REPO_URL, comm_repo, utils.request
        )

        return {"status": "success", "data": result}

    @app.post("/api/modules/install")
    async def install_module(data: ModuleInstallSchema = Body(...)):
        """Install module by ID, link, or user/repo shortcut"""
        repos = await utils.get_community_repo(mx._db)
        
        url, filename, from_community, needs_dev_warning = await utils.resolve_module_target(
            data.target, DEFAULT_REPO_URL, repos, utils.request
        )

        if not url:
            raise HTTPException(status_code=404, detail=f"Module {data.target} not found.")

        if needs_dev_warning and not data.is_dev:
            raise HTTPException(
                status_code=403, 
                detail="Confirmation is required for direct link installation (is_dev=True)."
            )
        try:
            code = await utils.request(url, return_type="text")
            success = await utils.install_module(mx.interface, filename, code)
            
            if success:
                return {"status": "success", "message": f"Module {filename} successfully installed."}
            else:
                raise HTTPException(status_code=400, detail="Invalid module structure.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/modules/uninstall")
    async def uninstall_module(data: ModuleNameSchema = Body(...)):
        """Uninstall module by its name"""
        if data.name not in mx.active_modules:
            raise HTTPException(status_code=404, detail=f"Module {data.name} is not loaded.")
            
        try:
            await utils.uninstall_module(mx.interface, data.name)
            return {"status": "success", "message": f"Module {data.name} successfully removed."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/modules/active")
    async def get_active_modules():
        """Returns a list of all active (loaded) modules"""
        return {"status": "success", "modules": list(mx.active_modules.keys())}

    @app.get("/api/repos")
    async def get_repos():
        """Returns a list of community repositories"""
        repos = await utils.get_community_repo(mx._db)
        return {"status": "success", "system_repo": DEFAULT_REPO_URL, "community_repos": repos}

    @app.post("/api/repos")
    async def add_repo(data: RepoSchema = Body(...)):
        """Adds a new community repository"""
        url = utils.convert_repo_url(data.url)
        
        try:
            test = await utils.request(f"{url}/index.json", return_type="json")
            if not test or "modules" not in test:
                raise Exception("Invalid structure")
        except:
            raise HTTPException(status_code=400, detail="Invalid repository or missing index.json.")

        repos = await utils.get_community_repo(mx._db)
        if url not in repos:
            repos.append(url)
            await utils.set_community_repo(mx._db, repos)
            
        return {"status": "success", "message": f"Repository {url} added.", "url": url}

    @app.delete("/api/repos")
    async def delete_repo(data: RepoSchema = Body(...)):
        """Removes a community repository"""
        url = utils.convert_repo_url(data.url)
        repos = await utils.get_community_repo(mx._db)
        
        if url in repos:
            repos.remove(url)
            await utils.set_community_repo(mx._db, repos)
            return {"status": "success", "message": f"Repository {url} removed."}
        else:
            raise HTTPException(status_code=404, detail="Repository not found in the list.")