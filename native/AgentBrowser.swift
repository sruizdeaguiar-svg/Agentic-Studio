import AppKit
import WebKit

// One ephemeral browser per app. It has no native message handler or access to the Studio session.
final class AgentBrowser: NSObject, WKNavigationDelegate, WKUIDelegate, NSWindowDelegate {
    var view: WKWebView?
    var window: NSWindow?
    var project = ""
    var scope = ""
    var origins: Set<String> = []
    var onClosed: ((String,String) -> Void)?
    var lastUse = Date.distantPast
    var navigating: (([String: Any]) -> Void)?
    var navigationTimer: Timer?
    let world = WKContentWorld.world(name: "AgenticStudioAgent")

    func origin(_ url: URL) -> String {
        let scheme = (url.scheme ?? "").lowercased(), host = (url.host ?? "").lowercased()
        let bracket = host.contains(":") && !host.hasPrefix("[") ? "[" + host + "]" : host
        let port = url.port
        return scheme + "://" + bracket + ((port != nil && port != (scheme == "https" ? 443 : 80)) ? ":\(port!)" : "")
    }
    func allowed(_ url: URL) -> Bool {
        return ["http", "https"].contains(url.scheme ?? "") && url.user == nil && url.password == nil && origins.contains(origin(url))
    }
    func close() {
        let previousProject=project, previousScope=scope
        navigationTimer?.invalidate(); navigationTimer = nil
        let completion = navigating; navigating = nil
        view?.stopLoading(); view?.navigationDelegate = nil; view?.uiDelegate = nil
        window?.delegate = nil; window?.close(); window = nil; view = nil
        project = ""; scope = ""; origins = []
        completion?(["error":"El navegador se cerró; acción detenida."])
        if !previousProject.isEmpty { onClosed?(previousProject,previousScope) }
    }
    func windowWillClose(_ notification: Notification) { close() }
    func execute(_ job: [String: Any], done: @escaping ([String: Any]) -> Void) {
        guard let operation = job["operation"] as? String, let pid = job["project"] as? String, let signature = job["scope"] as? String, let allowedOrigins = job["origins"] as? [String], let args = job["args"] as? [String: Any] else { done(["error":"Petición nativa no válida."]); return }
        if operation == "browser_close" {
            if project == pid { close() }
            done(["closed":true]); return
        }
        if view != nil && (project != pid || scope != signature) { close() }
        lastUse = Date()
        if view == nil {
            guard operation == "browser_navigate" else { done(["error":"Primero abre una página con browser_navigate."]); return }
            project = pid; scope = signature; origins = Set(allowedOrigins)
            // Block all resource requests except exact, user-approved origins (ports included).
            var rules: [[String: Any]] = [["trigger":["url-filter":".*"],"action":["type":"block"]]]
            for item in allowedOrigins {
                let prefix = "^" + NSRegularExpression.escapedPattern(for: item) + "/"
                rules.append(["trigger":["url-filter":prefix],"action":["type":"ignore-previous-rules"]])
            }
            guard let data = try? JSONSerialization.data(withJSONObject: rules), let text = String(data:data,encoding:.utf8) else { done(["error":"Reglas web no válidas."]); return }
            let identifier = "studio-agent-" + UUID().uuidString
            WKContentRuleListStore.default().compileContentRuleList(forIdentifier:identifier,encodedContentRuleList:text) { [weak self] list,error in
                guard let self = self else { return }
                guard let list = list, error == nil, self.project == pid, self.scope == signature else { self.close(); done(["error":"No se pudo establecer el aislamiento de orígenes. Pregunta al usuario cómo continuar. " + (error?.localizedDescription ?? "Configuración cancelada")]); return }
                let config = WKWebViewConfiguration()
                config.websiteDataStore = .nonPersistent()
                config.mediaTypesRequiringUserActionForPlayback = .all
                config.preferences.javaScriptCanOpenWindowsAutomatically = false
                config.userContentController.add(list)
                // The compiled rule is retained by this view; discard its persistent store entry.
                WKContentRuleListStore.default().removeContentRuleList(forIdentifier:identifier,completionHandler:{_ in})
                self.view = WKWebView(frame:NSRect(x:0,y:0,width:1000,height:700),configuration:config)
                self.view!.navigationDelegate = self; self.view!.uiDelegate = self
                self.window = NSWindow(contentRect:NSRect(x:0,y:0,width:1000,height:700),styleMask:[.titled,.closable,.miniaturizable,.resizable],backing:.buffered,defer:false)
                self.window!.title = "Navegador del agente · proyecto " + pid.prefix(8)
                self.window!.isReleasedWhenClosed = false
                self.window!.contentView = self.view; self.window!.delegate = self
                self.window!.center(); self.window!.orderFront(nil)
                self.execute(job,done:done)
            }
            return
        }
        if operation == "browser_navigate" {
            guard let value = args["url"] as? String, let url = URL(string:value), allowed(url) else { done(["error":"Origen web no autorizado."]); return }
            guard navigating == nil else { done(["error":"Navegación ya en curso."]); return }
            navigating = done
            navigationTimer = Timer.scheduledTimer(withTimeInterval:22,repeats:false) { [weak self] _ in
                guard let self = self else { return }
                self.view?.stopLoading(); let callback = self.navigating; self.navigating = nil
                callback?(["error":"Navegación agotó el tiempo. No se reintenta automáticamente."])
            }
            view!.load(URLRequest(url:url)); return
        }
        guard let url = view?.url, allowed(url) else { done(["error":"Página actual fuera de los orígenes autorizados."]); return }
        let script = """
        (() => {
          const op = __OP__, args = __ARGS__;
          if (op === 'browser_scroll') { window.scrollBy(0,args.pixels); globalThis.studioElements=null; return {scroll_y:window.scrollY,observe_again:true}; }
          if (op === 'browser_snapshot') {
            const visible = e => { const r=e.getBoundingClientRect(),s=getComputedStyle(e); return r.width>0&&r.height>0&&r.bottom>=0&&r.top<innerHeight&&r.right>=0&&r.left<innerWidth&&s.visibility!=='hidden'&&s.display!=='none'; };
            const nodes = Array.from(document.querySelectorAll('a[href],button,input,textarea,select,[role="button"]')).filter(visible).slice(0,60);
            globalThis.studioElements = new Map(nodes.map((e,i)=>[i+1,e]));
            const text=document.body?.innerText||'',offset=Math.max(0,args.text_offset||0);
            return {url:location.href,title:document.title,text:text.slice(offset,offset+8000),text_offset:offset,total_characters:text.length,next_text_offset:text.length>offset+8000?offset+8000:null,elements:nodes.map((e,i)=>({id:i+1,tag:e.tagName.toLowerCase(),type:e.type||'',label:(e.getAttribute('aria-label')||e.innerText||e.getAttribute('placeholder')||e.name||'').slice(0,160),href:e.tagName==='A'?e.href:undefined})),truncated:true};
          }
          const target = globalThis.studioElements?.get(args.element);
          if (!target || !target.isConnected) throw Error('Elemento caducado; vuelve a observar la página.');
          if (op === 'browser_click') { target.click(); return {clicked:args.element,url:location.href}; }
          if (op === 'browser_type') {
            if (!['INPUT','TEXTAREA'].includes(target.tagName) || ['password','file','hidden','submit','button','checkbox','radio'].includes(target.type)) throw Error('Solo campos de texto; contraseñas y archivos no admitidos.');
            const descriptor = Object.getOwnPropertyDescriptor(target.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value');
            descriptor.set.call(target,args.text); target.dispatchEvent(new Event('input',{bubbles:true})); target.dispatchEvent(new Event('change',{bubbles:true}));
            return {typed:args.element,characters:args.text.length};
          }
          throw Error('Operación del navegador no disponible.');
        })()
        """
        guard let argData = try? JSONSerialization.data(withJSONObject:args), let argText = String(data:argData,encoding:.utf8), let opData = try? JSONSerialization.data(withJSONObject:[operation]), let opText = String(data:opData,encoding:.utf8) else { done(["error":"Argumentos no válidos."]); return }
        let source = script.replacingOccurrences(of:"__OP__",with:String(opText.dropFirst().dropLast())).replacingOccurrences(of:"__ARGS__",with:argText)
        view!.evaluateJavaScript(source,in:nil,in:world) { result in
            switch result {
            case .success(let value): done(value as? [String:Any] ?? ["ok":true])
            case .failure(let error): done(["error":error.localizedDescription])
            }
        }
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        navigationTimer?.invalidate(); navigationTimer = nil
        let callback = navigating; navigating = nil
        callback?(["url":webView.url?.absoluteString ?? "","loaded":true])
    }
    func failure(_ error: Error) {
        navigationTimer?.invalidate(); navigationTimer = nil
        let callback = navigating; navigating = nil
        callback?(["error":error.localizedDescription])
    }
    func webView(_ webView: WKWebView,didFailProvisionalNavigation navigation:WKNavigation!,withError error:Error) { failure(error) }
    func webView(_ webView: WKWebView,didFail navigation:WKNavigation!,withError error:Error) { failure(error) }
    func webView(_ webView: WKWebView,decidePolicyFor navigationAction:WKNavigationAction,decisionHandler:@escaping (WKNavigationActionPolicy)->Void) {
        guard !navigationAction.shouldPerformDownload, let url=navigationAction.request.url, allowed(url), navigationAction.targetFrame != nil else {
            decisionHandler(.cancel)
            if navigating != nil { failure(NSError(domain:"AgenticBrowser",code:1,userInfo:[NSLocalizedDescriptionKey:"Navegación, redirección o descarga no autorizada."])) }
            return
        }
        decisionHandler(.allow)
    }
    func webView(_ webView:WKWebView,decidePolicyFor navigationResponse:WKNavigationResponse,decisionHandler:@escaping (WKNavigationResponsePolicy)->Void) {
        guard navigationResponse.canShowMIMEType, let url=navigationResponse.response.url, allowed(url) else { decisionHandler(.cancel); return }
        decisionHandler(.allow)
    }
    func webView(_ webView:WKWebView,createWebViewWith configuration:WKWebViewConfiguration,for navigationAction:WKNavigationAction,windowFeatures:WKWindowFeatures)->WKWebView? { nil }
    func webView(_ webView:WKWebView,runOpenPanelWith parameters:WKOpenPanelParameters,initiatedByFrame frame:WKFrameInfo,completionHandler:@escaping ([URL]?)->Void) { completionHandler(nil) }
    func webView(_ webView:WKWebView,runJavaScriptAlertPanelWithMessage message:String,initiatedByFrame frame:WKFrameInfo,completionHandler:@escaping ()->Void) { completionHandler() }
    func webView(_ webView:WKWebView,runJavaScriptConfirmPanelWithMessage message:String,initiatedByFrame frame:WKFrameInfo,completionHandler:@escaping (Bool)->Void) { completionHandler(false) }
    func webView(_ webView:WKWebView,runJavaScriptTextInputPanelWithPrompt prompt:String,defaultText:String?,initiatedByFrame frame:WKFrameInfo,completionHandler:@escaping (String?)->Void) { completionHandler(nil) }
    @available(macOS 12.0, *)
    func webView(_ webView:WKWebView,requestMediaCapturePermissionFor origin:WKSecurityOrigin,initiatedByFrame frame:WKFrameInfo,type:WKMediaCaptureType,decisionHandler:@escaping (WKPermissionDecision)->Void) { decisionHandler(.deny) }
}
