import asyncio
from mautrix.types import MessageEvent

from ...core import loader, utils

DEFAULT_REPO_URL = "https://raw.githubusercontent.com/MxUserBot/mx-modules/main"

class Meta:
    name = "LoaderModule"
    _cls_doc = "Module downloader and manager with multi-repository support."
    version = "1.9.0"
    tags = ["system"]

@loader.tds
class LoaderModule(loader.Module):
    config = {
        "repo_url": loader.ConfigValue(DEFAULT_REPO_URL, "Main system repository URL"),
        "repo_warn_ok": loader.ConfigValue(False, "User accepted third-party repo warning"),
        "dev_warn_ok": loader.ConfigValue(False, "User accepted dev/file installation warning")
    }

    strings = {
        "no_url_or_reply": "❌ | <b>Provide a Module ID, User/Module shortcut, or use <code>.mdl dev [url]</code>.</b>",
        "downloading": "⏳ | <b>Downloading...</b>",
        "fetching": "⏳ | <b>Searching for <code>{id}</code>...</b>",
        "repo_not_found": "❌ | <b>Module <code>{id}</code> not found in any repository.</b>",
        "done": "✅ | <b>Module loaded: <code>{name}</code></b>",
        "error": "❌ | <b>Error: <code>{err}</code></b>",
        "reloading": "⏳ | <b>Reloading all modules...</b>",
        "reloaded_header": "<b>♻️ | Modules reloaded:</b><br>",
        "module_item": "▫️ | <b><code>{name}</code></b><br>",
        "no_name": "❌ | <b>Provide module name (without .py).</b>",
        "not_found": "❌ | <b>Module <code>{name}</code> not found.</b>",
        "unloaded": "✅ | <b>Module <code>{name}</code> unloaded and deleted.</b>",
        "search_no_query": "❌ | <b>Provide search query.</b>",
        "search_header_system": "<b>🌐 | Found in System Repository:</b><br>",
        "search_header_community": "<br><b>👥 | Found in Community ({url}):</b><br>",
        "search_item": "📦 | <b>{name}</b> (<code>{id}</code>) v<b>{version}</b><br>📝 | <i>{desc}</i><br>📥 | <b><code>.mdl {cmd_id}</code></b><br>",
        "search_empty": "❌ | <b>No results found for <code>{query}</code>.</b>",
        "repo_added": "✅ | <b>Repository added: <code>{url}</code></b>",
        "repo_removed": "✅ | <b>Repository removed.</b>",
        "repo_invalid": "❌ | <b>Invalid repository or missing index.json.</b>",
        "file_not_py": "❌ | <b>File must be <code>.py</code></b>",
        "reply_decrypt_err": "❌ | <b>Failed to decrypt file message.</b>",
        "error_url": "❌ | <b>Provide repository URL.</b>",
        "dev_usage": "❌ | <b>Direct links and files require <code>dev</code> prefix.</b><br>Example: <code>.mdl dev https://...</code>",
        "invalid_module": "❌ | <b>Module structure is invalid (Missing Meta or Module class).</b>",
        "security_repo": "⚠️ | <b>SECURITY WARNING</b><br><b>You are adding a third-party repository. Modules from unknown sources can steal your session keys.</b><br><i>Wait 5 seconds to proceed...</i>",
        "security_module": "⚠️ | <b>SECURITY WARNING</b><br><b>Installing module from a community source. This action may be unsafe.</b><br><i>Wait 5 seconds to proceed...</i>",
        "security_dev": "⚠️ | <b>SECURITY WARNING</b><br><b>You are installing a module from a file or direct link. This is for development purposes only.</b><br><i>Wait 10 seconds to proceed...</i>"
    }

    @loader.command()
    async def addrepo(self, mx, event: MessageEvent):
        """<url> — Add a community repository"""
        args = await utils.get_args(mx, event)
        if not args: return await utils.answer(mx, self.strings.get("error_url"))
        
        url = utils.convert_repo_url(args[0])
        try:
            test = await utils.request(f"{url}/index.json", return_type="json")
            if not test or "modules" not in test: raise Exception()
        except:
            return await utils.answer(mx, self.strings.get("repo_invalid"))

        if not self.config.get("repo_warn_ok"):
            await utils.answer(mx, self.strings.get("security_repo"))
            await asyncio.sleep(5)
            self.config.set("repo_warn_ok", True)

        repos = await utils.get_community_repos(self._db)
        if url not in repos:
            repos.append(url)
            await utils.set_community_repos(self._db, repos)
        
        await utils.answer(mx, self.strings.get("repo_added").format(url=url))

    @loader.command()
    async def delrepo(self, mx, event: MessageEvent):
        """<url> — Remove a community repository"""
        args = await utils.get_args(mx, event)
        if not args: return await utils.answer(mx, self.strings.get("error_url"))
        
        url = utils.convert_repo_url(args[0])
        repos = await utils.get_community_repos(self._db)
        
        if url in repos:
            repos.remove(url)
            await utils.set_community_repos(self._db, repos)
            await utils.answer(mx, self.strings.get("repo_removed"))
        else:
            await utils.answer(mx, self.strings.get("error_url"))

    @loader.command()
    async def mdl(self, mx, event: MessageEvent):
        """<url/id/user/module/reply> — Install module"""
        args = await utils.get_args(mx, event)
        reply_to = event.content.relates_to.in_reply_to if event.content.relates_to else None
        
        is_dev = args and args[0].lower() == "dev"
        if is_dev: args = args[1:]

        if reply_to and reply_to.event_id:
            if not is_dev: return await utils.answer(mx, self.strings.get("dev_usage"))

            if not self.config.get("dev_warn_ok"):
                await utils.answer(mx, self.strings.get("security_dev"))
                await asyncio.sleep(10)
                self.config.set("dev_warn_ok", True)

            try:
                replied_event = await mx.client.get_event(event.room_id, reply_to.event_id)
                filename, code_bytes = await utils.get_matrix_file_content(mx, replied_event)
            except ValueError as e:
                err_msg = str(e)
                if err_msg == "decrypt_err": return await utils.answer(mx, self.strings.get("reply_decrypt_err"))
                if err_msg == "not_a_file": return await utils.answer(mx, self.strings.get("file_not_py"))
                return await utils.answer(mx, self.strings.get("error").format(err=err_msg))

            if not filename.endswith(".py"): return await utils.answer(mx, self.strings.get("file_not_py"))
            
            await utils.answer(mx, self.strings.get("downloading"))
            try:
                success = await utils.install_module_file(self.loader, mx, filename, code_bytes.decode("utf-8"))
                if success: return await utils.answer(mx, self.strings.get("done").format(name=filename))
                else: return await utils.answer(mx, self.strings.get("invalid_module"))
            except Exception as e: 
                return await utils.answer(mx, self.strings.get("error").format(err=str(e)))

        if not args: return await utils.answer(mx, self.strings.get("no_url_or_reply"))
        target = args[0]
        
        await utils.answer(mx, self.strings.get("fetching").format(id=target))

        repos = await utils.get_community_repos(self._db)
        system_repo = self.config.get("repo_url")
        url, filename, from_community, needs_dev_warning = await utils.resolve_module_target(
            target, system_repo, repos, utils.request
        )

        if not url: return await utils.answer(mx, self.strings.get("repo_not_found").format(id=target))

        if needs_dev_warning and not is_dev:
            return await utils.answer(mx, self.strings.get("dev_usage"))

        if needs_dev_warning:
            if not self.config.get("dev_warn_ok"):
                await utils.answer(mx, self.strings.get("security_dev"))
                await asyncio.sleep(10)
                self.config.set("dev_warn_ok", True)
        elif from_community:
            await utils.answer(mx, self.strings.get("security_module"))
            await asyncio.sleep(5)

        try:
            await utils.answer(mx, self.strings.get("downloading"))
            code = await utils.request(url, return_type="text")
            
            if await utils.install_module_file(self.loader, mx, filename, code):
                await utils.answer(mx, self.strings.get("done").format(name=filename))
            else:
                await utils.answer(mx, self.strings.get("invalid_module"))
        except Exception as e: 
            await utils.answer(mx, self.strings.get("error").format(err=str(e)))

    @loader.command()
    async def msearch(self, mx, event: MessageEvent):
        """<query> — Search in all repositories"""
        args = await utils.get_args(mx, event)
        if not args: return await utils.answer(mx, self.strings.get("search_no_query"))

        query = " ".join(args).lower()
        repos = await utils.get_community_repos(self._db)
        
        results_data = await utils.search_modules_in_repos(query, self.config.get("repo_url"), repos, utils.request)

        if not results_data: 
            return await utils.answer(mx, self.strings.get("search_empty").format(query=query))

        output = ""
        for repo_data in results_data:
            output += self.strings.get("search_header_system") if repo_data["is_system"] else self.strings.get("search_header_community").format(url=repo_data["url"])
            prefix = "" if repo_data["is_system"] else f"{utils.get_prefix_from_url(repo_data['url'])}/"
            
            for mod in repo_data["modules"]:
                output += self.strings.get("search_item").format(
                    name=mod.get("name"), 
                    id=mod.get("id"), 
                    version=mod.get("version"), 
                    desc=mod.get("description"),
                    cmd_id=f"{prefix}{mod.get('id')}"
                )
        await utils.answer(mx, output)

    @loader.command()
    async def reload(self, mx, event: MessageEvent):
        """Reload all modules"""
        await utils.answer(mx, self.strings.get("reloading"))
        for name in list(mx.active_modules.keys()):
            try: await self.loader.unload_module(name, mx)
            except: continue
            
        await self.loader.register_all(mx)
        
        msg = self.strings.get("reloaded_header")
        for name in mx.active_modules.keys():
            msg += self.strings.get("module_item").format(name=name)
        await utils.answer(mx, msg)

    @loader.command()
    async def unmd(self, mx, event: MessageEvent):
        """<name> — Unload and delete module"""
        args = await utils.get_args(mx, event)
        if not args: return await utils.answer(mx, self.strings.get("no_name"))
        
        name = args[0]
        if name not in mx.active_modules: 
            return await utils.answer(mx, self.strings.get("not_found").format(name=name))
            
        try:
            await utils.uninstall_module_file(self.loader, mx, name)
            await utils.answer(mx, self.strings.get("unloaded").format(name=name))
        except Exception as e: 
            await utils.answer(mx, self.strings.get("error").format(err=str(e)))