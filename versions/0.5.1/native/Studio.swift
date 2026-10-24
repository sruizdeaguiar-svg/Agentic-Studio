import AppKit
import WebKit
import Security
import CoreImage

final class StudioDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate, WKScriptMessageHandler {
    var window: NSWindow!
    var webView: WKWebView!
    var backend: Process?
    var baseURL: URL?
    var quitting = false
    var log: FileHandle?
    let agentBrowser = AgentBrowser()
    var nativeSecret = ""
    var backendToken = ""
    var browserTimer: Timer?
    var scopedVolumes:[URL]=[]
    var shareWindow:NSWindow?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        let menu = NSMenu()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Acerca de Agentic Studio", action: #selector(about), keyEquivalent: "")
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "Salir de Agentic Studio", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let appItem = NSMenuItem(); appItem.submenu = appMenu; menu.addItem(appItem)
        let editMenu = NSMenu(title: "Edición")
        for (title, action, key) in [("Deshacer", "undo:", "z"), ("Cortar", "cut:", "x"), ("Copiar", "copy:", "c"), ("Pegar", "paste:", "v"), ("Seleccionar todo", "selectAll:", "a")] {
            editMenu.addItem(withTitle: title, action: Selector(action), keyEquivalent: key)
        }
        let editItem = NSMenuItem(title: "Edición", action: nil, keyEquivalent: ""); editItem.submenu = editMenu; menu.addItem(editItem)
        NSApp.mainMenu = menu
        let config = WKWebViewConfiguration()
        config.userContentController.add(self, name: "studio")
        config.websiteDataStore = .nonPersistent()
        webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.setValue(false, forKey: "drawsBackground")
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1440, height: 950), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = Bundle.main.object(forInfoDictionaryKey:"CFBundleDisplayName") as? String ?? "Agentic Studio"
        window.minSize = NSSize(width: 1000, height: 700)
        window.appearance = NSAppearance(named: .darkAqua)
        window.backgroundColor = NSColor(calibratedRed: 0.086, green: 0.094, blue: 0.098, alpha: 1)
        window.contentView = webView
        window.delegate = self
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        prepareVolume { self.startBackend() }
    }

    func prepareVolume(done:@escaping ()->Void) {
        let workspace=Bundle.main.object(forInfoDictionaryKey:"StudioWorkspace") as? String ?? ""
        guard workspace.hasPrefix("/Volumes/"), workspace.split(separator:"/").count>=2 else { done();return }
        let volume=URL(fileURLWithPath:"/Volumes/"+String(workspace.split(separator:"/")[1]),isDirectory:true)
        let key="volumeBookmark:"+volume.path
        if let data=UserDefaults.standard.data(forKey:key) {
            var stale=false
            let restored=(try? URL(resolvingBookmarkData:data,options:[.withSecurityScope,.withoutUI],relativeTo:nil,bookmarkDataIsStale:&stale)) ?? (try? URL(resolvingBookmarkData:data,options:[.withoutUI],relativeTo:nil,bookmarkDataIsStale:&stale))
            if let restored=restored, restored.standardizedFileURL==volume.standardizedFileURL {
                let scoped=restored.startAccessingSecurityScopedResource()
                if scoped { scopedVolumes.append(restored) }
                // Non-sandboxed macOS apps may already have the persistent TCC grant;
                // false from startAccessing alone does not mean permission was denied.
                let readable=(try? FileManager.default.contentsOfDirectory(atPath:workspace)) != nil
                if scoped || readable {
                    if stale, let fresh=try? restored.bookmarkData(options:scoped ? .withSecurityScope : .minimalBookmark,includingResourceValuesForKeys:nil,relativeTo:nil) { UserDefaults.standard.set(fresh,forKey:key) }
                    done();return
                }
            }
        }
        let panel=NSOpenPanel();panel.canChooseDirectories=true;panel.canChooseFiles=false;panel.allowsMultipleSelection=false;panel.directoryURL=volume
        panel.message="Selecciona "+volume.path+" para recordar el acceso de Agentic al volumen. Los permisos del agente siguen limitados a la carpeta de cada proyecto."
        panel.prompt="Recordar acceso al volumen"
        panel.begin { response in
            guard response == .OK, let chosen=panel.url, chosen.standardizedFileURL==volume.standardizedFileURL else { self.showError("Se necesita seleccionar el volumen indicado para abrir los datos. No se ha cambiado ningún permiso del agente.");NSApp.terminate(nil);return }
            if chosen.startAccessingSecurityScopedResource() { self.scopedVolumes.append(chosen) }
            do { let data=try chosen.bookmarkData(options:.withSecurityScope,includingResourceValuesForKeys:nil,relativeTo:nil);UserDefaults.standard.set(data,forKey:key) }
            catch {
                // Preserve the user-selected location for a non-sandboxed TCC grant.
                if let ordinary=try? chosen.bookmarkData(options:.minimalBookmark,includingResourceValuesForKeys:nil,relativeTo:nil) { UserDefaults.standard.set(ordinary,forKey:key) }
                else { self.showError("macOS no pudo recordar el volumen: "+error.localizedDescription) }
            }
            done()
        }
    }

    func startBackend() {
        let process = Process()
        let resources = Bundle.main.resourceURL!
        let storedWorkspace=Bundle.main.object(forInfoDictionaryKey: "StudioWorkspace") as? String ?? "@application-support"
        let workspace=storedWorkspace=="@application-support" ? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Agentic Studio").path : storedWorkspace
        let data = URL(fileURLWithPath: workspace).appendingPathComponent("data")
        do {
            try FileManager.default.createDirectory(at: data, withIntermediateDirectories: true)
            let logURL = data.appendingPathComponent("native-backend.log")
            if !FileManager.default.fileExists(atPath: logURL.path) { FileManager.default.createFile(atPath: logURL.path, contents: nil) }
            log = try FileHandle(forWritingTo: logURL); log?.seekToEndOfFile()
        } catch { showError(error.localizedDescription); return }
        var random = [UInt8](repeating: 0, count: 32)
        guard SecRandomCopyBytes(kSecRandomDefault, random.count, &random) == errSecSuccess else { showError("No se pudo crear la sesión segura."); return }
        let token = random.map { String(format: "%02x", $0) }.joined()
        backendToken = token
        nativeSecret = UUID().uuidString + UUID().uuidString
        var env = ProcessInfo.processInfo.environment
        env["AGENTIC_STUDIO_TOKEN"] = token
        env["AGENTIC_STUDIO_NATIVE_SECRET"] = nativeSecret
        env["AGENTIC_STUDIO_DATA"] = data.path
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if let support=FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask).first {
            let identity=Bundle.main.object(forInfoDictionaryKey:"StudioCredentialIdentity") as? String ?? Bundle.main.bundleIdentifier ?? "local.agenticstudio.workspace"
            let local=support.appendingPathComponent(identity,isDirectory:true)
            try? FileManager.default.createDirectory(at:local,withIntermediateDirectories:true)
            env["AGENTIC_STUDIO_LOCAL_DATA"]=local.path
        }
        env.removeValue(forKey:"PYTHONHOME");env.removeValue(forKey:"PYTHONPATH")
        env["SSL_CERT_FILE"]="/etc/ssl/cert.pem"
        env["AGENTIC_STUDIO_SHOW_SETUP"]=(Bundle.main.object(forInfoDictionaryKey:"StudioShowSetup") as? Bool == true) ? "1" : "0"
        process.environment = env
        let bundledPython=resources.appendingPathComponent("python/bin/python3")
        process.executableURL = FileManager.default.isExecutableFile(atPath:bundledPython.path) ? bundledPython : URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = ["-u", resources.appendingPathComponent("prototype/server.py").path, "--port", "0", "--parent-pid", String(ProcessInfo.processInfo.processIdentifier)]
        let pipe = Pipe(); process.standardOutput = pipe; process.standardError = log
        process.terminationHandler = { [weak self] p in
            DispatchQueue.main.async {
                guard let self = self, !self.quitting else { return }
                self.showError("El backend se ha detenido (código \(p.terminationStatus)). Consulta data/native-backend.log.")
            }
        }
        do { try process.run(); backend = process } catch { showError(error.localizedDescription); return }
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let data = pipe.fileHandleForReading.availableData
            DispatchQueue.main.async {
                guard let self = self else { return }
                guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any], let port = obj["port"] as? Int, let url = URL(string: "http://127.0.0.1:\(port)/?token=\(token)") else {
                    if !self.quitting { self.showError("No se recibió una dirección válida del backend.") }; return
                }
                self.baseURL = url
                self.webView.load(URLRequest(url: url))
                self.agentBrowser.onClosed = { [weak self] project,scope in
                    self?.nativeRequest("/api/native-browser/closed",body:["project":project,"scope":scope]) { _ in }
                }
                self.pollBrowser()
                self.browserTimer = Timer.scheduledTimer(withTimeInterval:5,repeats:true) { [weak self] _ in
                    guard let self = self, self.agentBrowser.view != nil else { return }
                    if Date().timeIntervalSince(self.agentBrowser.lastUse)>60 { self.agentBrowser.close(); return }
                    self.nativeRequest("/api/native-browser/state",body:[:]) { state in
                        if state["project"] as? String != self.agentBrowser.project || state["scope"] as? String != self.agentBrowser.scope { self.agentBrowser.close() }
                    }
                }
            }
        }
    }

    func nativeRequest(_ path:String, body:[String:Any]?, completion:@escaping ([String:Any])->Void) {
        guard let base=baseURL, let url=URL(string:path,relativeTo:base) else { return }
        var request=URLRequest(url:url); request.timeoutInterval=12
        request.setValue("Bearer " + backendToken,forHTTPHeaderField:"Authorization")
        request.setValue(nativeSecret,forHTTPHeaderField:"X-Studio-Native")
        if let body=body { request.httpMethod="POST"; request.httpBody=try? JSONSerialization.data(withJSONObject:body); request.setValue("application/json",forHTTPHeaderField:"Content-Type") }
        URLSession.shared.dataTask(with:request) { data,_,_ in
            let value=data.flatMap { try? JSONSerialization.jsonObject(with:$0) as? [String:Any] } ?? [:]
            DispatchQueue.main.async { completion(value) }
        }.resume()
    }
    func pollBrowser() {
        guard !quitting else { return }
        nativeRequest("/api/native-browser/poll",body:nil) { [weak self] job in
            guard let self=self, !self.quitting else { return }
            if let id=job["id"] as? String {
                self.nativeRequest("/api/native-job/check",body:["id":id,"project":job["project"] ?? "","scope":job["scope"] ?? ""]) { state in
                    guard state["valid"] as? Bool == true, (job["deadline"] as? Double ?? 0)>Date().timeIntervalSince1970 else {
                        self.nativeRequest("/api/native-browser/result",body:["id":id,"result":["error":"Permisos o plazo cambiados; acción cancelada."]]) { _ in self.pollBrowser() }; return
                    }
                    self.executeNativeJob(job) { result in
                        self.nativeRequest("/api/native-browser/result",body:["id":id,"result":result]) { _ in self.pollBrowser() }
                    }
                }
            } else { DispatchQueue.main.asyncAfter(deadline:.now()+0.2) { self.pollBrowser() } }
        }
    }

    func executeNativeJob(_ job:[String:Any], completion:@escaping ([String:Any])->Void) {
        guard let operation=job["operation"] as? String, let args=job["args"] as? [String:Any] else { completion(["error":"Trabajo nativo no válido."]);return }
        if operation == "lmstudio_stop" {
            let apps=NSRunningApplication.runningApplications(withBundleIdentifier:"ai.elementlabs.lmstudio")
            let cli=FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".lmstudio/bin/lms")
            // Commands are fixed and bound to LM Studio's own instance. No fallback to Agentic.
            DispatchQueue.global(qos:.userInitiated).async {
                var failures:[String]=[]
                if !apps.isEmpty && FileManager.default.isExecutableFile(atPath:cli.path) {
                    for arguments in [["unload","--all"],["server","stop"]] {
                        let task=Process();task.executableURL=cli;task.arguments=arguments
                        var env=ProcessInfo.processInfo.environment
                        env["LMS_API_SERVER_INFO_PATH"]=FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".lmstudio/.internal/http-server.json").path
                        task.environment=env;task.standardOutput=FileHandle.nullDevice;task.standardError=FileHandle.nullDevice
                        do { try task.run();let limit=Date().addingTimeInterval(6);while task.isRunning && Date()<limit { Thread.sleep(forTimeInterval:0.05) };if task.isRunning { task.terminate();failures.append("El control de LM Studio agotó su plazo.") } }
                        catch { failures.append("No se pudo contactar con el control de LM Studio.") }
                    }
                }
                DispatchQueue.main.async {
                    for app in apps { _=app.terminate() }
                    let deadline=Date().addingTimeInterval(10)
                    func check() {
                        let live=NSRunningApplication.runningApplications(withBundleIdentifier:"ai.elementlabs.lmstudio").filter{ !$0.isTerminated }
                        if live.isEmpty { completion(["closed":true,"application":"ai.elementlabs.lmstudio","cli_warnings":failures]);return }
                        if Date()>deadline { completion(["error":"LM Studio no ha terminado. El nuevo motor no se arrancará hasta cerrarlo."]);return }
                        DispatchQueue.main.asyncAfter(deadline:.now()+0.2,execute:check)
                    }
                    check()
                }
            }
            return
        }
        if operation.hasPrefix("browser_") { agentBrowser.execute(job,done:completion);return }
        if operation == "oauth_open" {
            guard let text=args["url"] as? String, let url=URL(string:text), let host=url.host, url.user == nil, url.password == nil, url.scheme == "https" || (url.scheme == "http" && (host == "127.0.0.1" || host == "::1")) else { completion(["error":"URL OAuth no válida."]);return }
            completion(NSWorkspace.shared.open(url) ? ["opened":true] : ["error":"No se pudo abrir el navegador del sistema para OAuth."]);return
        }
        guard ["vault_get","vault_put","vault_delete"].contains(operation), let account=args["account"] as? String, account.count == 64, account.allSatisfy({ $0.isHexDigit }) else { completion(["error":"Operación del llavero no válida."]);return }
        // Only this app's generic-password namespace; no shell, environment or plaintext fallback.
        let identity=Bundle.main.object(forInfoDictionaryKey:"StudioCredentialIdentity") as? String ?? Bundle.main.bundleIdentifier ?? "local.agenticstudio.workspace"
        let service=identity+".mcp.oauth"
        let query:[String:Any]=[kSecClass as String:kSecClassGenericPassword,kSecAttrService as String:service,kSecAttrAccount as String:account,kSecUseAuthenticationUI as String:kSecUseAuthenticationUIFail]
        var status:OSStatus=errSecSuccess
        if operation == "vault_get" {
            var read=query;read[kSecReturnData as String]=true;read[kSecMatchLimit as String]=kSecMatchLimitOne
            var item:CFTypeRef?;status=SecItemCopyMatching(read as CFDictionary,&item)
            if status == errSecItemNotFound { completion(["value":""]);return }
            if status == errSecSuccess, let data=item as? Data, let value=String(data:data,encoding:.utf8) { completion(["value":value]);return }
        } else if operation == "vault_delete" {
            status=SecItemDelete(query as CFDictionary)
            if status == errSecItemNotFound { status=errSecSuccess }
        } else {
            guard let value=args["value"] as? String, let data=value.data(using:.utf8), data.count <= 65536 else { completion(["error":"Credencial OAuth demasiado grande."]);return }
            status=SecItemUpdate(query as CFDictionary,[kSecValueData as String:data] as CFDictionary)
            if status == errSecItemNotFound {
                var insert=query;insert[kSecValueData as String]=data;insert[kSecAttrLabel as String]="Agentic Studio · OAuth MCP";insert[kSecAttrAccessible as String]=kSecAttrAccessibleWhenUnlockedThisDeviceOnly
                status=SecItemAdd(insert as CFDictionary,nil)
            }
        }
        completion(status == errSecSuccess ? ["ok":true] : ["error":"Llavero no disponible (\(status)). Desbloquéalo desde macOS y vuelve a conectar OAuth; no se guardarán tokens en archivos."])
    }

    @objc func about() {
        let alert = NSAlert()
        alert.messageText = "Agentic Studio · versión experimental"
        alert.informativeText = "Implementación independiente de un espacio local de agentes y modelos. No está afiliada a Element Labs. Los datos se guardan en la carpeta de trabajo configurada."
        alert.runModal()
    }

    func showError(_ message: String) {
        let alert = NSAlert(); alert.messageText = "Agentic Studio"; alert.informativeText = message; alert.alertStyle = .warning; alert.runModal()
    }

    func windowWillClose(_ notification:Notification) {
        if notification.object as? NSWindow === window { NSApp.terminate(nil) }
    }
    func windowShouldClose(_ sender:NSWindow)->Bool {
        if sender === window && !quitting { quitting=true;NSApp.terminate(nil);return false }
        return true
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String:String], message.frameInfo.isMainFrame, message.frameInfo.securityOrigin.host == "127.0.0.1", message.frameInfo.securityOrigin.port == baseURL?.port else { return }
        if body["action"] == "chooseFolder" {
            let panel = NSOpenPanel(); panel.canChooseDirectories = true; panel.canChooseFiles = false; panel.allowsMultipleSelection = false
            panel.prompt = "Usar carpeta del proyecto"
            panel.begin { response in
                if response == .OK, let url = panel.url {
                    let value = ["project": body["project"] ?? "", "path": url.path]
                    if let data = try? JSONSerialization.data(withJSONObject: value), let json = String(data: data, encoding: .utf8) {
                        self.webView.evaluateJavaScript("window.studioFolderSelected(" + json + ")", completionHandler: nil)
                    }
                }
            }
        }
        if body["action"] == "shareLAN", let text=body["url"], let components=URLComponents(string:text), components.scheme == "agenticstudio", components.host == "pair" {
            shareWindow?.close();shareWindow=nil
            let filter=CIFilter(name:"CIQRCodeGenerator");filter?.setValue(Data(text.utf8),forKey:"inputMessage")
            let image=filter?.outputImage?.transformed(by:CGAffineTransform(scaleX:8,y:8))
            let window=NSWindow(contentRect:NSRect(x:0,y:0,width:460,height:560),styleMask:[.titled,.closable],backing:.buffered,defer:false);window.title="Vincular iPhone / iPad";window.isReleasedWhenClosed=false
            let stack=NSStackView();stack.orientation = .vertical;stack.spacing=16;stack.edgeInsets=NSEdgeInsets(top:20,left:20,bottom:20,right:20)
            let label=NSTextField(wrappingLabelWithString:"Escanea este QR desde Agentic Studio en iPhone/iPad. Contiene una vinculación de un solo uso, válida cinco minutos, y la huella TLS del Mac. No lo compartas.");stack.addArrangedSubview(label)
            if let image=image { let view=NSImageView();let rep=NSCIImageRep(ciImage:image);let bitmap=NSImage(size:rep.size);bitmap.addRepresentation(rep);view.image=bitmap;view.imageScaling = .scaleProportionallyUpOrDown;view.translatesAutoresizingMaskIntoConstraints=false;view.heightAnchor.constraint(equalToConstant:340).isActive=true;stack.addArrangedSubview(view) }
            let field=NSTextField(string:text);field.isEditable=false;field.isSelectable=true;field.lineBreakMode = .byTruncatingMiddle;stack.addArrangedSubview(field)
            window.contentView=stack;window.center();window.makeKeyAndOrderFront(nil);shareWindow=window
        }
        if body["action"] == "quit" { NSApp.terminate(nil) }
        if body["action"] == "release" {
            agentBrowser.close()
            let types: Set<String> = [WKWebsiteDataTypeDiskCache, WKWebsiteDataTypeMemoryCache]
            webView.configuration.websiteDataStore.removeData(ofTypes: types, modifiedSince: Date.distantPast) {}
        }
    }
    func applicationWillTerminate(_ notification: Notification) {
        quitting = true
        browserTimer?.invalidate(); agentBrowser.close()
        if let p = backend, p.isRunning {
            p.terminate()
            let deadline = Date().addingTimeInterval(15)
            while p.isRunning && Date() < deadline { Thread.sleep(forTimeInterval: 0.05) }
        }
        for url in scopedVolumes { url.stopAccessingSecurityScopedResource() };scopedVolumes=[]
        try? log?.close()
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if navigationAction.shouldPerformDownload { decisionHandler(.download); return }
        guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
        if url.scheme == "blob" || (url.host == "127.0.0.1" && url.port == baseURL?.port) { decisionHandler(.allow) }
        else { decisionHandler(.cancel) }
    }
    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let alert = NSAlert(); alert.messageText = "Revisar acción"; alert.informativeText = message; alert.addButton(withTitle: "Aceptar"); alert.addButton(withTitle: "Cancelar")
        completionHandler(alert.runModal() == .alertFirstButtonReturn)
    }
    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel(); panel.canChooseDirectories = false; panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        completionHandler(panel.runModal() == .OK ? panel.urls : nil)
    }
    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let panel = NSSavePanel(); panel.nameFieldStringValue = suggestedFilename
        completionHandler(panel.runModal() == .OK ? panel.url : nil)
    }
}
let app = NSApplication.shared
let delegate = StudioDelegate()
app.delegate = delegate
app.run()
