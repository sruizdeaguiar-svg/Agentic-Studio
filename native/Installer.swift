import AppKit
import Darwin

final class Installer: NSObject,NSApplicationDelegate {
    var commandLineInstall=false
    var window:NSWindow!
    var destination=FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Applications",isDirectory:true)
    var location=NSTextField(labelWithString:"")
    var status=NSTextField(wrappingLabelWithString:"Elige dónde instalar la aplicación. El asistente inicial detecta los modelos locales y permite conectar OpenAI mediante OAuth.")
    var installButton:NSButton!
    var chooseButton:NSButton!
    let desktop=NSButton(checkboxWithTitle:"Crear acceso en el Escritorio",target:nil,action:nil)
    func applicationDidFinishLaunching(_ notification:Notification) {
        NSApp.setActivationPolicy(.regular)
        let appMenu=NSMenu();appMenu.addItem(withTitle:"Salir del instalador",action:#selector(NSApplication.terminate(_:)),keyEquivalent:"q");let item=NSMenuItem();item.submenu=appMenu;let menu=NSMenu();menu.addItem(item);NSApp.mainMenu=menu
        let args=ProcessInfo.processInfo.arguments
        if let index=args.firstIndex(of:"--destination"),args.count>index+1 {
            commandLineInstall=true;destination=URL(fileURLWithPath:args[index+1],isDirectory:true);installButton=NSButton();chooseButton=NSButton();desktop.state=args.contains("--desktop") ? .on : .off;install();return
        }
        window=NSWindow(contentRect:NSRect(x:0,y:0,width:640,height:420),styleMask:[.titled,.closable,.miniaturizable],backing:.buffered,defer:false);window.title="Instalar Agentic Studio";window.isReleasedWhenClosed=false
        let stack=NSStackView();stack.orientation = .vertical;stack.alignment = .leading;stack.spacing=20;stack.edgeInsets=NSEdgeInsets(top:30,left:30,bottom:30,right:30)
        let title=NSTextField(labelWithString:"Agentic Studio · macOS");title.font = .systemFont(ofSize:28,weight:.semibold);stack.addArrangedSubview(title)
        stack.addArrangedSubview(status);status.preferredMaxLayoutWidth=560
        stack.addArrangedSubview(NSTextField(labelWithString:"Carpeta de instalación"));location.stringValue=destination.path;location.isSelectable=true;location.lineBreakMode = .byTruncatingMiddle;stack.addArrangedSubview(location)
        chooseButton=NSButton(title:"Elegir carpeta…",target:self,action:#selector(choose));stack.addArrangedSubview(chooseButton)
        desktop.state = .on;stack.addArrangedSubview(desktop)
        installButton=NSButton(title:"Instalar y configurar",target:self,action:#selector(install));installButton.bezelStyle = .rounded;stack.addArrangedSubview(installButton)
        let note=NSTextField(wrappingLabelWithString:"Apple Silicon · no requiere Python ni Xcode para usar la app. No incluye modelos ni motores de inferencia. La actualización conserva tus datos; el paquete no contiene conversaciones, credenciales ni firmas iOS personales.");note.font = .systemFont(ofSize:11);note.textColor = .secondaryLabelColor;note.preferredMaxLayoutWidth=560;stack.addArrangedSubview(note)
        window.contentView=stack;window.center();window.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps:true)
    }
    @objc func choose(){let panel=NSOpenPanel();panel.canChooseDirectories=true;panel.canChooseFiles=false;panel.canCreateDirectories=true;panel.allowsMultipleSelection=false;panel.directoryURL=destination;panel.message="Selecciona la carpeta que contendrá Agentic Studio.app. Los datos se guardan por separado.";if panel.runModal() == .OK,let url=panel.url{destination=url;location.stringValue=url.path}}
    func run(_ binary:String,_ args:[String]) throws {let p=Process();p.executableURL=URL(fileURLWithPath:binary);p.arguments=args;p.standardOutput=FileHandle.nullDevice;p.standardError=FileHandle.nullDevice;try p.run();p.waitUntilExit();if p.terminationStatus != 0{throw NSError(domain:"AgenticInstaller",code:Int(p.terminationStatus),userInfo:[NSLocalizedDescriptionKey:"No se pudo verificar o firmar la aplicación. La instalación anterior se conserva."])}}
    @objc func install(){
        let fm=FileManager.default,target=destination.appendingPathComponent("Agentic Studio.app",isDirectory:true)
        // The legacy identifier is retained only for migration of an existing installation.
        let identities=["local.agenticstudio.workspace","local.bionicstudio.workspace"]
        let candidates=identities.flatMap{NSRunningApplication.runningApplications(withBundleIdentifier:$0)}
        var installed:URL?=fm.fileExists(atPath:target.path) ? target : nil
        if installed == nil,let entries=try? fm.contentsOfDirectory(at:destination,includingPropertiesForKeys:nil) {
            installed=entries.first{url in url.pathExtension=="app" && Bundle(url:url)?.bundleIdentifier==identities[1] && fm.fileExists(atPath:url.appendingPathComponent("Contents/Resources/prototype/server.py").path)}
        }
        let active=candidates.filter{app in guard let url=app.bundleURL else{return true};return url.standardizedFileURL==target.standardizedFileURL || url.standardizedFileURL==installed?.standardizedFileURL}
        if !active.isEmpty{if commandLineInstall{print("Cierra Agentic Studio antes de instalar.");exit(2)};status.stringValue="Cierra Agentic Studio antes de instalar. El instalador no interrumpe generaciones ni cierra otros programas.";return}
        if let installed=installed {
            guard let existing=Bundle(url:installed),identities.contains(existing.bundleIdentifier ?? "") else {status.stringValue="La carpeta de destino contiene otra aplicación con ese nombre. Elige otra ubicación.";return}
            if commandLineInstall && !ProcessInfo.processInfo.arguments.contains("--update"){print("Ya existe una instalación; usa --update para conservarla como copia anterior.");exit(2)}
            if !commandLineInstall { let ask=NSAlert();ask.messageText="Actualizar Agentic Studio";ask.informativeText="Se conservarán los datos y una copia de la aplicación anterior. El instalador no borra carpetas de trabajo ni modelos.";ask.addButton(withTitle:"Actualizar");ask.addButton(withTitle:"Cancelar");if ask.runModal() != .alertFirstButtonReturn{return} }
        }
        installButton.isEnabled=false;chooseButton.isEnabled=false;status.stringValue="Instalando y verificando…"
        let addDesktop=desktop.state == .on
        let priorInstallation=installed
        DispatchQueue.global(qos:.userInitiated).async {
            let stage=self.destination.appendingPathComponent(".Agentic-Studio-install-"+UUID().uuidString+".app",isDirectory:true)
            var previous:URL?
            do {
                try fm.createDirectory(at:self.destination,withIntermediateDirectories:true)
                let source=Bundle.main.resourceURL!.appendingPathComponent("Payload/Agentic Studio.app",isDirectory:true)
                try self.run("/usr/bin/codesign",["--verify","--deep","--strict",source.path]);try fm.copyItem(at:source,to:stage)
                // Only preserve the data location of this exact pre-existing product.
                if let prior=priorInstallation,let b=Bundle(url:prior),var workspace=b.object(forInfoDictionaryKey:"StudioWorkspace") as? String {
                    if workspace=="@application-support" {workspace=fm.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support").appendingPathComponent(b.object(forInfoDictionaryKey:"CFBundleName") as? String ?? "Agentic Studio").path}
                    let info=stage.appendingPathComponent("Contents/Info.plist");var dict=try PropertyListSerialization.propertyList(from:Data(contentsOf:info),format:nil) as! [String:Any];dict["StudioWorkspace"]=workspace;dict["StudioCredentialIdentity"]=b.object(forInfoDictionaryKey:"StudioCredentialIdentity") as? String ?? b.bundleIdentifier;try PropertyListSerialization.data(fromPropertyList:dict,format:.xml,options:0).write(to:info,options:.atomic)
                    try self.run("/usr/bin/codesign",["--force","--deep","--sign","-",stage.path])
                }
                try self.run("/usr/bin/codesign",["--verify","--deep","--strict",stage.path])
                if let prior=priorInstallation {let backup=self.destination.appendingPathComponent("Agentic Studio.previous-"+UUID().uuidString+".app");try fm.moveItem(at:prior,to:backup);previous=backup}
                do {try fm.moveItem(at:stage,to:target)}catch{if let previous=previous{try? fm.moveItem(at:previous,to:priorInstallation ?? target)};throw error}
                var desktopNote=""
                if addDesktop {
                    let link=fm.homeDirectoryForCurrentUser.appendingPathComponent("Desktop/Agentic Studio.app")
                    do {
                        if fm.fileExists(atPath:link.path) || (try? fm.destinationOfSymbolicLink(atPath:link.path)) != nil {
                            if (try? fm.destinationOfSymbolicLink(atPath:link.path)) != nil {try fm.removeItem(at:link)}else{throw NSError(domain:"AgenticInstaller",code:1,userInfo:[NSLocalizedDescriptionKey:"Ya existe un archivo en el Escritorio; se ha conservado."])}
                        }
                        try fm.createSymbolicLink(at:link,withDestinationURL:target)
                        if let prior=priorInstallation,prior != target {
                            let oldLink=fm.homeDirectoryForCurrentUser.appendingPathComponent("Desktop").appendingPathComponent(prior.lastPathComponent)
                            if let points=try? fm.destinationOfSymbolicLink(atPath:oldLink.path),URL(fileURLWithPath:points,relativeTo:oldLink.deletingLastPathComponent()).standardizedFileURL==prior.standardizedFileURL {try fm.removeItem(at:oldLink)}
                        }
                    }catch{desktopNote=" No se cambió el Escritorio: "+error.localizedDescription}
                }
                DispatchQueue.main.async {
                    self.status.stringValue="Instalación completada en "+target.path+"."+desktopNote
                    if self.commandLineInstall{print("Instalada: "+target.path);if ProcessInfo.processInfo.arguments.contains("--no-launch"){NSApp.terminate(nil);return}}
                    let config=NSWorkspace.OpenConfiguration();config.activates=true
                    NSWorkspace.shared.openApplication(at:target,configuration:config){_,error in DispatchQueue.main.async{if let error=error{self.status.stringValue+=" No se pudo abrir: "+error.localizedDescription}}}
                    self.installButton.title="Instalada";self.chooseButton.isEnabled=true
                }
            }catch{try? fm.removeItem(at:stage);DispatchQueue.main.async{if self.commandLineInstall{print(error.localizedDescription);exit(1)};self.status.stringValue=error.localizedDescription;self.installButton.isEnabled=true;self.chooseButton.isEnabled=true}}
        }
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender:NSApplication)->Bool{true}
}
let app=NSApplication.shared;let delegate=Installer();app.delegate=delegate;app.run()
